"""Tests for the topics suggestion service and dispatcher integration."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test_access")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test_app_secret")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "test_phone_id")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")

from app.models.learner import Learner  # noqa: E402
from app.routers.whatsapp import dispatch_message  # noqa: E402
from app.schemas.webhook import IncomingTextMessage  # noqa: E402
from app.services.topics import (  # noqa: E402
    _NOT_ONBOARDED_TEXT,
    _SUGGESTIONS_COUNT,
    _TOPIC_POOLS,
    _bracket_for_level,
    get_topic_suggestions,
)

_PATCH_SEND = "app.routers.whatsapp.send_message"
_PATCH_GET_TOPICS = "app.routers.whatsapp.get_topic_suggestions"
_PATCH_EXPIRE = "app.routers.whatsapp._expire_stale_session"


def _make_message(text: str, phone: str = "14155550001") -> IncomingTextMessage:
    return IncomingTextMessage(
        message_id="wamid.test",
        sender_phone=phone,
        text=text,
        timestamp="1700000000",
        phone_number_id="test_phone_id",
    )


def _make_learner(level: int) -> Learner:
    learner = MagicMock(spec=Learner)
    learner.level = level
    return learner


# ---------------------------------------------------------------------------
# _bracket_for_level unit tests
# ---------------------------------------------------------------------------


def test_bracket_level_1():
    assert _bracket_for_level(1) == "beginner"


def test_bracket_level_2():
    assert _bracket_for_level(2) == "beginner"


def test_bracket_level_3():
    assert _bracket_for_level(3) == "intermediate"


def test_bracket_level_4():
    assert _bracket_for_level(4) == "intermediate"


def test_bracket_level_5():
    assert _bracket_for_level(5) == "advanced"


# ---------------------------------------------------------------------------
# get_topic_suggestions unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_topics_not_onboarded():
    """Returns not-onboarded text when learner doesn't exist."""

    class FakeResult:
        def scalar_one_or_none(self):
            return None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=FakeResult())

    with patch("app.services.topics.AsyncSessionLocal") as mock_session:
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await get_topic_suggestions("14155550001")

    assert result == _NOT_ONBOARDED_TEXT


@pytest.mark.asyncio
async def test_topics_beginner_level():
    """Returns beginner topics for level 1 learner."""
    learner = _make_learner(1)

    class FakeResult:
        def scalar_one_or_none(self):
            return learner

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=FakeResult())

    with patch("app.services.topics.AsyncSessionLocal") as mock_session:
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await get_topic_suggestions("14155550001")

    assert "beginner" in result
    assert "lesson <topic>" in result


@pytest.mark.asyncio
async def test_topics_advanced_level():
    """Returns advanced topics for level 5 learner."""
    learner = _make_learner(5)

    class FakeResult:
        def scalar_one_or_none(self):
            return learner

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=FakeResult())

    with patch("app.services.topics.AsyncSessionLocal") as mock_session:
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await get_topic_suggestions("14155550001")

    assert "advanced" in result


@pytest.mark.asyncio
async def test_topics_returns_correct_count():
    """Returns the expected number of topic suggestions."""
    learner = _make_learner(3)

    class FakeResult:
        def scalar_one_or_none(self):
            return learner

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=FakeResult())

    with patch("app.services.topics.AsyncSessionLocal") as mock_session:
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await get_topic_suggestions("14155550001")

    # Count numbered lines (1. through 6.)
    numbered_lines = [l for l in result.split("\n") if l and l[0].isdigit()]
    assert len(numbered_lines) == _SUGGESTIONS_COUNT


# ---------------------------------------------------------------------------
# Topic pools validation
# ---------------------------------------------------------------------------


def test_all_brackets_have_enough_topics():
    """Each bracket has at least _SUGGESTIONS_COUNT topics."""
    for bracket, pool in _TOPIC_POOLS.items():
        assert len(pool) >= _SUGGESTIONS_COUNT, f"{bracket} has too few topics"


# ---------------------------------------------------------------------------
# Dispatcher integration: topics keyword
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_topics_keyword_calls_get_topic_suggestions():
    with (
        patch(_PATCH_EXPIRE, new_callable=AsyncMock),
        patch(_PATCH_GET_TOPICS, new_callable=AsyncMock, return_value="topics list") as mock_topics,
        patch(_PATCH_SEND, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_message("topics"))

    mock_topics.assert_awaited_once_with("14155550001")


@pytest.mark.asyncio
async def test_topics_sends_suggestions():
    suggestions = "Topics for your level (beginner):\n1. *greetings* — hello"
    with (
        patch(_PATCH_EXPIRE, new_callable=AsyncMock),
        patch(_PATCH_GET_TOPICS, new_callable=AsyncMock, return_value=suggestions),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
    ):
        await dispatch_message(_make_message("topics"))

    mock_send.assert_awaited_once_with("14155550001", suggestions)


@pytest.mark.asyncio
async def test_topics_case_insensitive():
    with (
        patch(_PATCH_EXPIRE, new_callable=AsyncMock),
        patch(_PATCH_GET_TOPICS, new_callable=AsyncMock, return_value="topics"),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
    ):
        await dispatch_message(_make_message("TOPICS"))

    mock_send.assert_awaited_once()


@pytest.mark.asyncio
async def test_topics_does_not_hit_rate_limiter():
    """topics bypasses the rate limiter (no AI call)."""
    with (
        patch(_PATCH_EXPIRE, new_callable=AsyncMock),
        patch(_PATCH_GET_TOPICS, new_callable=AsyncMock, return_value="topics"),
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch("app.routers.whatsapp.rate_limiter.is_allowed") as mock_rl,
    ):
        await dispatch_message(_make_message("topics"))

    mock_rl.assert_not_called()


@pytest.mark.asyncio
async def test_topics_does_not_query_mode():
    """topics short-circuits mode dispatch."""
    with (
        patch(_PATCH_EXPIRE, new_callable=AsyncMock),
        patch(_PATCH_GET_TOPICS, new_callable=AsyncMock, return_value="topics"),
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch("app.routers.whatsapp._get_convo_state", new_callable=AsyncMock) as mock_state,
    ):
        await dispatch_message(_make_message("topics"))

    mock_state.assert_not_awaited()
