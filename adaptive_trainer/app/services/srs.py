"""SM-2 spaced repetition scheduler for vocabulary review."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vocabulary import LearnerVocabulary, VocabularyItem

_MIN_EASE_FACTOR = 1.3
_PRODUCTION_WEIGHT = 1.5
_PRODUCTION_TYPES = frozenset({"translation", "situational_prompt"})


def sm2_calculate(
    ease_factor: float,
    interval: int,
    repetitions: int,
    quality: int,
    exercise_type: str | None = None,
) -> tuple[float, int, int]:
    """Apply one SM-2 review cycle and return updated scheduling parameters.

    Args:
        ease_factor: Current ease factor (≥ 1.3).
        interval: Current interval in days.
        repetitions: Number of successful repetitions so far.
        quality: Recall quality score 0–5 (< 3 means failure).
        exercise_type: Exercise type string (e.g. "translation", "mcq").
            Production types ("translation", "situational_prompt") get a
            1.5× multiplier on positive ease-factor changes.

    Returns:
        (new_ease_factor, next_interval, new_repetitions)
    """
    ease_delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)

    # Production exercises contribute 1.5x to positive ease changes
    if ease_delta > 0 and exercise_type in _PRODUCTION_TYPES:
        ease_delta *= _PRODUCTION_WEIGHT

    new_ease = ease_factor + ease_delta
    new_ease = max(_MIN_EASE_FACTOR, new_ease)

    if quality < 3:
        # Recall failure — restart the repetition sequence
        new_repetitions = 0
        next_interval = 1
    else:
        new_repetitions = repetitions + 1
        if repetitions == 0:
            next_interval = 1
        elif repetitions == 1:
            next_interval = 6
        else:
            next_interval = round(interval * ease_factor)

    return new_ease, next_interval, new_repetitions


async def get_due_items(
    db: AsyncSession,
    learner_id: int,
    limit: int = 10,
) -> list[str]:
    """Return vocabulary words due for review today.

    Args:
        db: Async database session.
        learner_id: ID of the learner.
        limit: Maximum number of items to return.

    Returns:
        List of word strings from due vocabulary items.
    """
    today = date.today()
    result = await db.execute(
        select(VocabularyItem.word)
        .join(LearnerVocabulary, LearnerVocabulary.vocabulary_item_id == VocabularyItem.id)
        .where(LearnerVocabulary.learner_id == learner_id)
        .where(LearnerVocabulary.due_date <= today)
        .limit(limit)
    )
    return list(result.scalars().all())


async def record_review(
    db: AsyncSession,
    learner_vocab_id: int,
    quality: int,
    exercise_type: str | None = None,
) -> None:
    """Update a learner_vocabulary row after a review.

    Args:
        db: Async database session.
        learner_vocab_id: Primary key of the LearnerVocabulary row.
        quality: Recall quality score 0–5.
        exercise_type: The exercise type used for this review (e.g. "translation").
    """
    lv = await db.get(LearnerVocabulary, learner_vocab_id)
    if lv is None:
        raise ValueError(f"LearnerVocabulary {learner_vocab_id} not found")

    new_ease, next_interval, new_repetitions = sm2_calculate(
        lv.ease_factor, lv.interval, lv.repetitions, quality,
        exercise_type=exercise_type,
    )

    lv.ease_factor = new_ease
    lv.interval = next_interval
    lv.repetitions = new_repetitions
    lv.due_date = date.today() + timedelta(days=next_interval)
    if exercise_type is not None:
        lv.last_exercise_type = exercise_type

    await db.commit()
