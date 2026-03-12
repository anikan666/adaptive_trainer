"""Tests for the learner level tracker."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test_access")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test_app_secret")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "test_phone_id")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")

from app.services.level_tracker import (  # noqa: E402
    SESSIONS_TO_LEVEL_DOWN,
    SESSIONS_TO_LEVEL_UP,
    _compute_new_level,
    get_learner_level,
    update_level_after_session,
)


# ---------------------------------------------------------------------------
# _compute_new_level — pure function tests
# ---------------------------------------------------------------------------


def test_no_change_when_insufficient_history():
    assert _compute_new_level(3, [0.9, 0.9]) == 3  # fewer than SESSIONS_TO_LEVEL_UP


def test_level_up_after_consecutive_high_scores():
    scores = [0.9] * SESSIONS_TO_LEVEL_UP
    assert _compute_new_level(2, scores) == 3


def test_level_up_capped_at_5():
    scores = [0.9] * SESSIONS_TO_LEVEL_UP
    assert _compute_new_level(5, scores) == 5


def test_level_down_after_consecutive_low_scores():
    scores = [0.3] * SESSIONS_TO_LEVEL_DOWN
    assert _compute_new_level(3, scores) == 2


def test_level_down_capped_at_1():
    scores = [0.3] * SESSIONS_TO_LEVEL_DOWN
    assert _compute_new_level(1, scores) == 1


def test_mixed_scores_no_level_change():
    # Last N not all above threshold, last M not all below threshold
    scores = [0.9, 0.3, 0.9]
    assert _compute_new_level(3, scores) == 3


def test_level_up_uses_only_last_n_scores():
    # Older bad session followed by N good ones → should level up
    scores = [0.2] + [0.9] * SESSIONS_TO_LEVEL_UP
    assert _compute_new_level(2, scores) == 3


def test_level_down_uses_only_last_m_scores():
    # Older good session followed by M bad ones → should level down
    scores = [0.9] + [0.3] * SESSIONS_TO_LEVEL_DOWN
    assert _compute_new_level(3, scores) == 2


def test_score_exactly_at_threshold_does_not_trigger_level_up():
    # Threshold is strictly > 0.8; 0.8 itself must not trigger
    scores = [0.8] * SESSIONS_TO_LEVEL_UP
    assert _compute_new_level(2, scores) == 2


def test_score_exactly_at_threshold_does_not_trigger_level_down():
    # Threshold is strictly < 0.4; 0.4 itself must not trigger
    scores = [0.4] * SESSIONS_TO_LEVEL_DOWN
    assert _compute_new_level(3, scores) == 3


# ---------------------------------------------------------------------------
# get_learner_level — async tests (mocked DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_learner_level_returns_level():
    learner = MagicMock()
    learner.level = 3

    with patch(
        "app.services.level_tracker.AsyncSessionLocal"
    ) as mock_session_cls:
        mock_db = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_db

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = learner
        mock_db.execute.return_value = mock_result

        level = await get_learner_level("+15551234567")

    assert level == 3


@pytest.mark.asyncio
async def test_get_learner_level_raises_for_unknown_phone():
    with patch(
        "app.services.level_tracker.AsyncSessionLocal"
    ) as mock_session_cls:
        mock_db = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_db

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="No learner found"):
            await get_learner_level("+15559999999")


# ---------------------------------------------------------------------------
# update_level_after_session — async tests (mocked DB)
# ---------------------------------------------------------------------------


def _make_db_mock(learner_level: int, recent_scores: list[float]) -> AsyncMock:
    """Build a mock AsyncSession for update_level_after_session tests."""
    learner = MagicMock()
    learner.id = 1
    learner.level = learner_level

    mock_db = AsyncMock()

    learner_result = MagicMock()
    learner_result.scalar_one_or_none.return_value = learner

    scores_result = MagicMock()
    scores_result.scalars.return_value.all.return_value = list(reversed(recent_scores))

    mock_db.execute.side_effect = [learner_result, scores_result]

    return mock_db, learner


@pytest.mark.asyncio
async def test_update_level_raises_on_empty_scores():
    with pytest.raises(ValueError, match="must not be empty"):
        await update_level_after_session("+15551234567", [])


@pytest.mark.asyncio
async def test_update_level_no_change_mixed_history():
    recent = [0.9, 0.3, 0.9]  # no consistent pattern
    mock_db, learner = _make_db_mock(learner_level=3, recent_scores=recent)

    with patch(
        "app.services.level_tracker.AsyncSessionLocal"
    ) as mock_session_cls:
        mock_session_cls.return_value.__aenter__.return_value = mock_db

        new_level = await update_level_after_session("+15551234567", [0.5])

    assert new_level == 3
    assert learner.level == 3
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_level_promotes_on_high_scores():
    # Recent window already has N-1 high scores; new session is also high
    recent = [0.9] * SESSIONS_TO_LEVEL_UP
    mock_db, learner = _make_db_mock(learner_level=2, recent_scores=recent)

    with patch(
        "app.services.level_tracker.AsyncSessionLocal"
    ) as mock_session_cls:
        mock_session_cls.return_value.__aenter__.return_value = mock_db

        new_level = await update_level_after_session("+15551234567", [0.9, 0.95])

    assert new_level == 3
    assert learner.level == 3


@pytest.mark.asyncio
async def test_update_level_demotes_on_low_scores():
    recent = [0.3] * SESSIONS_TO_LEVEL_DOWN
    mock_db, learner = _make_db_mock(learner_level=3, recent_scores=recent)

    with patch(
        "app.services.level_tracker.AsyncSessionLocal"
    ) as mock_session_cls:
        mock_session_cls.return_value.__aenter__.return_value = mock_db

        new_level = await update_level_after_session("+15551234567", [0.2])

    assert new_level == 2
    assert learner.level == 2


@pytest.mark.asyncio
async def test_update_level_raises_for_unknown_learner():
    with patch(
        "app.services.level_tracker.AsyncSessionLocal"
    ) as mock_session_cls:
        mock_db = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_db

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="No learner found"):
            await update_level_after_session("+15559999999", [0.5])
