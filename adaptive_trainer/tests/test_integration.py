"""End-to-end integration tests for the adaptive_trainer WhatsApp app.

All external dependencies (Anthropic API, WhatsApp API, PostgreSQL) are mocked.
Tests use FastAPI's async test client (httpx) and drive full request paths.
"""

import hashlib
import hmac
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_verify")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test_access")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test_secret")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "test_phone_id")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")

from app.main import app  # noqa: E402
from app.services import rate_limiter  # noqa: E402

_SECRET = "test_secret"
_VERIFY_TOKEN = "test_verify"
_PHONE = "14155550001"


def _sign(body: bytes) -> str:
    sig = hmac.new(_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _wa_payload(phone: str, text: str) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550000000",
                                "phone_number_id": "test_phone_id",
                            },
                            "messages": [
                                {
                                    "id": "wamid.test001",
                                    "from": phone,
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


@pytest.fixture(autouse=True)
def clear_rate_log():
    rate_limiter._call_log.clear()
    yield
    rate_limiter._call_log.clear()


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Webhook verification (GET)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_verify_success(client):
    resp = await client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": _VERIFY_TOKEN,
            "hub.challenge": "999",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == 999


@pytest.mark.asyncio
async def test_webhook_verify_wrong_token(client):
    resp = await client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong",
            "hub.challenge": "999",
        },
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Flow 1: Quick Lookup — webhook → dispatch → Claude Haiku → WhatsApp send
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quick_lookup_flow(client):
    body = json.dumps(_wa_payload(_PHONE, "lookup how are you")).encode()

    mock_learner = MagicMock()
    mock_learner.scalar_one_or_none.return_value = MagicMock()  # learner exists

    with (
        patch("app.services.onboarding.AsyncSessionLocal") as mock_session_cls,
        patch(
            "app.services.quick_lookup.ask_haiku_with_system",
            new_callable=AsyncMock,
            return_value="hegiddira? (hegiddira?) — casual greeting",
        ),
        patch(
            "app.routers.whatsapp.send_message", new_callable=AsyncMock
        ) as mock_send,
        patch("app.routers.whatsapp._set_mode", new_callable=AsyncMock),
    ):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_learner)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_ctx

        resp = await client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _sign(body),
            },
        )

    assert resp.status_code == 200
    mock_send.assert_awaited_once()
    sent_text = mock_send.call_args[0][1]
    assert "hegiddira" in sent_text


# ---------------------------------------------------------------------------
# Flow 2: Lesson flow — "lesson greetings" → Claude Sonnet → WhatsApp send
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lesson_flow(client):
    body = json.dumps(_wa_payload(_PHONE, "lesson greetings")).encode()

    mock_learner = MagicMock()
    mock_learner.scalar_one_or_none.return_value = MagicMock()

    with (
        patch("app.services.onboarding.AsyncSessionLocal") as mock_session_cls,
        patch(
            "app.services.lesson.ask_sonnet",
            new_callable=AsyncMock,
            return_value="Lesson: Greetings\n1. hegiddira — how are you",
        ),
        patch(
            "app.routers.whatsapp.get_learner_level",
            new_callable=AsyncMock,
            return_value=2,
        ),
        patch(
            "app.routers.whatsapp.send_message", new_callable=AsyncMock
        ) as mock_send,
        patch("app.routers.whatsapp._set_mode", new_callable=AsyncMock),
    ):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_learner)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_ctx

        resp = await client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _sign(body),
            },
        )

    assert resp.status_code == 200
    mock_send.assert_awaited_once()
    assert "Greetings" in mock_send.call_args[0][1]


# ---------------------------------------------------------------------------
# Flow 3: Onboarding — new user gets welcome message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_onboarding_flow_new_user(client):
    body = json.dumps(_wa_payload(_PHONE, "hello")).encode()

    # Simulate learner not found (None) and no existing conversation
    mock_db = MagicMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    with (
        patch("app.services.onboarding.AsyncSessionLocal") as mock_session_cls,
        patch(
            "app.services.onboarding.send_message", new_callable=AsyncMock
        ) as mock_send,
    ):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_ctx

        resp = await client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _sign(body),
            },
        )

    assert resp.status_code == 200
    mock_send.assert_awaited_once()
    assert "Welcome" in mock_send.call_args[0][1]


# ---------------------------------------------------------------------------
# Flow 4: Invalid signature → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_signature_rejected(client):
    body = json.dumps(_wa_payload(_PHONE, "hello")).encode()
    resp = await client.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=badhash",
        },
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Flow 5: Rate limit exceeded → 200 with rate limit message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_flow(client):
    body = json.dumps(_wa_payload(_PHONE, "lookup hello")).encode()

    mock_learner = MagicMock()
    mock_learner.scalar_one_or_none.return_value = MagicMock()

    with (
        patch("app.services.onboarding.AsyncSessionLocal") as mock_session_cls,
        patch("app.routers.whatsapp.rate_limiter.is_allowed", return_value=False),
        patch(
            "app.routers.whatsapp.send_message", new_callable=AsyncMock
        ) as mock_send,
    ):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_learner)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_ctx

        resp = await client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _sign(body),
            },
        )

    assert resp.status_code == 200
    mock_send.assert_awaited_once()
    assert "limit" in mock_send.call_args[0][1].lower()
