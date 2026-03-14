"""Tests for the progress summary service."""

import os
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test_access")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test_app_secret")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "test_phone_id")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")

from app.models.learner import Learner  # noqa: E402
from app.services.progress import (  # noqa: E402
    _NOT_ONBOARDED_TEXT,
    _NO_SESSIONS_TEXT,
    get_progress_summary,
)

_PHONE = "14155550001"


def _make_learner(level: int = 2, name: str | None = None, current_ring: int = 1, current_streak: int = 0) -> Learner:
    learner = MagicMock(spec=Learner)
    learner.id = 42
    learner.level = level
    learner.current_ring = current_ring
    learner.name = name
    learner.current_streak = current_streak
    return learner


def _patch_db(learner, session_row=(0, None), vocab_row=(0, 0)):
    """Build nested AsyncSessionLocal context manager mocks."""

    async def _execute_side_effect(query):
        # Distinguish queries by inspecting — simplest approach: sequential call tracking
        raise NotImplementedError("Use _patch_db_sequential for multi-query tests")

    # We'll set up the mock differently per test using patch directly.
    pass


@pytest.mark.asyncio
async def test_not_onboarded_returns_friendly_message():
    """Returns the not-onboarded message when learner doesn't exist."""
    mock_scalar = MagicMock()
    mock_scalar.scalar_one_or_none.return_value = None

    mock_execute = AsyncMock(return_value=mock_scalar)
    mock_db = AsyncMock()
    mock_db.execute = mock_execute
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.progress.AsyncSessionLocal", return_value=mock_db):
        result = await get_progress_summary(_PHONE)

    assert result == _NOT_ONBOARDED_TEXT


@pytest.mark.asyncio
async def test_no_sessions_returns_nudge():
    """Returns no-sessions nudge when learner exists but has zero sessions."""
    learner = _make_learner(level=3, current_ring=2)

    # Call 1: select Learner
    mock_learner_row = MagicMock()
    mock_learner_row.scalar_one_or_none.return_value = learner

    # Call 2: session stats → (0, None)
    mock_session_row = MagicMock()
    mock_session_row.one.return_value = (0, None)

    db1 = AsyncMock()
    db1.execute = AsyncMock(return_value=mock_learner_row)
    db1.__aenter__ = AsyncMock(return_value=db1)
    db1.__aexit__ = AsyncMock(return_value=False)

    db2 = AsyncMock()
    db2.execute = AsyncMock(return_value=mock_session_row)
    db2.__aenter__ = AsyncMock(return_value=db2)
    db2.__aexit__ = AsyncMock(return_value=False)

    call_count = 0

    def _session_factory():
        nonlocal call_count
        call_count += 1
        return db1 if call_count == 1 else db2

    with patch("app.services.progress.AsyncSessionLocal", side_effect=_session_factory):
        result = await get_progress_summary(_PHONE)

    assert "Ring: 2/4" in result
    assert "session" in result.lower()


@pytest.mark.asyncio
async def test_full_progress_summary():
    """Returns full stats when learner has sessions and vocabulary."""
    learner = _make_learner(level=2)

    mock_learner_row = MagicMock()
    mock_learner_row.scalar_one_or_none.return_value = learner

    mock_session_row = MagicMock()
    mock_session_row.one.return_value = (12, 0.78)

    mock_vocab_row = MagicMock()
    mock_vocab_row.one.return_value = (47, 5)

    dbs = []
    for execute_mock in [
        AsyncMock(return_value=mock_learner_row),
        AsyncMock(return_value=mock_session_row),
        AsyncMock(return_value=mock_vocab_row),
    ]:
        db = AsyncMock()
        db.execute = execute_mock
        db.__aenter__ = AsyncMock(return_value=db)
        db.__aexit__ = AsyncMock(return_value=False)
        dbs.append(db)

    idx = 0

    def _factory():
        nonlocal idx
        db = dbs[idx]
        idx += 1
        return db

    with patch("app.services.progress.AsyncSessionLocal", side_effect=_factory):
        result = await get_progress_summary(_PHONE)

    assert "📊 Your Progress" in result
    assert "Ring: 1/4" in result
    assert "Sessions completed: 12" in result
    assert "Average score: 78%" in result
    assert "Vocabulary learned: 47 words" in result
    assert "Due for review: 5 words" in result


@pytest.mark.asyncio
async def test_progress_summary_includes_name_greeting():
    """Includes personalized greeting when learner has a name."""
    learner = _make_learner(level=2, name="Priya")

    mock_learner_row = MagicMock()
    mock_learner_row.scalar_one_or_none.return_value = learner

    mock_session_row = MagicMock()
    mock_session_row.one.return_value = (5, 0.90)

    mock_vocab_row = MagicMock()
    mock_vocab_row.one.return_value = (20, 3)

    dbs = []
    for execute_mock in [
        AsyncMock(return_value=mock_learner_row),
        AsyncMock(return_value=mock_session_row),
        AsyncMock(return_value=mock_vocab_row),
    ]:
        db = AsyncMock()
        db.execute = execute_mock
        db.__aenter__ = AsyncMock(return_value=db)
        db.__aexit__ = AsyncMock(return_value=False)
        dbs.append(db)

    idx = 0

    def _factory():
        nonlocal idx
        db = dbs[idx]
        idx += 1
        return db

    with patch("app.services.progress.AsyncSessionLocal", side_effect=_factory):
        result = await get_progress_summary(_PHONE)

    assert "Hi Priya!" in result
    assert "📊 Your Progress" in result
