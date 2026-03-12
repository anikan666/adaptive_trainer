import logging

from app.routers.whatsapp import dispatch_message
from app.schemas.webhook import IncomingTextMessage
from app.services.onboarding import handle_onboarding, needs_onboarding

logger = logging.getLogger(__name__)


async def emit_message_event(message: IncomingTextMessage) -> None:
    """Emit an incoming WhatsApp text message to the routing layer.

    Routes new users through onboarding before handing off to the main
    dispatcher.
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

    await dispatch_message(message)
