"""Lesson session state machine: orchestrates the full lesson-exercise-score flow."""

import logging
import random
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.conversation import Conversation, ConversationMode
from app.models.learner import Learner
from app.models.vocabulary import LearnerVocabulary, VocabularyItem
from app.services.evaluator import evaluate_answer
from app.services.exercise import ExerciseType, generate_exercises_batch
from app.services.lesson import generate_lesson
from app.services.level_tracker import get_learner_level, update_level_after_session
from app.services.whatsapp_sender import send_message

logger = logging.getLogger(__name__)

_EXERCISE_COUNT = 4
_EXERCISE_TYPES = [ExerciseType.MCQ, ExerciseType.FILL_IN_BLANK, ExerciseType.TRANSLATION]

_NO_LESSON_TEXT = "No active lesson. Send 'lesson' to start one."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def start_lesson(phone: str, topic: str) -> None:
    """Start a lesson session for the learner.

    Gets the learner's level, generates a lesson intro and a queue of 3-5
    mixed exercises, stores session state in lesson_context, sets the
    conversation mode to lesson, then sends the intro and first exercise.

    Args:
        phone: Learner's phone number in E.164 format.
        topic: Lesson topic in English (e.g. "greetings", "food ordering").
    """
    try:
        level = await get_learner_level(phone)
    except ValueError:
        level = 1

    logger.info("start_lesson phone=%s topic=%s level=%d", phone, topic, level)

    lesson_text = await generate_lesson(level=level, topic=topic)

    exercises = await generate_exercises_batch(
        count=_EXERCISE_COUNT, level=level, topic=topic, lesson_text=lesson_text
    )
    for ex in exercises:
        if ex.get("type") == ExerciseType.MCQ:
            _shuffle_mcq_options(ex)

    lesson_context = {
        "exercises": exercises,
        "current_index": 0,
        "scores": [],
        "topic": topic,
        "level": level,
    }

    async with AsyncSessionLocal() as db:
        convo = await _get_or_create_convo(db, phone)
        convo.lesson_context = lesson_context
        convo.mode = ConversationMode.lesson
        await db.commit()

    await send_message(phone, lesson_text)
    await send_message(phone, _format_exercise(exercises[0], index=1, total=len(exercises)))


async def handle_exercise_answer(phone: str, learner_answer: str) -> None:
    """Handle the learner's answer to the current exercise.

    Loads lesson_context, evaluates the answer, sends feedback, then either
    advances to the next exercise or calls finish_lesson if all are done.

    Args:
        phone: Learner's phone number in E.164 format.
        learner_answer: The raw text answer sent by the learner.
    """
    async with AsyncSessionLocal() as db:
        convo = await _get_active_convo(db, phone)
        if convo is None or not convo.lesson_context:
            await send_message(phone, _NO_LESSON_TEXT)
            return
        ctx = dict(convo.lesson_context)

    exercises = ctx["exercises"]
    current_index = ctx["current_index"]

    if current_index >= len(exercises):
        await finish_lesson(phone)
        return

    exercise = exercises[current_index]
    ex_type = ExerciseType(exercise["type"])

    resolved_answer = _resolve_mcq_answer(exercise, ex_type, learner_answer)

    result = await evaluate_answer(
        exercise_type=ex_type,
        question=exercise["question"],
        expected_answer=exercise["answer"],
        learner_answer=resolved_answer,
    )

    await send_message(phone, _build_feedback(result, exercise))

    new_scores = ctx["scores"] + [result["score"]]
    new_index = current_index + 1
    updated_ctx = {**ctx, "scores": new_scores, "current_index": new_index}

    async with AsyncSessionLocal() as db:
        convo = await _get_active_convo(db, phone)
        if convo is not None:
            convo.lesson_context = updated_ctx
            await db.commit()

    if new_index < len(exercises):
        next_ex = exercises[new_index]
        await send_message(phone, _format_exercise(next_ex, index=new_index + 1, total=len(exercises)))
    else:
        await finish_lesson(phone)


async def finish_lesson(phone: str) -> None:
    """Finalize the lesson session.

    Records session scores, updates learner level, adds exercise vocabulary
    to SRS, sends a summary message, then clears lesson_context and sets
    the conversation mode back to quick_lookup.

    Args:
        phone: Learner's phone number in E.164 format.
    """
    async with AsyncSessionLocal() as db:
        convo = await _get_active_convo(db, phone)
        if convo is None or not convo.lesson_context:
            return
        ctx = dict(convo.lesson_context)

    scores: list[float] = ctx.get("scores", [])
    exercises: list[dict] = ctx.get("exercises", [])
    old_level: int = ctx.get("level", 1)

    if scores:
        try:
            new_level = await update_level_after_session(phone, scores)
        except ValueError:
            new_level = old_level
    else:
        new_level = old_level

    for exercise in exercises:
        answer = exercise.get("answer", "")
        explanation = exercise.get("explanation", "")
        if answer:
            await _add_or_update_vocabulary(phone, word=answer, explanation=explanation)

    total = len(scores)
    correct_count = sum(1 for s in scores if s >= 0.5)
    if new_level > old_level:
        level_note = f"up to {new_level}"
    elif new_level < old_level:
        level_note = f"down to {new_level}"
    else:
        level_note = f"{new_level} (unchanged)"

    summary = (
        f"Session complete! Score: {correct_count}/{total}. "
        f"Level: {level_note}.\n"
        "Send 'lesson' to start another session."
    )
    await send_message(phone, summary)

    async with AsyncSessionLocal() as db:
        convo = await _get_active_convo(db, phone)
        if convo is not None:
            convo.lesson_context = None
            convo.mode = ConversationMode.quick_lookup
            await db.commit()


# ---------------------------------------------------------------------------
# Exercise formatting
# ---------------------------------------------------------------------------


def _shuffle_mcq_options(exercise: dict) -> None:
    """In-place shuffle MCQ options, storing ordered list as 'shuffled_options'."""
    options = [exercise["answer"]] + list(exercise.get("distractors", []))
    random.shuffle(options)
    exercise["shuffled_options"] = options


def _format_exercise(exercise: dict, index: int, total: int) -> str:
    """Format an exercise dict as a WhatsApp-friendly text message."""
    ex_type = exercise.get("type", "")
    question = exercise.get("question", "")
    header = f"Exercise {index}/{total}"

    if ex_type == ExerciseType.MCQ:
        options = exercise.get("shuffled_options", [exercise["answer"]] + exercise.get("distractors", []))
        lettered = "\n".join(f"{chr(65 + i)}) {opt}" for i, opt in enumerate(options))
        return f"{header}\n{question}\n{lettered}"

    if ex_type == ExerciseType.FILL_IN_BLANK:
        return f"{header}\nFill in the blank:\n{question}"

    if ex_type == ExerciseType.TRANSLATION:
        return f"{header}\nTranslate to Kannada:\n{question}"

    return f"{header}\n{question}"


def _resolve_mcq_answer(exercise: dict, ex_type: ExerciseType, learner_answer: str) -> str:
    """Resolve a single-letter MCQ answer (A/B/C/D) to the actual option text."""
    if ex_type != ExerciseType.MCQ:
        return learner_answer
    stripped = learner_answer.strip().upper()
    if len(stripped) == 1 and stripped in "ABCD":
        idx = ord(stripped) - ord("A")
        options = exercise.get("shuffled_options", [])
        if 0 <= idx < len(options):
            return options[idx]
    return learner_answer


def _build_feedback(result: dict, exercise: dict) -> str:
    """Build a WhatsApp feedback message from an evaluation result."""
    correct = result.get("correct", False)
    feedback = result.get("feedback", "")
    corrected = result.get("corrected_kannada")

    if correct:
        return f"\u2713 Correct! {feedback}"

    msg = f"\u2717 {feedback}"
    correction = corrected or exercise.get("answer", "")
    if correction:
        msg += f"\nCorrect answer: {correction}"
    return msg


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _pick_exercise_types(count: int) -> list[ExerciseType]:
    """Return a list of exercise types of the given count with a mixed spread."""
    types = list(_EXERCISE_TYPES)
    while len(types) < count:
        types.append(random.choice(_EXERCISE_TYPES))
    random.shuffle(types)
    return types[:count]


async def _get_or_create_convo(db: AsyncSession, phone: str) -> Conversation:
    """Return the active non-onboarding conversation, creating one if needed."""
    convo = await _get_active_convo(db, phone)
    if convo is None:
        convo = Conversation(
            phone_number=phone,
            mode=ConversationMode.lesson,
            lesson_context=None,
        )
        db.add(convo)
        await db.flush()
    return convo


async def _get_active_convo(db: AsyncSession, phone: str) -> Conversation | None:
    """Return the most-recently-updated non-onboarding conversation, or None."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.phone_number == phone)
        .where(Conversation.mode != ConversationMode.onboarding)
        .order_by(Conversation.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_learner_id(db: AsyncSession, phone: str) -> int | None:
    """Return the learner primary key for the given phone, or None."""
    result = await db.execute(select(Learner).where(Learner.phone_number == phone))
    learner = result.scalar_one_or_none()
    return learner.id if learner else None


async def _add_or_update_vocabulary(phone: str, word: str, explanation: str) -> None:
    """Add a word to the learner's SRS vocabulary deck if not already present.

    Finds or creates the VocabularyItem for *word*, then creates a
    LearnerVocabulary entry due today if one doesn't already exist.

    Args:
        phone: Learner's phone number in E.164 format.
        word: Kannada word in Roman transliteration.
        explanation: English explanation or translation context.
    """
    async with AsyncSessionLocal() as db:
        learner_id = await _get_learner_id(db, phone)
        if learner_id is None:
            return

        result = await db.execute(select(VocabularyItem).where(VocabularyItem.word == word))
        vocab_item = result.scalar_one_or_none()
        if vocab_item is None:
            vocab_item = VocabularyItem(
                word=word,
                translations={"explanation": explanation},
                tags=[],
            )
            db.add(vocab_item)
            await db.flush()

        result = await db.execute(
            select(LearnerVocabulary)
            .where(LearnerVocabulary.learner_id == learner_id)
            .where(LearnerVocabulary.vocabulary_item_id == vocab_item.id)
        )
        if result.scalar_one_or_none() is not None:
            return

        lv = LearnerVocabulary(
            learner_id=learner_id,
            vocabulary_item_id=vocab_item.id,
            due_date=date.today(),
        )
        db.add(lv)
        await db.commit()
