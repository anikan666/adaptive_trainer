"""Background task that warns users when their session is about to timeout.

Runs a periodic check (every 60 seconds) for active sessions where
updated_at is between 25 and 30 minutes old and no warning has been sent yet.
Sends a WhatsApp message and marks the session so the warning is not repeated.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.conversation import Conversation, ConversationMode
from app.services.whatsapp_sender import send_message

logger = logging.getLogger(__name__)

_WARNING_MINUTES = 25
_TIMEOUT_MINUTES = 30
_CHECK_INTERVAL_SECONDS = 60

_ACTIVE_MODES = {ConversationMode.lesson, ConversationMode.review, ConversationMode.gateway_test}

_TIMEOUT_WARNING_TEXT = (
    "Your session will timeout in 5 minutes. Send a message to continue."
)


async def _check_and_warn() -> int:
    """Check for sessions nearing timeout and send warnings.

    Returns the number of warnings sent (useful for testing/logging).
    """
    now = datetime.now(timezone.utc)
    warn_cutoff = now - timedelta(minutes=_WARNING_MINUTES)
    expire_cutoff = now - timedelta(minutes=_TIMEOUT_MINUTES)

    warned = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Conversation).where(
                Conversation.mode.in_(list(_ACTIVE_MODES)),
            )
        )
        convos = result.scalars().all()

        for convo in convos:
            updated = convo.updated_at
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)

            # Skip non-active modes (belt-and-suspenders with the SQL filter)
            if convo.mode not in _ACTIVE_MODES:
                continue

            # Skip if already expired (will be handled on next message)
            if updated < expire_cutoff:
                continue

            # Skip if not yet in the warning window
            if updated >= warn_cutoff:
                continue

            # Skip if warning already sent
            ctx = convo.lesson_context
            if ctx and ctx.get("timeout_warning_sent"):
                continue

            # Send warning
            try:
                await send_message(convo.phone_number, _TIMEOUT_WARNING_TEXT)
            except Exception as exc:
                logger.error(
                    "timeout_warning_send_failed phone=%s err=%s",
                    convo.phone_number, exc,
                )
                continue

            # Mark warning sent in lesson_context
            if ctx is None:
                ctx = {}
            ctx = {**ctx, "timeout_warning_sent": True}
            convo.lesson_context = ctx
            warned += 1

        if warned:
            await db.commit()
            logger.info("timeout_warnings_sent count=%d", warned)

    return warned


async def run_timeout_warning_loop() -> None:
    """Run the timeout warning check in a loop until cancelled."""
    logger.info("timeout_warning_loop started")
    try:
        while True:
            try:
                await _check_and_warn()
            except Exception:
                logger.exception("timeout_warning_check_error")
            await asyncio.sleep(_CHECK_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        logger.info("timeout_warning_loop stopped")
