"""Tests for the SM-2 spaced repetition scheduler."""

import os
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test_access")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test_app_secret")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "test_phone_id")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")

from app.services.srs import get_due_items, record_review, sm2_calculate  # noqa: E402


# ---------------------------------------------------------------------------
# sm2_calculate — pure function tests
# ---------------------------------------------------------------------------


def test_first_successful_repetition():
    ease, interval, reps = sm2_calculate(2.5, 1, 0, 5)
    assert interval == 1
    assert reps == 1
    assert ease > 2.5  # quality 5 increases ease


def test_second_successful_repetition():
    _, interval, reps = sm2_calculate(2.5, 1, 1, 4)
    assert interval == 6
    assert reps == 2


def test_third_repetition_uses_ease_factor():
    ease_factor = 2.5
    prev_interval = 6
    _, interval, reps = sm2_calculate(ease_factor, prev_interval, 2, 4)
    assert interval == round(prev_interval * ease_factor)
    assert reps == 3


def test_failure_resets_repetitions():
    _, interval, reps = sm2_calculate(2.5, 10, 4, 2)
    assert interval == 1
    assert reps == 0


def test_ease_factor_minimum_clamped():
    # Very low quality drives ease down — should not go below 1.3
    ease, _, _ = sm2_calculate(1.3, 1, 0, 0)
    assert ease >= 1.3


def test_ease_factor_increases_on_high_quality():
    ease, _, _ = sm2_calculate(2.5, 1, 0, 5)
    assert ease > 2.5


def test_ease_factor_decreases_on_low_quality():
    ease, _, _ = sm2_calculate(2.5, 1, 0, 3)
    assert ease < 2.5


def test_production_exercise_boosts_ease_increase():
    """Production exercises (translation) should get 1.5x ease increase."""
    ease_no_prod, _, _ = sm2_calculate(2.5, 1, 0, 5)
    ease_prod, _, _ = sm2_calculate(2.5, 1, 0, 5, exercise_type="translation")
    # Both should increase, but production should increase more
    assert ease_prod > ease_no_prod
    # The delta should be 1.5x
    delta_no_prod = ease_no_prod - 2.5
    delta_prod = ease_prod - 2.5
    assert abs(delta_prod - delta_no_prod * 1.5) < 1e-9


def test_production_weight_not_applied_on_negative_delta():
    """Production weight should only apply to positive ease changes."""
    ease_no_prod, _, _ = sm2_calculate(2.5, 1, 0, 3)
    ease_prod, _, _ = sm2_calculate(2.5, 1, 0, 3, exercise_type="translation")
    # Quality 3 produces negative delta, so no weight applied
    assert ease_no_prod == ease_prod


def test_mcq_does_not_get_production_weight():
    """MCQ (recognition) should not get the production weight."""
    ease_mcq, _, _ = sm2_calculate(2.5, 1, 0, 5, exercise_type="mcq")
    ease_none, _, _ = sm2_calculate(2.5, 1, 0, 5)
    assert ease_mcq == ease_none


def test_situational_prompt_gets_production_weight():
    """Situational prompt is also a production type."""
    ease_none, _, _ = sm2_calculate(2.5, 1, 0, 5)
    ease_sit, _, _ = sm2_calculate(2.5, 1, 0, 5, exercise_type="situational_prompt")
    assert ease_sit > ease_none


def test_quality_3_is_success():
    _, interval, reps = sm2_calculate(2.5, 1, 0, 3)
    assert reps == 1  # treated as success


def test_quality_2_is_failure():
    _, interval, reps = sm2_calculate(2.5, 1, 3, 2)
    assert reps == 0
    assert interval == 1


# ---------------------------------------------------------------------------
# get_due_items — async DB tests (mocked session)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_due_items_returns_words():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["hegiddira", "chennagide"]
    mock_db.execute.return_value = mock_result

    words = await get_due_items(mock_db, learner_id=1, limit=10)

    assert words == ["hegiddira", "chennagide"]
    mock_db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_due_items_empty():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    words = await get_due_items(mock_db, learner_id=99)

    assert words == []


# ---------------------------------------------------------------------------
# record_review — async DB tests (mocked session)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_review_updates_fields():
    mock_db = AsyncMock()

    lv = MagicMock()
    lv.ease_factor = 2.5
    lv.interval = 6
    lv.repetitions = 2
    lv.last_exercise_type = None
    mock_db.get.return_value = lv

    today = date.today()
    await record_review(mock_db, learner_vocab_id=1, quality=4)

    # SM-2: repetitions=2, interval=6, ease=2.5, quality=4
    expected_new_ease = 2.5 + (0.1 - (5 - 4) * (0.08 + (5 - 4) * 0.02))
    expected_interval = round(6 * 2.5)
    assert abs(lv.ease_factor - expected_new_ease) < 1e-9
    assert lv.interval == expected_interval
    assert lv.repetitions == 3
    assert lv.due_date == today + timedelta(days=expected_interval)
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_review_stores_exercise_type():
    mock_db = AsyncMock()

    lv = MagicMock()
    lv.ease_factor = 2.5
    lv.interval = 1
    lv.repetitions = 0
    lv.last_exercise_type = None
    mock_db.get.return_value = lv

    await record_review(mock_db, learner_vocab_id=1, quality=5, exercise_type="translation")

    assert lv.last_exercise_type == "translation"


@pytest.mark.asyncio
async def test_record_review_production_boosts_ease():
    mock_db = AsyncMock()

    lv = MagicMock()
    lv.ease_factor = 2.5
    lv.interval = 1
    lv.repetitions = 0
    lv.last_exercise_type = None
    mock_db.get.return_value = lv

    await record_review(mock_db, learner_vocab_id=1, quality=5, exercise_type="translation")

    # Production exercise should get 1.5x positive ease delta
    expected_delta = (0.1 - (5 - 5) * (0.08 + (5 - 5) * 0.02)) * 1.5
    expected_ease = 2.5 + expected_delta
    assert abs(lv.ease_factor - expected_ease) < 1e-9


@pytest.mark.asyncio
async def test_record_review_not_found_raises():
    mock_db = AsyncMock()
    mock_db.get.return_value = None

    with pytest.raises(ValueError, match="not found"):
        await record_review(mock_db, learner_vocab_id=999, quality=4)


@pytest.mark.asyncio
async def test_record_review_failure_resets():
    mock_db = AsyncMock()

    lv = MagicMock()
    lv.ease_factor = 2.5
    lv.interval = 10
    lv.repetitions = 4
    mock_db.get.return_value = lv

    today = date.today()
    await record_review(mock_db, learner_vocab_id=1, quality=1)

    assert lv.repetitions == 0
    assert lv.interval == 1
    assert lv.due_date == today + timedelta(days=1)
