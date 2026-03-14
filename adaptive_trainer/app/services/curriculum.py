"""Curriculum service layer: unit selection, completion check, ring progression."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.curriculum import CurriculumUnit, LearnerUnitProgress, UnitVocabulary
from app.models.learner import Learner
from app.models.vocabulary import LearnerVocabulary, VocabularyItem

logger = logging.getLogger(__name__)


async def get_next_unit(phone: str) -> CurriculumUnit | None:
    """Return the first uncompleted curriculum unit for the learner.

    Looks at the learner's current ring first.  If all units in that ring are
    complete, moves to the next ring.  Returns ``None`` when no curriculum
    units remain.
    """
    async with AsyncSessionLocal() as db:
        learner = await _get_learner(db, phone)
        if learner is None:
            return None

        # Try current ring first, then next rings
        for ring in range(learner.current_ring, 5):
            unit = await _first_uncompleted_unit(db, learner.id, ring)
            if unit is not None:
                return unit

    return None


async def get_unit_new_words(
    phone: str, unit_id: int, count: int = 5
) -> list[UnitVocabulary]:
    """Return up to *count* words from the unit that the learner hasn't mastered.

    A word is considered "new" if it either:
    - Does not exist in ``learner_vocabulary`` for this learner, or
    - Exists but has ``ease_factor <= 2.0`` (still weak).
    """
    async with AsyncSessionLocal() as db:
        learner = await _get_learner(db, phone)
        if learner is None:
            return []

        mastered_words_subq = (
            select(VocabularyItem.word)
            .join(
                LearnerVocabulary,
                LearnerVocabulary.vocabulary_item_id == VocabularyItem.id,
            )
            .where(LearnerVocabulary.learner_id == learner.id)
            .where(LearnerVocabulary.ease_factor > 2.0)
        ).subquery()

        # Get unit vocabulary words NOT in the mastered set
        stmt = (
            select(UnitVocabulary)
            .where(UnitVocabulary.unit_id == unit_id)
            .where(UnitVocabulary.english.notin_(select(mastered_words_subq.c.word)))
            .order_by(UnitVocabulary.id)
            .limit(count)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


async def check_unit_completion(phone: str, unit_id: int) -> bool:
    """Check whether the learner has completed all words in the given unit.

    A unit is complete when **every** word in ``unit_vocabulary`` for that unit
    exists in ``learner_vocabulary`` with ``ease_factor > 2.0`` AND
    ``interval > 6``.

    If the unit is complete and ``learner_unit_progress.completed_at`` is not
    yet set, it is set to ``now()``.

    Returns ``True`` if the unit is (now) complete.
    """
    async with AsyncSessionLocal() as db:
        learner = await _get_learner(db, phone)
        if learner is None:
            return False

        # Total words in the unit
        total_result = await db.execute(
            select(UnitVocabulary.english).where(UnitVocabulary.unit_id == unit_id)
        )
        unit_words = set(total_result.scalars().all())
        if not unit_words:
            return False

        # Words the learner has mastered (ease_factor > 2.0 AND interval > 6)
        mastered_result = await db.execute(
            select(VocabularyItem.word)
            .join(
                LearnerVocabulary,
                LearnerVocabulary.vocabulary_item_id == VocabularyItem.id,
            )
            .where(LearnerVocabulary.learner_id == learner.id)
            .where(LearnerVocabulary.ease_factor > 2.0)
            .where(LearnerVocabulary.interval > 6)
            .where(VocabularyItem.word.in_(unit_words))
        )
        mastered_words = set(mastered_result.scalars().all())

        if not unit_words.issubset(mastered_words):
            return False

        # Unit is complete — stamp learner_unit_progress
        progress = await _get_or_create_progress(db, learner.id, unit_id)
        if progress.completed_at is None:
            progress.completed_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info(
                "Unit %d completed for learner %s", unit_id, phone
            )

        return True


async def check_ring_progression(phone: str) -> int | None:
    """If all units in the learner's current ring are complete, advance ring.

    Returns the new ring, or ``None`` if no progression occurred.
    """
    async with AsyncSessionLocal() as db:
        learner = await _get_learner(db, phone)
        if learner is None:
            return None

        current_ring = learner.current_ring

        # All units in the current ring
        units_result = await db.execute(
            select(CurriculumUnit.id).where(CurriculumUnit.ring == current_ring)
        )
        unit_ids = list(units_result.scalars().all())
        if not unit_ids:
            # No curriculum units defined for this ring — no progression
            return None

        # Check that ALL have a completed learner_unit_progress row
        completed_result = await db.execute(
            select(LearnerUnitProgress.unit_id)
            .where(LearnerUnitProgress.learner_id == learner.id)
            .where(LearnerUnitProgress.unit_id.in_(unit_ids))
            .where(LearnerUnitProgress.completed_at.is_not(None))
        )
        completed_ids = set(completed_result.scalars().all())

        if set(unit_ids) != completed_ids:
            return None

        # All units complete — advance ring (cap at 4)
        if current_ring >= 4:
            return None

        learner.current_ring = current_ring + 1
        await db.commit()
        logger.info(
            "Learner %s progressed from ring %d to %d",
            phone, current_ring, learner.current_ring,
        )
        return learner.current_ring


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_learner(db: AsyncSession, phone: str) -> Learner | None:
    result = await db.execute(select(Learner).where(Learner.phone_number == phone))
    return result.scalar_one_or_none()


async def _first_uncompleted_unit(
    db: AsyncSession, learner_id: int, ring: int
) -> CurriculumUnit | None:
    """Return the first unit in *ring* that the learner hasn't completed."""
    # Subquery: unit IDs this learner has completed
    completed_subq = (
        select(LearnerUnitProgress.unit_id)
        .where(LearnerUnitProgress.learner_id == learner_id)
        .where(LearnerUnitProgress.completed_at.is_not(None))
    ).subquery()

    stmt = (
        select(CurriculumUnit)
        .where(CurriculumUnit.ring == ring)
        .where(CurriculumUnit.id.notin_(select(completed_subq.c.unit_id)))
        .order_by(CurriculumUnit.unit_order)
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _get_or_create_progress(
    db: AsyncSession, learner_id: int, unit_id: int
) -> LearnerUnitProgress:
    """Return the progress row, creating it if it doesn't exist."""
    result = await db.execute(
        select(LearnerUnitProgress)
        .where(LearnerUnitProgress.learner_id == learner_id)
        .where(LearnerUnitProgress.unit_id == unit_id)
    )
    progress = result.scalar_one_or_none()
    if progress is None:
        progress = LearnerUnitProgress(learner_id=learner_id, unit_id=unit_id)
        db.add(progress)
        await db.flush()
    return progress
