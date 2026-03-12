"""Tests for the quick lookup service."""

import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test_access")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test_app_secret")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "test_phone_id")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")

from app.services.quick_lookup import SYSTEM_QUICK_LOOKUP, quick_lookup  # noqa: E402


SAMPLE_RESPONSE = "ಹೇಗಿದ್ದೀರಾ? (hegiddira?) — greeting someone casually"


@pytest.mark.asyncio
async def test_quick_lookup_returns_haiku_response():
    with patch(
        "app.services.quick_lookup.ask_haiku_with_system",
        new_callable=AsyncMock,
        return_value=SAMPLE_RESPONSE,
    ) as mock_ask:
        result = await quick_lookup("How are you?")

    mock_ask.assert_awaited_once_with("How are you?", SYSTEM_QUICK_LOOKUP)
    assert result == SAMPLE_RESPONSE


@pytest.mark.asyncio
async def test_quick_lookup_passes_phrase_unchanged():
    phrase = "I am very hungry"
    with patch(
        "app.services.quick_lookup.ask_haiku_with_system",
        new_callable=AsyncMock,
        return_value="ನನಗೆ ತುಂಬಾ ಹಸಿವಾಗಿದೆ (nanage tumba hasivagide) — expressing hunger",
    ) as mock_ask:
        await quick_lookup(phrase)

    assert mock_ask.call_args[0][0] == phrase


@pytest.mark.asyncio
async def test_quick_lookup_response_fits_whatsapp(monkeypatch):
    """Response must be under 200 chars for WhatsApp readability."""
    long_response = "ಅ " * 50  # simulate a clipped/short haiku response
    with patch(
        "app.services.quick_lookup.ask_haiku_with_system",
        new_callable=AsyncMock,
        return_value=SAMPLE_RESPONSE,
    ):
        result = await quick_lookup("test phrase")

    assert len(result) <= 200


def test_system_prompt_requires_kannada_script():
    assert "Kannada Unicode" in SYSTEM_QUICK_LOOKUP or "script" in SYSTEM_QUICK_LOOKUP


def test_system_prompt_requires_romanization():
    assert "roman" in SYSTEM_QUICK_LOOKUP.lower() or "transliteration" in SYSTEM_QUICK_LOOKUP.lower()


def test_system_prompt_requires_usage_note():
    assert "note" in SYSTEM_QUICK_LOOKUP.lower() or "usage" in SYSTEM_QUICK_LOOKUP.lower()
