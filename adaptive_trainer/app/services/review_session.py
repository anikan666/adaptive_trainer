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
from app.models.session import SessionRecord
from app.models.vocabulary import LearnerVocabulary, VocabularyItem
from app.services import srs
from app.services.curriculum import check_ring_progression, check_unit_completion
from app.services.evaluator import evaluate_answer
from app.services.exercise import ExerciseType
from app.services.streaks import record_session_streak
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
        convo = await _get_active_convo(db, phone)
        if convo is not None and convo.mode in (ConversationMode.lesson, ConversationMode.review):
            ctx = convo.lesson_context
            if ctx and (ctx.get("exercises") or ctx.get("items")):
                await send_message(phone, "You have a session in progress. Type 'cancel' to end it or reply to continue.")
                return

    async with AsyncSessionLocal() as db:
        learner = await _get_learner(db, phone)
        if learner is None:
            await send_message(phone, _NO_LEARNER_TEXT)
            return

        today = date.today()
        due_filter = (
            select(
                LearnerVocabulary.id,
                VocabularyItem.word,
                VocabularyItem.translations,
                LearnerVocabulary.unit_id,
            )
            .join(VocabularyItem, LearnerVocabulary.vocabulary_item_id == VocabularyItem.id)
            .where(LearnerVocabulary.learner_id == learner.id)
            .where(LearnerVocabulary.due_date <= today)
        )
        count_result = await db.execute(
            select(func.count())
            .select_from(LearnerVocabulary)
            .where(LearnerVocabulary.learner_id == learner.id)
            .where(LearnerVocabulary.due_date <= today)
        )
        total_due = count_result.scalar_one()
        result = await db.execute(due_filter.limit(10))
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

    await send_message(phone, "Loading your review...")

    items = [
        {"lv_id": row[0], "word": row[1], "translations": row[2], "unit_id": row[3]}
        for row in rows
    ]
    items = _interleave_by_unit(items)

    for item in items:
        translations = item["translations"] or {}
        if "roman" in translations:
            # New format: word=English, translations.roman=Kannada
            english = item["word"]
            roman = translations["roman"]
        else:
            # Old format: word=Kannada, translations.explanation=context
            # Only Kannada is available — quiz recognition only
            roman = item["word"]
            english = translations.get("explanation", roman)

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
        "total_due": total_due,
    }

    async with AsyncSessionLocal() as db:
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

    # Validate lesson_context schema — guard against corruption
    required_keys = ("items", "current_index")
    if not all(k in ctx for k in required_keys):
        logger.warning(
            "Corrupt review lesson_context for phone=%s: missing keys %s",
            phone,
            [k for k in required_keys if k not in ctx],
        )
        async with AsyncSessionLocal() as db:
            convo = await _get_active_convo(db, phone)
            if convo is not None:
                convo.lesson_context = None
                convo.mode = ConversationMode.quick_lookup
                await db.commit()
        await send_message(phone, _NO_REVIEW_TEXT)
        return

    items = ctx["items"]
    current_index = ctx["current_index"]

    if current_index >= len(items):
        await _finish_review(phone, ctx)
        return

    item = items[current_index]
    question = item["question"]
    expected = item["expected"]

    skip_words = ('skip', 'idk', "i don't know", 'pass', 'dk')
    if learner_answer.lower().strip() in skip_words:
        result = {"score": 0.0, "correct": False, "feedback": "Skipped."}
        quality = 0
    else:
        result = await evaluate_answer(
            exercise_type=ExerciseType.TRANSLATION,
            question=question,
            expected_answer=expected,
            learner_answer=learner_answer,
        )
        # Map 0.0-1.0 score to SM-2 quality 0-5.
        # Use int() so 0.5 (score=0.5) maps to quality 2 (failure)
        # and 0.6+ maps to quality 3+ (success). This matches SM-2's
        # threshold where quality < 3 triggers a reset.
        quality = min(5, max(0, int(result["score"] * 5 + 0.5)))

    async with AsyncSessionLocal() as db:
        await srs.record_review(db, item["lv_id"], quality, exercise_type=ExerciseType.TRANSLATION)

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
    total_due = ctx.get("total_due", reviewed)
    remaining = total_due - reviewed

    # Record session
    scores = ctx.get("scores", [])
    avg_score = sum(scores) / len(scores) if scores else 0.0
    async with AsyncSessionLocal() as db:
        learner = await _get_learner(db, phone)
        if learner is not None:
            db.add(SessionRecord(learner_id=learner.id, avg_score=avg_score))
            await db.commit()

    celebration = await record_session_streak(phone)

    summary = f"Review complete! {reviewed} word{'s' if reviewed != 1 else ''} reviewed."
    if remaining > 0:
        summary += f" {remaining} more word{'s' if remaining != 1 else ''} still due — send 'review' again to continue."
    if celebration:
        summary += f"\n{celebration}"
    await send_message(phone, summary)

    # Curriculum: check unit completion for reviewed words' units
    # Compute per-unit average scores from review items
    from collections import defaultdict
    unit_scores: dict[int, list[float]] = defaultdict(list)
    items = ctx.get("items", [])
    item_scores = ctx.get("scores", [])
    for i, item in enumerate(items):
        uid = item.get("unit_id")
        if uid is not None and i < len(item_scores):
            unit_scores[uid].append(item_scores[i])

    for uid, u_scores in unit_scores.items():
        unit_avg = sum(u_scores) / len(u_scores) if u_scores else 0.0
        completed = await check_unit_completion(phone, uid, session_score=unit_avg)
        if completed:
            await check_ring_progression(phone)

    async with AsyncSessionLocal() as db:
        convo = await _get_active_convo(db, phone)
        if convo is not None:
            convo.lesson_context = None
            convo.mode = ConversationMode.quick_lookup
            await db.commit()


def _interleave_by_unit(items: list[dict]) -> list[dict]:
    """Reorder items so that consecutive items come from different units.

    Groups items by unit_id, then round-robin picks from each group
    (shuffled within each group) to maximise spacing between same-unit items.
    Items with no unit_id are treated as their own unique groups.
    """
    from collections import defaultdict

    groups: dict[object, list[dict]] = defaultdict(list)
    no_unit_counter = 0
    for item in items:
        uid = item.get("unit_id")
        if uid is None:
            # Each unit-less item gets its own bucket so they spread out
            groups[("_none", no_unit_counter)] = [item]
            no_unit_counter += 1
        else:
            groups[uid].append(item)

    # Shuffle within each group
    for g in groups.values():
        random.shuffle(g)

    # Sort groups by descending size so the largest groups get first picks,
    # maximising spacing
    buckets = sorted(groups.values(), key=len, reverse=True)

    result: list[dict] = []
    while buckets:
        next_buckets = []
        for bucket in buckets:
            result.append(bucket.pop(0))
            if bucket:
                next_buckets.append(bucket)
        buckets = next_buckets

    return result


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


