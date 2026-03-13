"""WhatsApp message routing dispatcher.

Dispatches incoming text messages to the appropriate handler based on:
1. Keyword triggers in the message text (lesson, lookup, help, cancel/stop)
2. Current conversation mode stored in the database

Modes:
  onboarding   — handled upstream (events.py); not dispatched here
  lesson       — active lesson flow; non-keyword input continues the lesson
  quick_lookup — default mode; text is treated as a lookup phrase

This module is stateless: all state is read from and written to the DB.
"""

import logging

import anthropic
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.conversation import Conversation, ConversationMode
from app.schemas.webhook import IncomingTextMessage
from app.services import lesson_session
from app.services import rate_limiter
from app.services.quick_lookup import quick_lookup as _lookup
from app.services.whatsapp_sender import send_message

logger = logging.getLogger(__name__)

_DEFAULT_TOPIC = "everyday conversation"

_HELP_TEXT = (
    "QuickLearn Kannada commands:\n"
    "• *lesson* — start a Kannada lesson\n"
    "• *lesson <topic>* — lesson on a specific topic (e.g. lesson greetings)\n"
    "• *lookup <word>* — quick Kannada translation\n"
    "• *cancel* or *stop* — cancel the current lesson\n"
    "• *help* — show this menu"
)

_RATE_LIMIT_TEXT = (
    "You've reached the limit of 20 AI requests per hour. "
    "Please try again later."
)

_ERROR_TEXT = "Sorry, I'm having trouble right now. Please try again in a moment."

_OVERLOADED_TEXT = (
    "The AI service is currently overloaded. Please try again in a few minutes."
)

_CANCEL_TEXT = "Lesson cancelled. Send 'lesson' to start a new one."


async def dispatch_message(message: IncomingTextMessage) -> None:
    """Route an incoming WhatsApp message to the appropriate handler.

    Keyword triggers take priority over the current conversation mode:
      - "help"             → send the help menu
      - "cancel" / "stop"  → cancel active lesson, return to quick_lookup
      - "lesson [<topic>]" → start a lesson session
      - "lookup <phrase>"  → translate phrase to colloquial Kannada
      - anything else      → exercise answer (if active lesson) or quick lookup

    All Anthropic API errors, database errors, and WhatsApp send failures are
    caught here; a safe fallback message is sent to the user on error.

    Args:
        message: Normalized incoming WhatsApp text message.
    """
    phone = message.sender_phone
    text = message.text.strip()
    text_lower = text.lower()

    if text_lower == "help":
        await _try_send_fallback(phone, _HELP_TEXT)
        return

    if text_lower in ("cancel", "stop"):
        await _cancel_lesson(phone)
        return

    # All paths below invoke AI — enforce the per-phone hourly rate limit.
    if not rate_limiter.is_allowed(phone):
        logger.warning("rate_limit_exceeded phone=%s", phone)
        await _try_send_fallback(phone, _RATE_LIMIT_TEXT)
        return

    try:
        if text_lower == "lesson" or text_lower.startswith("lesson "):
            topic = text[len("lesson"):].strip() or _DEFAULT_TOPIC
            await _handle_lesson(phone, topic)
            return

        if text_lower.startswith("lookup "):
            phrase = text[len("lookup "):].strip()
            if phrase:
                await _handle_lookup(phone, phrase)
                return
            # Empty phrase — fall through to mode-based dispatch

        mode, lesson_context = await _get_convo_state(phone)

        if mode == ConversationMode.lesson:
            exercises = lesson_context.get("exercises") if lesson_context else None
            current_index = lesson_context.get("current_index", 0) if lesson_context else 0
            if exercises and current_index < len(exercises):
                await lesson_session.handle_exercise_answer(phone, text)
            else:
                await _handle_lesson(phone, _DEFAULT_TOPIC)
        else:
            # Default: treat bare text as a lookup phrase
            await _handle_lookup(phone, text)

    except anthropic.RateLimitError as exc:
        logger.error("anthropic_rate_limit phone=%s err=%s", phone, exc)
        await _try_send_fallback(phone, _OVERLOADED_TEXT)
    except anthropic.APIStatusError as exc:
        logger.error("anthropic_api_error phone=%s status=%d err=%s", phone, exc.status_code, exc)
        await _try_send_fallback(phone, _ERROR_TEXT)
    except SQLAlchemyError as exc:
        logger.error("db_error phone=%s err=%s", phone, exc, exc_info=True)
        await _try_send_fallback(phone, _ERROR_TEXT)
    except RuntimeError as exc:
        # WhatsApp send failure from an inner send_message call.
        # _try_send_fallback would likely fail too, so just log.
        logger.error("whatsapp_send_failure phone=%s err=%s", phone, exc)


# ---------------------------------------------------------------------------
# Internal handlers
# ---------------------------------------------------------------------------


async def _handle_lesson(phone: str, topic: str) -> None:
    """Start a lesson session for the learner."""
    logger.info("lesson_requested phone=%s topic=%s", phone, topic)
    await lesson_session.start_lesson(phone, topic)


async def _handle_lookup(phone: str, phrase: str) -> None:
    """Translate a phrase and send the result."""
    logger.info("lookup_requested phone=%s phrase=%s", phone, phrase)
    result = await _lookup(phrase)
    await send_message(phone, result)
    await _set_mode(phone, ConversationMode.quick_lookup)


async def _cancel_lesson(phone: str) -> None:
    """Cancel the active lesson session and return to quick_lookup mode."""
    async with AsyncSessionLocal() as db:
        convo = await _get_active_convo(db, phone)
        if convo is not None:
            convo.lesson_context = None
            convo.mode = ConversationMode.quick_lookup
            await db.commit()
    await _try_send_fallback(phone, _CANCEL_TEXT)


# ---------------------------------------------------------------------------
# Error helpers
# ---------------------------------------------------------------------------


async def _try_send_fallback(phone: str, text: str) -> None:
    """Attempt to send a message; swallow errors to avoid cascading failures."""
    try:
        await send_message(phone, text)
    except Exception as exc:
        logger.error("fallback_send_failure phone=%s err=%s", phone, exc)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


async def _get_convo_state(phone: str) -> tuple[ConversationMode, dict | None]:
    """Return the current conversation mode and lesson_context."""
    async with AsyncSessionLocal() as db:
        convo = await _get_active_convo(db, phone)
        if convo is None:
            return ConversationMode.quick_lookup, None
        return convo.mode, convo.lesson_context


async def _set_mode(phone: str, mode: ConversationMode) -> None:
    """Upsert the active conversation record with the given mode."""
    async with AsyncSessionLocal() as db:
        convo = await _get_active_convo(db, phone)
        if convo is None:
            convo = Conversation(phone_number=phone, mode=mode)
            db.add(convo)
        else:
            convo.mode = mode
        await db.commit()


async def _get_active_convo(db: AsyncSession, phone: str) -> Conversation | None:
    """Return the most-recently-updated non-onboarding conversation, or None."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.phone_number == phone)
        .where(Conversation.mode != ConversationMode.onboarding)
        .order_by(Conversation.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
