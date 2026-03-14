"""Curriculum service layer: ring-aware unit selection, completion, ring advancement."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.curriculum import CurriculumUnit, LearnerUnitProgress, UnitVocabulary
from app.models.learner import Learner
from app.models.vocabulary import LearnerVocabulary, VocabularyItem

logger = logging.getLogger(__name__)

_MAX_RING = 4  # rings 0-4


async def get_next_unit(phone: str) -> CurriculumUnit | None:
    """Return the first uncompleted curriculum unit in the learner's current ring.

    Looks at units matching the learner's current ring.
    Returns ``None`` when all units in the ring are complete — signalling
    that a gateway test is needed before advancing.
    """
    async with AsyncSessionLocal() as db:
        learner = await _get_learner(db, phone)
        if learner is None:
            return None

        return await _first_uncompleted_unit(db, learner.id, learner.current_ring)


async def _get_unit_new_words_for_learner(
    db: AsyncSession, learner_id: int, unit_id: int, count: int = 5
) -> list[UnitVocabulary]:
    """Return up to *count* unseen words from the unit for the given learner.

    Uses an existing session — no separate round trip.
    """
    seen_subq = (
        select(VocabularyItem.word)
        .join(
            LearnerVocabulary,
            LearnerVocabulary.vocabulary_item_id == VocabularyItem.id,
        )
        .where(LearnerVocabulary.learner_id == learner_id)
        .where(LearnerVocabulary.unit_id == unit_id)
    ).subquery()

    stmt = (
        select(UnitVocabulary)
        .where(UnitVocabulary.unit_id == unit_id)
        .where(UnitVocabulary.english.notin_(select(seen_subq.c.word)))
        .order_by(UnitVocabulary.id)
        .limit(count)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_unit_new_words(
    phone: str, unit_id: int, count: int = 5
) -> list[UnitVocabulary]:
    """Return up to *count* words from the unit that the learner hasn't seen.

    A word is "seen" if a ``LearnerVocabulary`` row linked to this unit
    exists for it.  Order by ``UnitVocabulary.id`` for stable ordering.
    """
    async with AsyncSessionLocal() as db:
        learner = await _get_learner(db, phone)
        if learner is None:
            return []
        return await _get_unit_new_words_for_learner(db, learner.id, unit_id, count)


async def check_unit_completion(phone: str, unit_id: int) -> bool:
    """Check whether the learner has completed all words in the given unit.

    A unit is complete when **every** word in ``unit_vocabulary`` for that unit
    exists in ``learner_vocabulary`` with ``ease_factor >= 2.5``.

    If the unit is newly complete, ``learner_unit_progress.completed_at`` is
    set to now.
    """
    async with AsyncSessionLocal() as db:
        learner = await _get_learner(db, phone)
        if learner is None:
            return False

        # Count total and mastered words in a single query.
        # Production exercises (translation, situational_prompt) get 1.5x
        # effective ease for the mastery check.
        from sqlalchemy import case, func as sa_func

        _MASTERY_THRESHOLD = 2.5
        _PRODUCTION_WEIGHT = 1.5
        effective_ease = case(
            (
                LearnerVocabulary.last_exercise_type.in_(["translation", "situational_prompt"]),
                LearnerVocabulary.ease_factor * _PRODUCTION_WEIGHT,
            ),
            else_=LearnerVocabulary.ease_factor,
        )

        mastered_subq = (
            select(VocabularyItem.word)
            .join(LearnerVocabulary, LearnerVocabulary.vocabulary_item_id == VocabularyItem.id)
            .where(LearnerVocabulary.learner_id == learner.id)
            .where(effective_ease >= _MASTERY_THRESHOLD)
        ).subquery()

        result = await db.execute(
            select(
                sa_func.count().label("total"),
                sa_func.count(case((UnitVocabulary.english.in_(select(mastered_subq.c.word)), 1))).label("mastered"),
            )
            .where(UnitVocabulary.unit_id == unit_id)
        )
        row = result.one()
        if row.total == 0:
            return False

        if row.mastered < row.total:
            return False

        # Unit is complete — stamp learner_unit_progress
        progress = await _get_or_create_progress(db, learner.id, unit_id)
        if progress.completed_at is None:
            progress.completed_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info("Unit %d completed for learner %s", unit_id, phone)

        return True


async def check_ring_completion(phone: str) -> bool:
    """Check whether all units in the learner's current ring are completed.

    Returns ``True`` if the learner is ready for a gateway test.
    """
    async with AsyncSessionLocal() as db:
        learner = await _get_learner(db, phone)
        if learner is None:
            return False

        current_ring = learner.current_ring

        units_result = await db.execute(
            select(CurriculumUnit.id).where(CurriculumUnit.ring == current_ring)
        )
        unit_ids = set(units_result.scalars().all())
        if not unit_ids:
            return False

        completed_result = await db.execute(
            select(LearnerUnitProgress.unit_id)
            .where(LearnerUnitProgress.learner_id == learner.id)
            .where(LearnerUnitProgress.unit_id.in_(unit_ids))
            .where(LearnerUnitProgress.completed_at.is_not(None))
        )
        completed_ids = set(completed_result.scalars().all())

        return unit_ids <= completed_ids


async def advance_ring(phone: str) -> int:
    """Increment the learner's current ring (cap at ``_MAX_RING``).

    Returns the new ring number.
    """
    async with AsyncSessionLocal() as db:
        learner = await _get_learner(db, phone)
        if learner is None:
            return 0

        current_ring = learner.current_ring
        if current_ring >= _MAX_RING:
            return current_ring

        new_ring = current_ring + 1
        learner.current_ring = new_ring
        await db.commit()
        logger.info(
            "Learner %s advanced from ring %d to %d",
            phone, current_ring, new_ring,
        )
        return new_ring


async def check_ring_progression(phone: str) -> int | None:
    """Check ring completion and advance if ready.

    Returns the new ring, or ``None`` if no progression occurred.
    """
    ring_complete = await check_ring_completion(phone)
    if not ring_complete:
        return None

    return await advance_ring(phone)



async def _all_ring_units_complete(phone: str, ring: int) -> bool:
    """Check whether all units at the given ring are complete for the learner.

    Unlike ``check_ring_progression``, this does NOT bump the learner's ring.
    Used to detect when a gateway test should be offered.
    """
    async with AsyncSessionLocal() as db:
        learner = await _get_learner(db, phone)
        if learner is None:
            return False

        units_result = await db.execute(
            select(CurriculumUnit.id).where(CurriculumUnit.ring == ring)
        )
        unit_ids = list(units_result.scalars().all())
        if not unit_ids:
            return False

        completed_result = await db.execute(
            select(LearnerUnitProgress.unit_id)
            .where(LearnerUnitProgress.learner_id == learner.id)
            .where(LearnerUnitProgress.unit_id.in_(unit_ids))
            .where(LearnerUnitProgress.completed_at.is_not(None))
        )
        completed_ids = set(completed_result.scalars().all())

        return set(unit_ids) == completed_ids


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
