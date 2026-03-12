import hashlib
import hmac
import logging

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.config import settings
from app.schemas.webhook import IncomingTextMessage, WebhookPayload
from app.services.events import emit_message_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


def _verify_signature(payload_bytes: bytes, signature_header: str | None) -> bool:
    """Verify X-Hub-Signature-256 HMAC signature from WhatsApp."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = signature_header.removeprefix("sha256=")
    actual = hmac.new(
        settings.whatsapp_app_secret.encode(),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(actual, expected)


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> int:
    """WhatsApp webhook verification handshake (GET /webhook).

    Meta calls this endpoint when you register or update the webhook URL.
    Returns hub.challenge as plain text on success, 403 on token mismatch.
    """
    if hub_mode != "subscribe" or hub_verify_token != settings.whatsapp_verify_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return int(hub_challenge)


@router.post("", status_code=status.HTTP_200_OK)
async def receive_message(request: Request) -> dict:
    """Receive incoming WhatsApp messages (POST /webhook).

    Verifies the HMAC-SHA256 signature, parses the payload, and emits
    text message events to the routing layer.  Non-text message types
    are silently acknowledged (required by WhatsApp — must always 200).
    """
    body = await request.body()

    sig = request.headers.get("X-Hub-Signature-256")
    if not _verify_signature(body, sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature"
        )

    try:
        payload = WebhookPayload.model_validate_json(body)
    except Exception:
        logger.warning("unparseable_webhook_payload")
        # Return 200 to prevent WhatsApp from retrying malformed payloads
        return {"status": "ok"}

    for entry in payload.entry:
        for change in entry.changes:
            if change.field != "messages":
                continue
            value = change.value
            for msg in value.messages or []:
                if msg.type != "text" or msg.text is None:
                    continue
                incoming = IncomingTextMessage(
                    message_id=msg.id,
                    sender_phone=msg.from_,
                    text=msg.text.body,
                    timestamp=msg.timestamp,
                    phone_number_id=value.metadata.phone_number_id,
                )
                await emit_message_event(incoming)

    return {"status": "ok"}
