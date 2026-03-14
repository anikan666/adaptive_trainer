"""Lesson session state machine: orchestrates the full lesson-exercise-score flow."""

import logging
import random
import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.queries import get_active_convo as _get_active_convo
from app.db.session import AsyncSessionLocal
from app.models.conversation import Conversation, ConversationMode
from app.models.curriculum import LearnerUnitProgress
from app.models.learner import Learner
from app.models.vocabulary import LearnerVocabulary, VocabularyItem
from app.services.evaluator import evaluate_answer
from app.services.exercise import ExerciseType, generate_exercises_batch
from app.services.lesson import generate_lesson
from app.services.curriculum import (
    check_ring_completion,
    check_unit_completion,
    get_next_unit,
    get_unit_new_words,
)
from app.services.level_tracker import get_learner_level, update_level_after_session
from app.services.srs import get_due_items
from app.services.whatsapp_sender import send_message

logger = logging.getLogger(__name__)

_EXERCISE_COUNT = 4
_NEW_WORD_COUNT = 5
_REVIEW_WORD_COUNT = 3
_NO_LESSON_TEXT = "No active lesson. Send 'lesson' to start one."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def start_lesson(phone: str, topic: str) -> None:
    """Start a lesson session for the learner.

    If topic is the default (user typed just "lesson"), uses the curriculum
    service to select the next unit and its vocabulary. Otherwise falls back
    to freeform Claude-generated lesson on the explicit topic.

    Args:
        phone: Learner's phone number in E.164 format.
        topic: Lesson topic in English (e.g. "greetings", "food ordering").
    """
    try:
        level = await get_learner_level(phone)
    except ValueError:
        level = 1

    async with AsyncSessionLocal() as db:
        convo = await _get_active_convo(db, phone)
        if convo is not None and convo.mode in (ConversationMode.lesson, ConversationMode.review):
            ctx = convo.lesson_context
            if ctx and (ctx.get("exercises") or ctx.get("items")):
                await send_message(phone, "You have a session in progress. Type 'cancel' to end it or reply to continue.")
                return

    # Determine if this is a curriculum-driven or freeform lesson
    is_default_topic = topic.lower().strip() in ("lesson", "kannada", "")
    unit = None
    new_words: list[dict] = []
    review_words: list[str] = []
    unit_id: int | None = None

    if is_default_topic:
        unit, new_words, review_words = await _get_curriculum_context(phone)

    if unit is not None:
        unit_id = unit.id
        topic = unit.name
        logger.info(
            "start_lesson phone=%s unit=%s new_words=%d review_words=%d level=%d",
            phone, unit.name, len(new_words), len(review_words), level,
        )
    else:
        logger.info("start_lesson phone=%s topic=%s level=%d (freeform)", phone, topic, level)

    await send_message(phone, f"Starting your lesson on {topic}...")

    if new_words:
        # Curriculum-aware: pass structured words to lesson generator
        lesson_text = await generate_lesson(
            level=level, topic=topic,
            new_words=new_words, review_words=review_words,
        )
        # Build target words for exercises from both new and review words
        target_words = list(new_words)
        exercises = await generate_exercises_batch(
            count=_EXERCISE_COUNT, level=level, topic=topic,
            lesson_text=lesson_text, target_words=target_words,
        )
    else:
        # Freeform: legacy path with SRS due items
        due_items: list[str] = []
        async with AsyncSessionLocal() as db:
            learner_id = await _get_learner_id(db, phone)
            if learner_id is not None:
                due_items = await get_due_items(db, learner_id)

        lesson_text = await generate_lesson(
            level=level, topic=topic, due_items=due_items or None,
        )
        exercises = await generate_exercises_batch(
            count=_EXERCISE_COUNT, level=level, topic=topic,
            lesson_text=lesson_text,
        )

    for ex in exercises:
        if ex.get("type") == ExerciseType.MCQ:
            _shuffle_mcq_options(ex)

    lesson_context: dict = {
        "exercises": exercises,
        "current_index": 0,
        "scores": [],
        "topic": topic,
        "level": level,
    }
    if unit_id is not None:
        lesson_context["unit_id"] = unit_id

    async with AsyncSessionLocal() as db:
        convo = await _get_or_create_convo(db, phone)
        convo.lesson_context = lesson_context
        convo.mode = ConversationMode.lesson
        await db.commit()

    # Create learner_vocabulary entries for curriculum new words
    if new_words and unit_id is not None:
        for w in new_words:
            await _add_or_update_vocabulary(
                phone,
                english_word=w.get("english", ""),
                kannada_word=w.get("roman", ""),
                explanation=w.get("usage_example", ""),
                unit_id=unit_id,
            )
        # Mark unit as started
        await _ensure_unit_started(phone, unit_id)

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

    # Validate lesson_context schema — guard against corruption
    required_keys = ("exercises", "current_index", "scores")
    if not all(k in ctx for k in required_keys):
        logger.warning(
            "Corrupt lesson_context for phone=%s: missing keys %s",
            phone,
            [k for k in required_keys if k not in ctx],
        )
        async with AsyncSessionLocal() as db:
            convo = await _get_active_convo(db, phone)
            if convo is not None:
                convo.lesson_context = None
                convo.mode = ConversationMode.quick_lookup
                await db.commit()
        await send_message(phone, _NO_LESSON_TEXT)
        return

    exercises = ctx["exercises"]
    current_index = ctx["current_index"]

    if current_index >= len(exercises):
        await finish_lesson(phone)
        return

    exercise = exercises[current_index]
    ex_type = ExerciseType(exercise["type"])

    resolved_answer = _resolve_mcq_answer(exercise, ex_type, learner_answer)

    skip_words = ('skip', 'idk', "i don't know", 'pass', 'dk')
    if learner_answer.lower().strip() in skip_words:
        result = {"score": 0.0, "correct": False, "feedback": "Skipped."}
    else:
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
    to SRS, checks curriculum unit completion and level progression,
    sends a summary message, then clears lesson_context and sets
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
    unit_id: int | None = ctx.get("unit_id")

    if scores:
        try:
            new_level = await update_level_after_session(phone, scores)
        except ValueError:
            new_level = old_level
    else:
        new_level = old_level

    for exercise in exercises:
        kannada = exercise.get("answer", "")
        explanation = exercise.get("explanation", "")
        english = _extract_english_meaning(exercise)
        if kannada:
            await _add_or_update_vocabulary(
                phone, english_word=english, kannada_word=kannada, explanation=explanation,
                unit_id=unit_id,
            )

    # Check curriculum unit completion and level progression
    curriculum_note = ""
    if unit_id is not None:
        unit_complete = await check_unit_completion(phone, unit_id)
        if unit_complete:
            curriculum_note = "\nUnit complete!"
            # Check if all units in the ring are done — offer gateway test
            ring_done = await check_ring_completion(phone)
            if ring_done:
                curriculum_note += (
                    "\nAll units in this ring complete! "
                    "Send 'gateway' to take the level assessment, "
                    "or 'lesson' to continue."
                )

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
        f"Level: {level_note}.{curriculum_note}\n"
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

    if ex_type == ExerciseType.SITUATIONAL_PROMPT:
        return f"{header}\nSituation: {question}\nRespond in Kannada:"

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


# Pattern for MCQ questions like "Which Kannada word means 'hello'?"
_MCQ_MEANING_RE = re.compile(r"""means\s+['"\u2018\u2019\u201c\u201d](.+?)['"\u2018\u2019\u201c\u201d]""", re.IGNORECASE)


def _extract_english_meaning(exercise: dict) -> str:
    """Return the best English meaning to store as vocabulary for an exercise.

    - **translation**: the question IS the English sentence -- use it directly.
    - **mcq**: parse the English meaning from the question pattern
      ``"Which Kannada word means '<word>'?"``.  Falls back to explanation.
    - **fill_in_blank**: the question is a Kannada sentence with a blank --
      use the explanation which contains the English translation.
    - Any other type: prefer explanation, fall back to question.
    """
    ex_type = exercise.get("type", "")
    question = exercise.get("question", "")
    explanation = exercise.get("explanation", "")

    if ex_type in (ExerciseType.TRANSLATION, ExerciseType.SITUATIONAL_PROMPT):
        # The question is already the English sentence/scenario to translate.
        return question

    if ex_type == ExerciseType.MCQ:
        m = _MCQ_MEANING_RE.search(question)
        if m:
            return m.group(1).strip()
        # Fall back to explanation if we can't parse the pattern.
        return explanation or question

    if ex_type == ExerciseType.FILL_IN_BLANK:
        # The question is a Kannada sentence with ___ -- not useful as English.
        return explanation or question

    # Unknown type: prefer explanation over a possibly non-English question.
    return explanation or question


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



async def _get_learner_id(db: AsyncSession, phone: str) -> int | None:
    """Return the learner primary key for the given phone, or None."""
    result = await db.execute(select(Learner).where(Learner.phone_number == phone))
    learner = result.scalar_one_or_none()
    return learner.id if learner else None


async def _add_or_update_vocabulary(
    phone: str,
    english_word: str,
    kannada_word: str,
    explanation: str,
    unit_id: int | None = None,
) -> None:
    """Add a word to the learner's SRS vocabulary deck if not already present.

    Stores the English meaning as VocabularyItem.word and the Kannada
    transliteration in translations.roman so review_session can quiz in
    both directions.

    Args:
        phone: Learner's phone number in E.164 format.
        english_word: English meaning or question context.
        kannada_word: Kannada answer in Roman transliteration.
        explanation: Additional context about the word.
        unit_id: Optional curriculum unit ID to associate with the vocabulary.
    """
    async with AsyncSessionLocal() as db:
        learner_id = await _get_learner_id(db, phone)
        if learner_id is None:
            return

        result = await db.execute(
            select(VocabularyItem).where(VocabularyItem.word == english_word)
        )
        vocab_item = result.scalars().first()
        if vocab_item is None:
            vocab_item = VocabularyItem(
                word=english_word,
                translations={"roman": kannada_word, "explanation": explanation},
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

        lv_kwargs: dict = {
            "learner_id": learner_id,
            "vocabulary_item_id": vocab_item.id,
            "due_date": date.today(),
        }
        # Set unit_id if the LearnerVocabulary model supports it (added by ql-q1e)
        if unit_id is not None and hasattr(LearnerVocabulary, "unit_id"):
            lv_kwargs["unit_id"] = unit_id
        lv = LearnerVocabulary(**lv_kwargs)
        db.add(lv)
        await db.commit()


async def _get_curriculum_context(
    phone: str,
) -> tuple["object | None", list[dict], list[str]]:
    """Try to load curriculum context for the learner.

    Returns:
        (unit, new_words, review_words) where unit is a CurriculumUnit or None
        if the curriculum service is not available or no unit is found.
    """
    unit = await get_next_unit(phone)
    if unit is None:
        return None, [], []

    new_words_raw = await get_unit_new_words(phone, unit.id, count=_NEW_WORD_COUNT)
    # Convert UnitVocabulary objects to dicts for downstream use
    new_words = [
        {
            "word": w.word,
            "roman": w.roman,
            "english": w.english,
            "usage_example": getattr(w, "usage_example", ""),
        }
        for w in new_words_raw
    ]

    # Get review words from SRS due items
    review_words: list[str] = []
    async with AsyncSessionLocal() as db:
        learner_id = await _get_learner_id(db, phone)
        if learner_id is not None:
            review_words = await get_due_items(db, learner_id, limit=_REVIEW_WORD_COUNT)

    return unit, new_words, review_words


async def _ensure_unit_started(phone: str, unit_id: int) -> None:
    """Create or verify learner_unit_progress record for this unit."""
    async with AsyncSessionLocal() as db:
        learner_id = await _get_learner_id(db, phone)
        if learner_id is None:
            return

        result = await db.execute(
            select(LearnerUnitProgress)
            .where(LearnerUnitProgress.learner_id == learner_id)
            .where(LearnerUnitProgress.unit_id == unit_id)
        )
        if result.scalar_one_or_none() is not None:
            return

        progress = LearnerUnitProgress(learner_id=learner_id, unit_id=unit_id)
        db.add(progress)
        await db.commit()
