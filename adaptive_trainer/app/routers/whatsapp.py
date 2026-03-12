"""WhatsApp message routing dispatcher.

Dispatches incoming text messages to the appropriate handler based on:
1. Keyword triggers in the message text (lesson, lookup, help)
2. Current conversation mode stored in the database

Modes:
  onboarding   — handled upstream (events.py); not dispatched here
  lesson       — active lesson flow; non-keyword input continues the lesson
  quick_lookup — default mode; text is treated as a lookup phrase

This module is stateless: all state is read from and written to the DB.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.conversation import Conversation, ConversationMode
from app.schemas.webhook import IncomingTextMessage
from app.services.level_tracker import get_learner_level
from app.services.lesson import generate_lesson
from app.services.quick_lookup import quick_lookup as _lookup
from app.services.whatsapp_sender import send_message

logger = logging.getLogger(__name__)

_DEFAULT_TOPIC = "everyday conversation"

_HELP_TEXT = (
    "QuickLearn Kannada commands:\n"
    "• *lesson* — start a Kannada lesson\n"
    "• *lesson <topic>* — lesson on a specific topic (e.g. lesson greetings)\n"
    "• *lookup <word>* — quick Kannada translation\n"
    "• *help* — show this menu"
)


async def dispatch_message(message: IncomingTextMessage) -> None:
    """Route an incoming WhatsApp message to the appropriate handler.

    Keyword triggers take priority over the current conversation mode:
      - "help"             → send the help menu
      - "lesson [<topic>]" → generate and send a lesson
      - "lookup <phrase>"  → translate phrase to colloquial Kannada
      - anything else      → quick lookup (default) or lesson continuation

    Args:
        message: Normalized incoming WhatsApp text message.
    """
    phone = message.sender_phone
    text = message.text.strip()
    text_lower = text.lower()

    if text_lower == "help":
        await send_message(phone, _HELP_TEXT)
        return

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

    mode = await _get_mode(phone)

    if mode == ConversationMode.lesson:
        # In an active lesson flow, bare text is treated as a new lesson topic
        await _handle_lesson(phone, text or _DEFAULT_TOPIC)
    else:
        # Default: treat bare text as a lookup phrase
        await _handle_lookup(phone, text)


# ---------------------------------------------------------------------------
# Internal handlers
# ---------------------------------------------------------------------------


async def _handle_lesson(phone: str, topic: str) -> None:
    """Generate an adaptive lesson and send it to the learner."""
    try:
        level = await get_learner_level(phone)
    except ValueError:
        level = 1

    logger.info("lesson_requested phone=%s topic=%s level=%d", phone, topic, level)
    lesson_text = await generate_lesson(level=level, topic=topic)
    await send_message(phone, lesson_text)
    await _set_mode(phone, ConversationMode.lesson)


async def _handle_lookup(phone: str, phrase: str) -> None:
    """Translate a phrase and send the result."""
    logger.info("lookup_requested phone=%s phrase=%s", phone, phrase)
    result = await _lookup(phrase)
    await send_message(phone, result)
    await _set_mode(phone, ConversationMode.quick_lookup)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


async def _get_mode(phone: str) -> ConversationMode:
    """Return the current conversation mode, defaulting to quick_lookup."""
    async with AsyncSessionLocal() as db:
        convo = await _get_active_convo(db, phone)
        return convo.mode if convo else ConversationMode.quick_lookup


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
