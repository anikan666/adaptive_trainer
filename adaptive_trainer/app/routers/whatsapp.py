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
from datetime import datetime, timedelta, timezone

import anthropic
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.queries import get_active_convo as _get_active_convo
from app.db.session import AsyncSessionLocal
from app.models.conversation import Conversation, ConversationMode
from app.schemas.webhook import IncomingTextMessage
from app.services import gateway_session
from app.services import lesson_session
from app.services import rate_limiter
from app.services import review_session
from app.services.progress import get_progress_summary
from app.services.quick_lookup import quick_lookup as _lookup
from app.services.topics import get_topic_suggestions
from app.services.whatsapp_sender import send_message

logger = logging.getLogger(__name__)

_DEFAULT_TOPIC = "everyday conversation"

_HELP_TEXT = (
    "QuickLearn Kannada commands:\n"
    "• *lesson* — start a Kannada lesson\n"
    "• *lesson <topic>* — lesson on a specific topic (e.g. lesson greetings)\n"
    "• *topics* — get topic suggestions for your level\n"
    "• *review* — review vocabulary words due today\n"
    "• *gateway* — take the level gateway test (roleplay assessment)\n"
    "• *lookup <word>* — quick Kannada translation\n"
    "• *progress* — view your learning stats\n"
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

_MAX_INPUT_LENGTH = 500
_INPUT_TOO_LONG_TEXT = (
    f"Your message is too long (max {_MAX_INPUT_LENGTH} characters). "
    "Please shorten it and try again."
)

_CANCEL_TEXT = "Lesson cancelled. Send 'lesson' to start a new one."
_NO_ACTIVE_SESSION_TEXT = "Nothing to cancel. Send 'help' to see what I can do."

_SESSION_TIMEOUT_MINUTES = 30
_TIMEOUT_TEXT = "Your previous session timed out. Send 'lesson' to start a new one."

_ACTIVE_SESSION_MODES = {ConversationMode.lesson, ConversationMode.review, ConversationMode.gateway_test}

# ---------------------------------------------------------------------------
# Typo correction — static map of common misspellings
# ---------------------------------------------------------------------------

_TYPO_MAP: dict[str, str] = {
    # help
    "hlep": "help", "hepl": "help", "hep": "help", "halp": "help",
    "helpp": "help", "hekp": "help",
    # lesson
    "lessn": "lesson", "leson": "lesson", "leeson": "lesson",
    "lessno": "lesson", "lesosn": "lesson", "lssn": "lesson",
    "lessson": "lesson", "lessen": "lesson",
    # review
    "reveiw": "review", "reviw": "review", "revew": "review",
    "rview": "review", "reveiv": "review", "rveiw": "review",
    "reviwe": "review",
    # progress
    "progres": "progress", "progess": "progress", "porgress": "progress",
    "prgress": "progress", "progrss": "progress", "progrees": "progress",
    # cancel
    "cancle": "cancel", "cancal": "cancel", "cansel": "cancel",
    "canel": "cancel", "cacel": "cancel", "cncel": "cancel",
    # stop
    "stp": "stop", "sotp": "stop", "stpo": "stop", "stpp": "stop",
    # skip
    "skp": "skip", "skpi": "skip", "sikp": "skip", "skiip": "skip",
    # topics
    "topcs": "topics", "topis": "topics", "topcis": "topics",
    "tpics": "topics", "toipcs": "topics",
    # gateway
    "gatway": "gateway", "gatewya": "gateway", "gaeway": "gateway",
    "gatewy": "gateway", "gatewat": "gateway",
    # lookup
    "lokup": "lookup", "looup": "lookup", "lookp": "lookup",
    "lokoup": "lookup", "lkup": "lookup", "lookupp": "lookup",
}


def _correct_typo(text_lower: str) -> str:
    """Correct common typos in command keywords.

    Handles both single-word commands (e.g. "hlep" → "help") and
    prefix commands (e.g. "lessn greetings" → "lesson greetings").
    """
    # Single-word: direct lookup
    if text_lower in _TYPO_MAP:
        return _TYPO_MAP[text_lower]

    # Prefix commands: check if the first word is a typo
    first_space = text_lower.find(" ")
    if first_space > 0:
        first_word = text_lower[:first_space]
        if first_word in _TYPO_MAP:
            return _TYPO_MAP[first_word] + text_lower[first_space:]

    return text_lower


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

    if len(text) > _MAX_INPUT_LENGTH:
        logger.warning("input_too_long phone=%s length=%d", phone, len(text))
        await _try_send_fallback(phone, _INPUT_TOO_LONG_TEXT)
        return

    text_lower = _correct_typo(text.lower())

    # Load conversation once — used for timeout check and mode-based dispatch.
    convo_mode, convo_context, timed_out = await _load_convo_and_expire(phone)

    if timed_out:
        await _try_send_fallback(phone, _TIMEOUT_TEXT)

    if text_lower == "help":
        await _try_send_fallback(phone, _HELP_TEXT)
        return

    if text_lower in ("cancel", "stop"):
        await _cancel_lesson(phone)
        return

    if text_lower == "progress":
        summary = await get_progress_summary(phone)
        await _try_send_fallback(phone, summary)
        return

    if text_lower == "topics":
        suggestions = await get_topic_suggestions(phone)
        await _try_send_fallback(phone, suggestions)
        return

    if text_lower == "review":
        await review_session.start_review(phone)
        return

    if text_lower == "gateway":
        # Rate-limited: gateway uses AI for roleplay
        if not rate_limiter.is_allowed(phone):
            logger.warning("rate_limit_exceeded phone=%s", phone)
            await _try_send_fallback(phone, _RATE_LIMIT_TEXT)
            return
        try:
            await _handle_gateway(phone)
        except anthropic.RateLimitError as exc:
            logger.error("anthropic_rate_limit phone=%s err=%s", phone, exc)
            await _try_send_fallback(phone, _OVERLOADED_TEXT)
        except anthropic.APIStatusError as exc:
            logger.error("anthropic_api_error phone=%s status=%d err=%s", phone, exc.status_code, exc)
            await _try_send_fallback(phone, _ERROR_TEXT)
        except SQLAlchemyError as exc:
            logger.error("db_error phone=%s err=%s", phone, exc, exc_info=True)
            await _try_send_fallback(phone, _ERROR_TEXT)
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

        mode, lesson_context = convo_mode, convo_context

        if mode == ConversationMode.lesson:
            exercises = lesson_context.get("exercises") if lesson_context else None
            current_index = lesson_context.get("current_index", 0) if lesson_context else 0
            if exercises and current_index < len(exercises):
                await lesson_session.handle_exercise_answer(phone, text)
            else:
                await _handle_lesson(phone, _DEFAULT_TOPIC)
        elif mode == ConversationMode.review:
            await review_session.handle_review_answer(phone, text)
        elif mode == ConversationMode.gateway_test:
            await gateway_session.handle_gateway_turn(phone, text)
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


async def _handle_gateway(phone: str) -> None:
    """Start a gateway test for the learner's current ring."""
    logger.info("gateway_requested phone=%s", phone)
    from app.models.learner import Learner
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Learner).where(Learner.phone_number == phone))
        learner = result.scalar_one_or_none()
        ring = learner.current_ring if learner else 0
    await gateway_session.start_gateway(phone, ring)


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
        if convo is not None and convo.mode in _ACTIVE_SESSION_MODES:
            convo.lesson_context = None
            convo.mode = ConversationMode.quick_lookup
            await db.commit()
            await _try_send_fallback(phone, _CANCEL_TEXT)
            return
    await _try_send_fallback(phone, _NO_ACTIVE_SESSION_TEXT)


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
# Session timeout
# ---------------------------------------------------------------------------


async def _load_convo_and_expire(
    phone: str,
) -> tuple[ConversationMode, dict | None, bool]:
    """Load conversation state and expire stale sessions in a single DB round-trip.

    Returns (mode, lesson_context, timed_out). If the session was stale it is
    reset to quick_lookup and timed_out is True.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=_SESSION_TIMEOUT_MINUTES)
    async with AsyncSessionLocal() as db:
        convo = await _get_active_convo(db, phone)
        if convo is None:
            return ConversationMode.quick_lookup, None, False

        # Check for stale active session
        if convo.mode in _ACTIVE_SESSION_MODES:
            updated = convo.updated_at
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            if updated < cutoff:
                logger.info(
                    "session_timeout phone=%s mode=%s last_active=%s",
                    phone, convo.mode, updated.isoformat(),
                )
                convo.lesson_context = None
                convo.mode = ConversationMode.quick_lookup
                await db.commit()
                return ConversationMode.quick_lookup, None, True

        return convo.mode, convo.lesson_context, False


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


