import logging

from app.schemas.webhook import IncomingTextMessage
from app.services.onboarding import handle_onboarding, needs_onboarding

logger = logging.getLogger(__name__)


async def emit_message_event(message: IncomingTextMessage) -> None:
    """Emit an incoming WhatsApp text message to the routing layer.

    Routes new users through onboarding before handing off to the main
    dispatcher (ql-w0q).
    """
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

    # TODO(ql-w0q): dispatch to routing layer
