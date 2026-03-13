"""SRS vocabulary review session: quiz learners on due vocabulary words."""

import logging
import random
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.queries import get_active_convo as _get_active_convo
from app.db.session import AsyncSessionLocal
from app.models.conversation import Conversation, ConversationMode
from app.models.learner import Learner
from app.models.vocabulary import LearnerVocabulary, VocabularyItem
from app.services import srs
from app.services.evaluator import evaluate_answer
from app.services.exercise import ExerciseType
from app.services.level_tracker import update_level_after_session
from app.services.whatsapp_sender import send_message

logger = logging.getLogger(__name__)

_NO_LEARNER_TEXT = "You haven't started a lesson yet. Send 'lesson' to begin learning!"
_NO_REVIEW_TEXT = "No active review session. Send 'review' to start one."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def start_review(phone: str) -> None:
    """Start a vocabulary review session for the learner.

    Queries all vocabulary words due today, stores them in lesson_context,
    sets mode to review, and sends the first exercise.

    Args:
        phone: Learner's phone number in E.164 format.
    """
    async with AsyncSessionLocal() as db:
        learner = await _get_learner(db, phone)
        if learner is None:
            await send_message(phone, _NO_LEARNER_TEXT)
            return

        today = date.today()
        result = await db.execute(
            select(LearnerVocabulary.id, VocabularyItem.word, VocabularyItem.translations)
            .join(VocabularyItem, LearnerVocabulary.vocabulary_item_id == VocabularyItem.id)
            .where(LearnerVocabulary.learner_id == learner.id)
            .where(LearnerVocabulary.due_date <= today)
        )
        rows = result.all()

        if not rows:
            next_result = await db.execute(
                select(func.min(LearnerVocabulary.due_date))
                .where(LearnerVocabulary.learner_id == learner.id)
            )
            next_date = next_result.scalar_one_or_none()
            if next_date:
                await send_message(phone, f"No words due! Next review: {next_date.strftime('%b %d, %Y')}")
            else:
                await send_message(phone, "No vocabulary to review yet. Complete a lesson to add words!")
            return

        items = [
            {"lv_id": row[0], "word": row[1], "translations": row[2]}
            for row in rows
        ]

        for item in items:
            english = item["word"]
            roman = (item["translations"] or {}).get("roman", english)
            if random.random() < 0.5:
                item["direction"] = "en_to_kn"
                item["question"] = f"Translate to Kannada: {english}"
                item["expected"] = roman
            else:
                item["direction"] = "kn_to_en"
                item["question"] = f"Translate to English: {roman}"
                item["expected"] = english

        lesson_context = {
            "items": items,
            "current_index": 0,
            "reviewed_count": 0,
        }

        convo = await _get_or_create_convo(db, phone)
        convo.lesson_context = lesson_context
        convo.mode = ConversationMode.review
        await db.commit()

    total = len(items)
    logger.info("start_review phone=%s items=%d", phone, total)
    await send_message(phone, f"Review session: {total} word{'s' if total != 1 else ''} due. Let's go!")
    await send_message(phone, _format_exercise(items[0], index=1, total=total))


async def handle_review_answer(phone: str, learner_answer: str) -> None:
    """Handle the learner's answer to the current review exercise.

    Evaluates the answer, updates the SRS schedule, sends feedback, then
    advances to the next item or finishes the session.

    Args:
        phone: Learner's phone number in E.164 format.
        learner_answer: The raw text answer sent by the learner.
    """
    async with AsyncSessionLocal() as db:
        convo = await _get_active_convo(db, phone)
        if convo is None or not convo.lesson_context:
            await send_message(phone, _NO_REVIEW_TEXT)
            return
        ctx = dict(convo.lesson_context)

    items = ctx["items"]
    current_index = ctx["current_index"]

    if current_index >= len(items):
        await _finish_review(phone, ctx)
        return

    item = items[current_index]
    question = item["question"]
    expected = item["expected"]

    result = await evaluate_answer(
        exercise_type=ExerciseType.TRANSLATION,
        question=question,
        expected_answer=expected,
        learner_answer=learner_answer,
    )

    quality = round(result["score"] * 5)
    async with AsyncSessionLocal() as db:
        await srs.record_review(db, item["lv_id"], quality)

    await send_message(phone, _build_feedback(result, expected))

    new_index = current_index + 1
    new_reviewed = ctx.get("reviewed_count", 0) + 1
    scores = list(ctx.get("scores", []))
    scores.append(result["score"])
    updated_ctx = {**ctx, "current_index": new_index, "reviewed_count": new_reviewed, "scores": scores}

    async with AsyncSessionLocal() as db:
        convo = await _get_active_convo(db, phone)
        if convo is not None:
            convo.lesson_context = updated_ctx
            await db.commit()

    if new_index < len(items):
        next_item = items[new_index]
        await send_message(phone, _format_exercise(next_item, index=new_index + 1, total=len(items)))
    else:
        await _finish_review(phone, updated_ctx)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _finish_review(phone: str, ctx: dict) -> None:
    """Send the review summary, record the session, and reset conversation."""
    reviewed = ctx.get("reviewed_count", len(ctx.get("items", [])))
    summary = f"Review complete! {reviewed} word{'s' if reviewed != 1 else ''} reviewed."
    await send_message(phone, summary)

    scores = ctx.get("scores", [])
    if scores:
        try:
            await update_level_after_session(phone, scores)
        except ValueError:
            logger.warning("Could not record review session for phone=%s", phone)

    async with AsyncSessionLocal() as db:
        convo = await _get_active_convo(db, phone)
        if convo is not None:
            convo.lesson_context = None
            convo.mode = ConversationMode.quick_lookup
            await db.commit()


def _format_exercise(item: dict, index: int, total: int) -> str:
    """Format a vocabulary item as a review exercise message."""
    return f"Word {index}/{total}\n{item['question']}"


def _build_feedback(result: dict, expected: str) -> str:
    """Build a WhatsApp feedback message from an evaluation result."""
    correct = result.get("correct", False)
    feedback = result.get("feedback", "")
    corrected = result.get("corrected_kannada")

    if correct:
        return f"\u2713 Correct! {feedback}"

    msg = f"\u2717 {feedback}"
    correction = corrected or expected
    if correction:
        msg += f"\nCorrect answer: {correction}"
    return msg


async def _get_learner(db: AsyncSession, phone: str) -> Learner | None:
    """Return the Learner for the given phone, or None."""
    result = await db.execute(select(Learner).where(Learner.phone_number == phone))
    return result.scalar_one_or_none()


async def _get_or_create_convo(db: AsyncSession, phone: str) -> Conversation:
    """Return the active non-onboarding conversation, creating one if needed."""
    convo = await _get_active_convo(db, phone)
    if convo is None:
        convo = Conversation(
            phone_number=phone,
            mode=ConversationMode.review,
            lesson_context=None,
        )
        db.add(convo)
        await db.flush()
    return convo


