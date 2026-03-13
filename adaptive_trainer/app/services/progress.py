"""Progress summary service: aggregate learner stats for the 'progress' command."""

import logging
from datetime import date

from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.models.learner import Learner
from app.models.session import SessionRecord
from app.models.vocabulary import LearnerVocabulary

logger = logging.getLogger(__name__)

_NOT_ONBOARDED_TEXT = (
    "You haven't started learning yet! 🌱\n"
    "Send *lesson* to begin your first Kannada lesson."
)

_NO_SESSIONS_TEXT = (
    "📊 Your Progress\n"
    "Level: {level}/5\n\n"
    "You haven't completed any sessions yet.\n"
    "Send *lesson* to start your first one! 🚀"
)


async def get_progress_summary(phone: str) -> str:
    """Return a formatted progress summary string for the given phone number.

    Queries learner stats from the database and formats them into a
    human-readable WhatsApp message.

    Args:
        phone: The learner's phone number.

    Returns:
        A formatted progress summary string.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Learner).where(Learner.phone_number == phone)
        )
        learner = result.scalar_one_or_none()

    if learner is None:
        return _NOT_ONBOARDED_TEXT

    async with AsyncSessionLocal() as db:
        session_stats = await db.execute(
            select(
                func.count(SessionRecord.id),
                func.avg(SessionRecord.avg_score),
            ).where(SessionRecord.learner_id == learner.id)
        )
        total_lessons, avg_score = session_stats.one()

    if total_lessons == 0:
        return _NO_SESSIONS_TEXT.format(level=learner.level)

    async with AsyncSessionLocal() as db:
        vocab_stats = await db.execute(
            select(
                func.count(LearnerVocabulary.id),
                func.count(LearnerVocabulary.id).filter(
                    LearnerVocabulary.due_date <= date.today()
                ),
            ).where(LearnerVocabulary.learner_id == learner.id)
        )
        total_vocab, due_today = vocab_stats.one()

    avg_pct = round((avg_score or 0) * 100)
    lines = [
        "📊 Your Progress",
        f"Level: {learner.level}/5",
        f"Sessions completed: {total_lessons}",
        f"Average score: {avg_pct}%",
        f"Vocabulary learned: {total_vocab} words",
        f"Due for review: {due_today} words",
    ]
    return "\n".join(lines)
