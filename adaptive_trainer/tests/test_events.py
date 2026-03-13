"""Tests for message deduplication in emit_message_event."""

import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test_access")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test_app_secret")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "test_phone_id")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")

from app.schemas.webhook import IncomingTextMessage  # noqa: E402
from app.services import events  # noqa: E402


def _make_message(message_id: str = "wamid.abc123", phone: str = "14155550001") -> IncomingTextMessage:
    return IncomingTextMessage(
        message_id=message_id,
        sender_phone=phone,
        text="hello",
        timestamp="1700000000",
        phone_number_id="test_phone_id",
    )


@pytest.fixture(autouse=True)
def clear_seen_ids():
    """Reset the dedup cache before each test."""
    events._seen_ids.clear()
    yield
    events._seen_ids.clear()


@pytest.mark.asyncio
async def test_first_message_is_dispatched():
    with (
        patch("app.services.events.needs_onboarding", new_callable=AsyncMock, return_value=False),
        patch("app.services.events.dispatch_message", new_callable=AsyncMock) as mock_dispatch,
    ):
        await events.emit_message_event(_make_message("wamid.001"))

    mock_dispatch.assert_awaited_once()


@pytest.mark.asyncio
async def test_duplicate_message_id_is_skipped():
    with (
        patch("app.services.events.needs_onboarding", new_callable=AsyncMock, return_value=False),
        patch("app.services.events.dispatch_message", new_callable=AsyncMock) as mock_dispatch,
    ):
        await events.emit_message_event(_make_message("wamid.dup"))
        await events.emit_message_event(_make_message("wamid.dup"))

    mock_dispatch.assert_awaited_once()


@pytest.mark.asyncio
async def test_different_message_ids_are_both_dispatched():
    with (
        patch("app.services.events.needs_onboarding", new_callable=AsyncMock, return_value=False),
        patch("app.services.events.dispatch_message", new_callable=AsyncMock) as mock_dispatch,
    ):
        await events.emit_message_event(_make_message("wamid.001"))
        await events.emit_message_event(_make_message("wamid.002"))

    assert mock_dispatch.await_count == 2


@pytest.mark.asyncio
async def test_duplicate_skipped_before_onboarding_check():
    """Duplicate check happens before onboarding, so no DB hit on retry."""
    with (
        patch("app.services.events.needs_onboarding", new_callable=AsyncMock, return_value=False) as mock_onboard,
        patch("app.services.events.dispatch_message", new_callable=AsyncMock),
    ):
        await events.emit_message_event(_make_message("wamid.dup2"))
        await events.emit_message_event(_make_message("wamid.dup2"))

    mock_onboard.assert_awaited_once()
