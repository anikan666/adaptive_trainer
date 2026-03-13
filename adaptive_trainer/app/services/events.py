import logging

from cachetools import TTLCache

from app.routers.whatsapp import dispatch_message
from app.schemas.webhook import IncomingTextMessage
from app.services.onboarding import handle_onboarding, needs_onboarding

logger = logging.getLogger(__name__)

# TTL cache for deduplicating WhatsApp message retries.
# WhatsApp retries within a ~5-minute window, so a 300s TTL is sufficient.
_seen_ids: TTLCache = TTLCache(maxsize=10_000, ttl=300)


async def emit_message_event(message: IncomingTextMessage) -> None:
    """Emit an incoming WhatsApp text message to the routing layer.

    Routes new users through onboarding before handing off to the main
    dispatcher. Duplicate message_ids (WhatsApp retries) are dropped
    before any processing occurs.
    """
    if message.message_id in _seen_ids:
        logger.info("duplicate_message skipped id=%s", message.message_id)
        return
    _seen_ids[message.message_id] = True

    logger.info(
        "message_received",
        extra={
            "message_id": message.message_id,
            "sender_phone": message.sender_phone,
            "phone_number_id": message.phone_number_id,
        },
    )

    if await needs_onboarding(message.sender_phone):
        await handle_onboarding(message.sender_phone, message.text)
        return

    await dispatch_message(message)
