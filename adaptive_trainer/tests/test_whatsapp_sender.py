"""Tests for the WhatsApp message sender service."""

import pytest
import respx
import httpx

from unittest.mock import patch


# Patch settings before importing the module under test
_MOCK_SETTINGS_ATTRS = {
    "whatsapp_access_token": "test_token",
    "whatsapp_phone_number_id": "123456789",
}


@pytest.fixture(autouse=True)
def mock_settings():
    with patch("app.services.whatsapp_sender.settings") as m:
        m.whatsapp_access_token = _MOCK_SETTINGS_ATTRS["whatsapp_access_token"]
        m.whatsapp_phone_number_id = _MOCK_SETTINGS_ATTRS["whatsapp_phone_number_id"]
        yield m


MESSAGES_URL = "https://graph.facebook.com/v18.0/123456789/messages"


@pytest.mark.asyncio
@respx.mock
async def test_send_message_success():
    respx.post(MESSAGES_URL).mock(
        return_value=httpx.Response(
            200,
            json={"messages": [{"id": "wamid.abc123"}]},
        )
    )

    from app.services.whatsapp_sender import send_message

    result = await send_message("15551234567", "Hello!")
    assert result["messages"][0]["id"] == "wamid.abc123"


@pytest.mark.asyncio
@respx.mock
async def test_send_message_retries_on_rate_limit():
    call_count = 0

    def rate_limit_then_success(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={})
        return httpx.Response(200, json={"messages": [{"id": "wamid.xyz"}]})

    respx.post(MESSAGES_URL).mock(side_effect=rate_limit_then_success)

    from app.services.whatsapp_sender import send_message

    result = await send_message("15559876543", "Retry test")
    assert result["messages"][0]["id"] == "wamid.xyz"
    assert call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_send_message_raises_on_client_error():
    respx.post(MESSAGES_URL).mock(
        return_value=httpx.Response(400, json={"error": {"message": "Bad request"}})
    )

    from app.services.whatsapp_sender import send_message

    with pytest.raises(httpx.HTTPStatusError):
        await send_message("15550000000", "Bad message")
