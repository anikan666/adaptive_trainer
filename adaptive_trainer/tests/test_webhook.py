import hashlib
import hmac
import json
import os
from unittest.mock import AsyncMock, patch

import pytest

# Set required env vars before any app imports trigger config validation
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test_access")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test_app_secret")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "test_phone_id")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)

VERIFY_TOKEN = "test_verify_token"
APP_SECRET = "test_app_secret"


def _make_signature(payload: bytes, secret: str = APP_SECRET) -> str:
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _text_payload(
    sender: str = "1234567890",
    text: str = "Hello",
    message_id: str = "wamid.abc123",
    phone_number_id: str = "9876543210",
) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+1234",
                                "phone_number_id": phone_number_id,
                            },
                            "contacts": [{"profile": {"name": "Test"}, "wa_id": sender}],
                            "messages": [
                                {
                                    "from": sender,
                                    "id": message_id,
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# GET /webhook  (verification handshake)
# ---------------------------------------------------------------------------


class TestVerifyWebhook:
    def test_valid_token_returns_challenge(self):
        resp = client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": VERIFY_TOKEN,
                "hub.challenge": "42",
            },
        )
        assert resp.status_code == 200
        assert resp.json() == 42

    def test_wrong_token_returns_403(self):
        resp = client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong",
                "hub.challenge": "42",
            },
        )
        assert resp.status_code == 403

    def test_wrong_mode_returns_403(self):
        resp = client.get(
            "/webhook",
            params={
                "hub.mode": "unsubscribe",
                "hub.verify_token": VERIFY_TOKEN,
                "hub.challenge": "42",
            },
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /webhook  (receive messages)
# ---------------------------------------------------------------------------


class TestReceiveMessage:
    def _post(self, payload: dict, secret: str = APP_SECRET) -> object:
        body = json.dumps(payload).encode()
        return client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _make_signature(body, secret),
            },
        )

    def test_valid_text_message_returns_200(self):
        with patch("app.routers.webhook.emit_message_event", new_callable=AsyncMock) as mock_emit:
            resp = self._post(_text_payload())
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        mock_emit.assert_awaited_once()

    def test_emit_called_with_correct_fields(self):
        payload = _text_payload(
            sender="447700900123",
            text="Namaskara",
            message_id="wamid.xyz",
            phone_number_id="111222333",
        )
        with patch("app.routers.webhook.emit_message_event", new_callable=AsyncMock) as mock_emit:
            self._post(payload)
        call_arg = mock_emit.call_args[0][0]
        assert call_arg.sender_phone == "447700900123"
        assert call_arg.text == "Namaskara"
        assert call_arg.message_id == "wamid.xyz"
        assert call_arg.phone_number_id == "111222333"

    def test_missing_signature_returns_401(self):
        body = json.dumps(_text_payload()).encode()
        resp = client.post(
            "/webhook",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 401

    def test_wrong_signature_returns_401(self):
        resp = self._post(_text_payload(), secret="wrong_secret")
        assert resp.status_code == 401

    def test_non_text_message_still_returns_200(self):
        """Non-text messages are silently acknowledged."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WABA_ID",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+1234",
                                    "phone_number_id": "999",
                                },
                                "messages": [
                                    {
                                        "from": "555",
                                        "id": "wamid.img",
                                        "timestamp": "1700000000",
                                        "type": "image",
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        with patch("app.routers.webhook.emit_message_event", new_callable=AsyncMock) as mock_emit:
            resp = self._post(payload)
        assert resp.status_code == 200
        mock_emit.assert_not_awaited()

    def test_malformed_json_returns_200(self):
        """Malformed payloads are acked to prevent WhatsApp retry storms."""
        body = b"not json at all"
        resp = client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _make_signature(body),
            },
        )
        assert resp.status_code == 200
