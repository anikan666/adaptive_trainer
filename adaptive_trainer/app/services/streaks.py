"""Streak tracking and milestone celebrations for session completion."""

from datetime import date, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.learner import Learner
from app.models.session import SessionRecord
from app.models.vocabulary import LearnerVocabulary


async def record_session_streak(phone: str) -> str:
    """Update the learner's streak and return celebration text (may be empty).

    Streak logic:
    - If last_session_date is yesterday: increment streak
    - If last_session_date is today: no change (already counted)
    - Otherwise: reset streak to 1

    Uses database-level updates to avoid race conditions with concurrent requests.

    Returns milestone/streak celebration text, or empty string.
    """
    today = date.today()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Learner).where(Learner.phone_number == phone)
        )
        learner = result.scalar_one_or_none()
        if learner is None:
            return ""

        last = learner.last_session_date
        if last == today:
            # Already recorded today — return streak message if noteworthy
            return _streak_message(learner.current_streak)

        if last == today - timedelta(days=1):
            new_streak = Learner.current_streak + 1
        else:
            new_streak = 1

        await db.execute(
            update(Learner)
            .where(Learner.id == learner.id)
            .values(current_streak=new_streak, last_session_date=today)
        )

        # Re-read to get the actual value after atomic update
        await db.refresh(learner)
        streak = learner.current_streak

        # Gather milestone data
        session_count = await _count_sessions(db, learner.id)
        vocab_count = await _count_vocabulary(db, learner.id)

        await db.commit()

    return _build_celebration(streak, session_count, vocab_count)


async def _count_sessions(db: AsyncSession, learner_id: int) -> int:
    result = await db.execute(
        select(func.count(SessionRecord.id))
        .where(SessionRecord.learner_id == learner_id)
    )
    return result.scalar_one()


async def _count_vocabulary(db: AsyncSession, learner_id: int) -> int:
    result = await db.execute(
        select(func.count(LearnerVocabulary.id))
        .where(LearnerVocabulary.learner_id == learner_id)
    )
    return result.scalar_one()


def _streak_message(streak: int) -> str:
    if streak >= 7:
        return f"🔥 {streak}-day streak! You're on fire!"
    if streak >= 3:
        return f"🔥 {streak}-day streak!"
    return ""


_VOCAB_MILESTONES = [10, 25, 50, 100, 200, 500]
_SESSION_MILESTONES = [5, 10, 25, 50, 100]


def _build_celebration(streak: int, session_count: int, vocab_count: int) -> str:
    parts: list[str] = []

    # Streak celebration
    streak_msg = _streak_message(streak)
    if streak_msg:
        parts.append(streak_msg)

    # Vocabulary milestones
    for m in _VOCAB_MILESTONES:
        if vocab_count == m:
            parts.append(f"🎉 {m} words learned!")
            break

    # Session milestones
    for m in _SESSION_MILESTONES:
        if session_count == m:
            parts.append(f"🎉 {m} sessions completed!")
            break

    return "\n".join(parts)
