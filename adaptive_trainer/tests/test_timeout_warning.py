"""Tests for the session timeout warning background task."""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test_access")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test_app_secret")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "test_phone_id")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")

from app.models.conversation import Conversation, ConversationMode  # noqa: E402
from app.services.timeout_warning import (  # noqa: E402
    _TIMEOUT_WARNING_TEXT,
    _check_and_warn,
)

PHONE = "14155550001"


def _make_convo(
    phone: str = PHONE,
    mode: ConversationMode = ConversationMode.lesson,
    updated_minutes_ago: int = 26,
    lesson_context: dict | None = None,
) -> MagicMock:
    convo = MagicMock(spec=Conversation)
    convo.phone_number = phone
    convo.mode = mode
    convo.updated_at = datetime.now(timezone.utc) - timedelta(minutes=updated_minutes_ago)
    convo.lesson_context = lesson_context if lesson_context is not None else {"exercises": []}
    return convo


def _mock_db_with_convos(convos: list):
    """Create a mock AsyncSessionLocal that returns the given conversations."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = convos

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    mock_session_cls = MagicMock()
    mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_session_cls, mock_db


# ---------------------------------------------------------------------------
# _check_and_warn
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_warns_session_at_26_minutes():
    convo = _make_convo(updated_minutes_ago=26)
    mock_session_cls, mock_db = _mock_db_with_convos([convo])

    with (
        patch("app.services.timeout_warning.AsyncSessionLocal", mock_session_cls),
        patch("app.services.timeout_warning.send_message", new_callable=AsyncMock) as mock_send,
    ):
        count = await _check_and_warn()

    assert count == 1
    mock_send.assert_awaited_once_with(PHONE, _TIMEOUT_WARNING_TEXT)
    mock_db.commit.assert_awaited_once()
    # Verify the warning flag was set
    assert convo.lesson_context["timeout_warning_sent"] is True


@pytest.mark.asyncio
async def test_no_warning_before_25_minutes():
    convo = _make_convo(updated_minutes_ago=20)
    mock_session_cls, mock_db = _mock_db_with_convos([convo])

    with (
        patch("app.services.timeout_warning.AsyncSessionLocal", mock_session_cls),
        patch("app.services.timeout_warning.send_message", new_callable=AsyncMock) as mock_send,
    ):
        count = await _check_and_warn()

    assert count == 0
    mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_warning_after_30_minutes():
    """Sessions past 30 minutes are already expired — don't warn."""
    convo = _make_convo(updated_minutes_ago=35)
    mock_session_cls, mock_db = _mock_db_with_convos([convo])

    with (
        patch("app.services.timeout_warning.AsyncSessionLocal", mock_session_cls),
        patch("app.services.timeout_warning.send_message", new_callable=AsyncMock) as mock_send,
    ):
        count = await _check_and_warn()

    assert count == 0
    mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_duplicate_warning():
    """If timeout_warning_sent is already True, don't warn again."""
    convo = _make_convo(
        updated_minutes_ago=26,
        lesson_context={"exercises": [], "timeout_warning_sent": True},
    )
    mock_session_cls, mock_db = _mock_db_with_convos([convo])

    with (
        patch("app.services.timeout_warning.AsyncSessionLocal", mock_session_cls),
        patch("app.services.timeout_warning.send_message", new_callable=AsyncMock) as mock_send,
    ):
        count = await _check_and_warn()

    assert count == 0
    mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_quick_lookup_mode_not_warned():
    """quick_lookup mode is not an active session — don't warn."""
    convo = _make_convo(mode=ConversationMode.quick_lookup, updated_minutes_ago=26)
    mock_session_cls, mock_db = _mock_db_with_convos([convo])

    with (
        patch("app.services.timeout_warning.AsyncSessionLocal", mock_session_cls),
        patch("app.services.timeout_warning.send_message", new_callable=AsyncMock) as mock_send,
    ):
        count = await _check_and_warn()

    assert count == 0
    mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_warns_review_mode():
    convo = _make_convo(mode=ConversationMode.review, updated_minutes_ago=27)
    mock_session_cls, mock_db = _mock_db_with_convos([convo])

    with (
        patch("app.services.timeout_warning.AsyncSessionLocal", mock_session_cls),
        patch("app.services.timeout_warning.send_message", new_callable=AsyncMock) as mock_send,
    ):
        count = await _check_and_warn()

    assert count == 1
    mock_send.assert_awaited_once_with(convo.phone_number, _TIMEOUT_WARNING_TEXT)


@pytest.mark.asyncio
async def test_warns_gateway_mode():
    convo = _make_convo(mode=ConversationMode.gateway_test, updated_minutes_ago=28)
    mock_session_cls, mock_db = _mock_db_with_convos([convo])

    with (
        patch("app.services.timeout_warning.AsyncSessionLocal", mock_session_cls),
        patch("app.services.timeout_warning.send_message", new_callable=AsyncMock) as mock_send,
    ):
        count = await _check_and_warn()

    assert count == 1
    mock_send.assert_awaited_once()


@pytest.mark.asyncio
async def test_multiple_sessions_warns_eligible_only():
    """Only sessions in the 25-30 minute window without prior warning get warned."""
    eligible = _make_convo(phone="111", updated_minutes_ago=26)
    too_fresh = _make_convo(phone="222", updated_minutes_ago=10)
    already_warned = _make_convo(
        phone="333",
        updated_minutes_ago=27,
        lesson_context={"timeout_warning_sent": True},
    )
    expired = _make_convo(phone="444", updated_minutes_ago=35)

    mock_session_cls, mock_db = _mock_db_with_convos(
        [eligible, too_fresh, already_warned, expired]
    )

    with (
        patch("app.services.timeout_warning.AsyncSessionLocal", mock_session_cls),
        patch("app.services.timeout_warning.send_message", new_callable=AsyncMock) as mock_send,
    ):
        count = await _check_and_warn()

    assert count == 1
    mock_send.assert_awaited_once_with("111", _TIMEOUT_WARNING_TEXT)


@pytest.mark.asyncio
async def test_send_failure_does_not_crash():
    """If sending the warning fails, continue checking other sessions."""
    convo = _make_convo(updated_minutes_ago=26)
    mock_session_cls, mock_db = _mock_db_with_convos([convo])

    with (
        patch("app.services.timeout_warning.AsyncSessionLocal", mock_session_cls),
        patch(
            "app.services.timeout_warning.send_message",
            new_callable=AsyncMock,
            side_effect=RuntimeError("WhatsApp down"),
        ) as mock_send,
    ):
        count = await _check_and_warn()

    assert count == 0
    mock_send.assert_awaited_once()


@pytest.mark.asyncio
async def test_handles_naive_updated_at():
    """updated_at without tzinfo is treated as UTC."""
    convo = _make_convo(updated_minutes_ago=26)
    # Make updated_at naive (no timezone)
    convo.updated_at = convo.updated_at.replace(tzinfo=None)
    mock_session_cls, mock_db = _mock_db_with_convos([convo])

    with (
        patch("app.services.timeout_warning.AsyncSessionLocal", mock_session_cls),
        patch("app.services.timeout_warning.send_message", new_callable=AsyncMock) as mock_send,
    ):
        count = await _check_and_warn()

    assert count == 1
    mock_send.assert_awaited_once()


@pytest.mark.asyncio
async def test_null_lesson_context_gets_warning_flag():
    """If lesson_context is None, it should be initialized with the flag."""
    convo = _make_convo(updated_minutes_ago=26, lesson_context=None)
    # Override the spec to allow setting lesson_context to None
    convo.lesson_context = None
    mock_session_cls, mock_db = _mock_db_with_convos([convo])

    with (
        patch("app.services.timeout_warning.AsyncSessionLocal", mock_session_cls),
        patch("app.services.timeout_warning.send_message", new_callable=AsyncMock) as mock_send,
    ):
        count = await _check_and_warn()

    assert count == 1
    mock_send.assert_awaited_once()
    assert convo.lesson_context["timeout_warning_sent"] is True
