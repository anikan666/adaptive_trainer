import logging
from app.schemas.webhook import IncomingTextMessage

logger = logging.getLogger(__name__)


async def emit_message_event(message: IncomingTextMessage) -> None:
    """Emit an incoming WhatsApp text message to the routing layer.

    This is the integration point for ql-w0q (message routing dispatcher).
    Downstream handlers register via the routing layer, not directly here.
    """
    logger.info(
        "message_received",
        extra={
            "message_id": message.message_id,
            "sender_phone": message.sender_phone,
            "phone_number_id": message.phone_number_id,
        },
    )
    # TODO(ql-w0q): dispatch to routing layer
