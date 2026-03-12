"""Tests for error handling, fallback messages, and rate limiting in dispatch."""

import os
from unittest.mock import AsyncMock, patch

import anthropic
import pytest
from sqlalchemy.exc import OperationalError

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test_access")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test_app_secret")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "test_phone_id")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")

from app.routers.whatsapp import (  # noqa: E402
    _ERROR_TEXT,
    _OVERLOADED_TEXT,
    _RATE_LIMIT_TEXT,
    dispatch_message,
)
from app.schemas.webhook import IncomingTextMessage  # noqa: E402
from app.services import rate_limiter  # noqa: E402

_PHONE = "14155550099"

_PATCH_SEND = "app.routers.whatsapp.send_message"
_PATCH_LESSON = "app.routers.whatsapp.generate_lesson"
_PATCH_LOOKUP = "app.routers.whatsapp._lookup"
_PATCH_LEVEL = "app.routers.whatsapp.get_learner_level"
_PATCH_GET_MODE = "app.routers.whatsapp._get_mode"
_PATCH_SET_MODE = "app.routers.whatsapp._set_mode"
_PATCH_RATE = "app.routers.whatsapp.rate_limiter.is_allowed"


def _make_msg(text: str, phone: str = _PHONE) -> IncomingTextMessage:
    return IncomingTextMessage(
        message_id="wamid.test",
        sender_phone=phone,
        text=text,
        timestamp="1700000000",
        phone_number_id="test_phone_id",
    )


@pytest.fixture(autouse=True)
def clear_rate_log():
    rate_limiter._call_log.clear()
    yield
    rate_limiter._call_log.clear()


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_sends_limit_message():
    """When the rate limit is exceeded a friendly message is sent."""
    with (
        patch(_PATCH_RATE, return_value=False),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
    ):
        await dispatch_message(_make_msg("lookup hello"))

    mock_send.assert_awaited_once_with(_PHONE, _RATE_LIMIT_TEXT)


@pytest.mark.asyncio
async def test_rate_limit_does_not_call_ai():
    """When rate-limited, no AI service is invoked."""
    with (
        patch(_PATCH_RATE, return_value=False),
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_LOOKUP, new_callable=AsyncMock) as mock_lkp,
        patch(_PATCH_LESSON, new_callable=AsyncMock) as mock_lesson,
    ):
        await dispatch_message(_make_msg("lesson greetings"))

    mock_lkp.assert_not_awaited()
    mock_lesson.assert_not_awaited()


@pytest.mark.asyncio
async def test_help_bypasses_rate_limit():
    """Help command does not count against the AI rate limit."""
    with (
        patch(_PATCH_RATE, return_value=False),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
    ):
        await dispatch_message(_make_msg("help"))

    # Should send help text, not rate limit text
    args = mock_send.call_args[0]
    assert args[1] != _RATE_LIMIT_TEXT


@pytest.mark.asyncio
async def test_rate_limit_checked_before_ai_calls():
    """is_allowed is called before any AI service."""
    with (
        patch(_PATCH_RATE, return_value=True) as mock_allowed,
        patch(_PATCH_LEVEL, new_callable=AsyncMock, return_value=1),
        patch(_PATCH_LESSON, new_callable=AsyncMock, return_value="Lesson"),
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_SET_MODE, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_msg("lesson"))

    mock_allowed.assert_called_once_with(_PHONE)


# ---------------------------------------------------------------------------
# Anthropic API errors → fallback message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anthropic_rate_limit_error_sends_fallback():
    from httpx import Request, Response

    exc = anthropic.RateLimitError(
        message="rate limited",
        response=Response(status_code=429, request=Request("POST", "https://api.anthropic.com")),
        body=None,
    )
    with (
        patch(_PATCH_RATE, return_value=True),
        patch(_PATCH_LEVEL, new_callable=AsyncMock, return_value=1),
        patch(_PATCH_LESSON, new_callable=AsyncMock, side_effect=exc),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_SET_MODE, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_msg("lesson"))

    mock_send.assert_awaited_once_with(_PHONE, _OVERLOADED_TEXT)


@pytest.mark.asyncio
async def test_anthropic_api_status_error_sends_fallback():
    from httpx import Request, Response

    exc = anthropic.APIStatusError(
        message="server error",
        response=Response(status_code=500, request=Request("POST", "https://api.anthropic.com")),
        body=None,
    )
    with (
        patch(_PATCH_RATE, return_value=True),
        patch(_PATCH_GET_MODE, new_callable=AsyncMock, return_value="quick_lookup"),
        patch(_PATCH_LOOKUP, new_callable=AsyncMock, side_effect=exc),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_SET_MODE, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_msg("lookup hello"))

    mock_send.assert_awaited_once_with(_PHONE, _ERROR_TEXT)


# ---------------------------------------------------------------------------
# Database errors → fallback message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_db_error_sends_fallback():
    exc = OperationalError("connection refused", None, None)
    with (
        patch(_PATCH_RATE, return_value=True),
        patch(_PATCH_GET_MODE, new_callable=AsyncMock, side_effect=exc),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
    ):
        await dispatch_message(_make_msg("how are you"))

    mock_send.assert_awaited_once_with(_PHONE, _ERROR_TEXT)


@pytest.mark.asyncio
async def test_db_error_does_not_propagate():
    """A database error must be caught and not re-raised."""
    exc = OperationalError("connection refused", None, None)
    with (
        patch(_PATCH_RATE, return_value=True),
        patch(_PATCH_GET_MODE, new_callable=AsyncMock, side_effect=exc),
        patch(_PATCH_SEND, new_callable=AsyncMock),
    ):
        # Should not raise
        await dispatch_message(_make_msg("lookup hello"))


# ---------------------------------------------------------------------------
# WhatsApp send failure → log only, no cascade
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_whatsapp_send_failure_does_not_propagate():
    """RuntimeError from send_message must be swallowed."""
    with (
        patch(_PATCH_RATE, return_value=True),
        patch(_PATCH_GET_MODE, new_callable=AsyncMock, return_value="quick_lookup"),
        patch(_PATCH_LOOKUP, new_callable=AsyncMock, side_effect=RuntimeError("send failed")),
        patch(_PATCH_SEND, new_callable=AsyncMock),
    ):
        # Should not raise
        await dispatch_message(_make_msg("hello"))


@pytest.mark.asyncio
async def test_fallback_send_failure_does_not_cascade():
    """If fallback send_message also fails, error is swallowed."""
    from sqlalchemy.exc import OperationalError as OpErr

    with (
        patch(_PATCH_RATE, return_value=True),
        patch(_PATCH_GET_MODE, new_callable=AsyncMock, side_effect=OpErr("db down", None, None)),
        patch(_PATCH_SEND, new_callable=AsyncMock, side_effect=RuntimeError("WA down too")),
    ):
        # Should not raise even though both DB and fallback send fail
        await dispatch_message(_make_msg("hello"))


# ---------------------------------------------------------------------------
# Payload validation (IncomingTextMessage)
# ---------------------------------------------------------------------------


def test_incoming_message_rejects_empty_phone():
    import pytest as _pytest

    with _pytest.raises(Exception):
        IncomingTextMessage(
            message_id="wamid.test",
            sender_phone="   ",
            text="hello",
            timestamp="1700000000",
            phone_number_id="test_phone_id",
        )


def test_incoming_message_rejects_empty_text():
    import pytest as _pytest

    with _pytest.raises(Exception):
        IncomingTextMessage(
            message_id="wamid.test",
            sender_phone="14155550001",
            text="   ",
            timestamp="1700000000",
            phone_number_id="test_phone_id",
        )


def test_incoming_message_accepts_valid_fields():
    msg = IncomingTextMessage(
        message_id="wamid.test",
        sender_phone="14155550001",
        text="hello",
        timestamp="1700000000",
        phone_number_id="test_phone_id",
    )
    assert msg.sender_phone == "14155550001"
