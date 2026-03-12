"""Learner level tracking and adaptive difficulty.

Tracks proficiency level (1–5) updated after each session.  Level-up
after SESSIONS_TO_LEVEL_UP consecutive sessions with avg score > 0.8;
level-down after SESSIONS_TO_LEVEL_DOWN consecutive sessions with avg
score < 0.4.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.learner import Learner
from app.models.session import SessionRecord

SESSIONS_TO_LEVEL_UP = 3
SESSIONS_TO_LEVEL_DOWN = 3
LEVEL_UP_THRESHOLD = 0.8
LEVEL_DOWN_THRESHOLD = 0.4

_WINDOW = max(SESSIONS_TO_LEVEL_UP, SESSIONS_TO_LEVEL_DOWN)


async def get_learner_level(phone: str) -> int:
    """Return the current proficiency level (1–5) for the given phone number.

    Args:
        phone: Learner's phone number in E.164 format.

    Returns:
        Current level (1–5).

    Raises:
        ValueError: If no learner with that phone number exists.
    """
    async with AsyncSessionLocal() as db:
        learner = await _get_learner(db, phone)
        if learner is None:
            raise ValueError(f"No learner found for phone {phone}")
        return learner.level


async def update_level_after_session(phone: str, session_scores: list[float]) -> int:
    """Record a completed session and update the learner's level if warranted.

    Computes the average of *session_scores*, stores it, then examines the
    most recent sessions to decide whether to promote or demote.

    Args:
        phone: Learner's phone number in E.164 format.
        session_scores: Per-exercise scores in the [0.0, 1.0] range.

    Returns:
        Updated level (1–5), which may be unchanged.

    Raises:
        ValueError: If no learner with that phone number exists, or if
            *session_scores* is empty.
    """
    if not session_scores:
        raise ValueError("session_scores must not be empty")

    avg = sum(session_scores) / len(session_scores)

    async with AsyncSessionLocal() as db:
        learner = await _get_learner(db, phone)
        if learner is None:
            raise ValueError(f"No learner found for phone {phone}")

        record = SessionRecord(learner_id=learner.id, avg_score=avg)
        db.add(record)
        await db.flush()  # persist so the window query includes this record

        recent = await _recent_avg_scores(db, learner.id, _WINDOW)
        new_level = _compute_new_level(learner.level, recent)
        learner.level = new_level

        await db.commit()
        return new_level


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_learner(db: AsyncSession, phone: str) -> Learner | None:
    result = await db.execute(select(Learner).where(Learner.phone_number == phone))
    return result.scalar_one_or_none()


async def _recent_avg_scores(db: AsyncSession, learner_id: int, n: int) -> list[float]:
    """Return the avg_scores of the *n* most recent sessions, oldest-first."""
    result = await db.execute(
        select(SessionRecord.avg_score)
        .where(SessionRecord.learner_id == learner_id)
        .order_by(SessionRecord.created_at.desc())
        .limit(n)
    )
    scores = list(result.scalars().all())
    scores.reverse()  # oldest first
    return scores


def _compute_new_level(current_level: int, recent_scores: list[float]) -> int:
    """Apply level-up / level-down logic and return the new level."""
    if len(recent_scores) >= SESSIONS_TO_LEVEL_UP:
        last_n = recent_scores[-SESSIONS_TO_LEVEL_UP:]
        if all(s > LEVEL_UP_THRESHOLD for s in last_n):
            return min(5, current_level + 1)

    if len(recent_scores) >= SESSIONS_TO_LEVEL_DOWN:
        last_m = recent_scores[-SESSIONS_TO_LEVEL_DOWN:]
        if all(s < LEVEL_DOWN_THRESHOLD for s in last_m):
            return max(1, current_level - 1)

    return current_level
