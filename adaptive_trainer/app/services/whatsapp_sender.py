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
_MAX_MESSAGE_LENGTH = 4000  # WhatsApp limit is 4096; leave margin

def _split_message(text: str) -> list[str]:
    """Split text into chunks that fit within WhatsApp's character limit.

    Splits at paragraph boundaries (double newline) when possible.
    Falls back to hard truncation with '...' suffix.
    """
    if len(text) <= _MAX_MESSAGE_LENGTH:
        return [text]

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= _MAX_MESSAGE_LENGTH:
            chunks.append(remaining)
            break
        # Try to split at a paragraph boundary within the limit
        split_region = remaining[:_MAX_MESSAGE_LENGTH]
        split_pos = split_region.rfind("\n\n")
        if split_pos > 0:
            chunks.append(remaining[:split_pos])
            remaining = remaining[split_pos + 2:]  # skip the double newline
        else:
            # No paragraph boundary — hard truncate
            chunks.append(remaining[:_MAX_MESSAGE_LENGTH - 3] + "...")
            remaining = remaining[_MAX_MESSAGE_LENGTH - 3:]
    return chunks

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    """Return the shared httpx client, creating it lazily if needed."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30.0)
    return _client


async def close_client() -> None:
    """Close the shared httpx client. Called during app shutdown."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _messages_url() -> str:
    return f"{_BASE_URL}/{_GRAPH_API_VERSION}/{settings.whatsapp_phone_number_id}/messages"

def _auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }

async def _send_single(client: httpx.AsyncClient, to: str, text: str) -> dict:
    """Send a single text message (must be within the character limit)."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
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


async def send_message(to: str, text: str) -> dict:
    chunks = _split_message(text)
    logger.info("Sending WhatsApp message to=%s text_len=%d chunks=%d", to, len(text), len(chunks))
    async with httpx.AsyncClient(timeout=30.0) as client:
        last_result: dict = {}
        for chunk in chunks:
            last_result = await _send_single(client, to, chunk)
        return last_result
