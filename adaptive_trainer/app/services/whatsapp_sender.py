"""Async WhatsApp message sender using the WhatsApp Business API."""
import asyncio
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

_GRAPH_API_VERSION = "v18.0"
_BASE_URL = "https://graph.facebook.com"
_MAX_RETRIES = 5
_BACKOFF_BASE = 1.0

def _messages_url() -> str:
    return f"{_BASE_URL}/{_GRAPH_API_VERSION}/{settings.whatsapp_phone_number_id}/messages"

def _auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }

async def send_message(to: str, text: str) -> dict:
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    logger.info("Sending WhatsApp message to=%s text_len=%d", to, len(text))
    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(_MAX_RETRIES):
            try:
                response = await client.post(
                    _messages_url(),
                    headers=_auth_headers(),
                    json=payload,
                )
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", _BACKOFF_BASE * (2**attempt)))
                    logger.warning("Rate limited (attempt %d/%d), retrying in %.1fs", attempt + 1, _MAX_RETRIES, retry_after)
                    await asyncio.sleep(retry_after)
                    continue
                if response.status_code >= 500:
                    wait = _BACKOFF_BASE * (2**attempt)
                    logger.warning("Server error %d (attempt %d/%d), retrying in %.1fs", response.status_code, attempt + 1, _MAX_RETRIES, wait)
                    await asyncio.sleep(wait)
                    continue
                response.raise_for_status()
                data = response.json()
                logger.info("WhatsApp message sent to=%s message_id=%s", to, data.get("messages", [{}])[0].get("id"))
                return data
            except httpx.TransportError as exc:
                wait = _BACKOFF_BASE * (2**attempt)
                logger.warning("Transport error (attempt %d/%d): %s, retrying in %.1fs", attempt + 1, _MAX_RETRIES, exc, wait)
                if attempt == _MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(wait)
    raise RuntimeError(f"Failed to send WhatsApp message to {to} after {_MAX_RETRIES} attempts")
