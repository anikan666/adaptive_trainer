"""Learner onboarding flow: welcome → name → level → create record → main menu."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.conversation import Conversation, ConversationMode
from app.models.learner import Learner
from app.services.whatsapp_sender import send_message

logger = logging.getLogger(__name__)

_WELCOME = (
    "Welcome to QuickLearn Kannada! 🙏\n"
    "I'll help you learn Kannada through short daily lessons.\n\n"
    "What's your name?"
)

_ASK_LEVEL = (
    "Nice to meet you, {name}! 👋\n\n"
    "On a scale of 1–5, how would you rate your current Kannada level?\n"
    "1 = Complete beginner\n"
    "2 = Know a few words\n"
    "3 = Basic conversations\n"
    "4 = Intermediate\n"
    "5 = Advanced"
)

_INVALID_LEVEL = (
    "Please reply with a number between 1 and 5.\n"
    "1 = Complete beginner\n"
    "2 = Know a few words\n"
    "3 = Basic conversations\n"
    "4 = Intermediate\n"
    "5 = Advanced"
)

_MAIN_MENU = (
    "You're all set! 🎉\n\n"
    "Send me a message anytime:\n"
    "• *lesson* — get a Kannada lesson\n"
    "• *lookup <word>* — quick word lookup\n"
    "• *help* — see all commands"
)


async def needs_onboarding(phone: str) -> bool:
    """Return True if this phone number has not completed onboarding."""
    async with AsyncSessionLocal() as db:
        learner = await _get_learner(db, phone)
        return learner is None


async def handle_onboarding(phone: str, text: str) -> None:
    """Handle an incoming message during the onboarding flow.

    Routes to the correct onboarding step based on the current conversation
    state.  If no onboarding conversation exists yet, sends the welcome message
    and creates one.

    Args:
        phone: Sender's phone number in E.164 format.
        text: Incoming message text.
    """
    async with AsyncSessionLocal() as db:
        learner = await _get_learner(db, phone)
        if learner is not None:
            # Already onboarded — nothing to do here
            return

        convo = await _get_onboarding_convo(db, phone)

        if convo is None:
            # First contact: create onboarding conversation and send welcome
            new_convo = Conversation(
                phone_number=phone,
                mode=ConversationMode.onboarding,
                lesson_context={"step": "ask_name"},
            )
            db.add(new_convo)
            await db.commit()
            await send_message(phone, _WELCOME)
            return

        step = (convo.lesson_context or {}).get("step", "ask_name")

        if step == "ask_name":
            await _handle_ask_name(db, convo, phone, text)
        elif step == "ask_level":
            await _handle_ask_level(db, convo, phone, text)
        else:
            logger.warning("onboarding_unknown_step phone=%s step=%s", phone, step)


async def _get_learner(db: AsyncSession, phone: str) -> Learner | None:
    result = await db.execute(select(Learner).where(Learner.phone_number == phone))
    return result.scalar_one_or_none()


async def _get_onboarding_convo(db: AsyncSession, phone: str) -> Conversation | None:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.phone_number == phone)
        .where(Conversation.mode == ConversationMode.onboarding)
    )
    return result.scalar_one_or_none()


_COMMAND_KEYWORDS = {"help", "lesson", "lookup", "review", "progress", "cancel", "stop"}

_ONBOARDING_HELP = (
    "I can help you learn Kannada! But first, let's finish setting up.\n\n"
    "Available commands (after setup):\n"
    "• *lesson* — start a Kannada lesson\n"
    "• *lookup <word>* — quick translation\n"
    "• *review* — review vocabulary\n"
    "• *progress* — view your stats\n"
    "• *help* — show commands\n\n"
    "What's your name?"
)

_FINISH_SETUP_FIRST = "Let's finish setting up first! 😊 What's your name?"


async def _handle_ask_name(
    db: AsyncSession, convo: Conversation, phone: str, text: str
) -> None:
    name = text.strip()
    if not name:
        await send_message(phone, "I didn't catch that — what's your name?")
        return

    # Don't silently swallow commands as the user's name
    if name.lower().split()[0] in _COMMAND_KEYWORDS:
        if name.lower().split()[0] == "help":
            await send_message(phone, _ONBOARDING_HELP)
        else:
            await send_message(phone, _FINISH_SETUP_FIRST)
        return

    convo.lesson_context = {"step": "ask_level", "name": name}
    await db.commit()
    await send_message(phone, _ASK_LEVEL.format(name=name))


async def _handle_ask_level(
    db: AsyncSession, convo: Conversation, phone: str, text: str
) -> None:
    try:
        level = int(text.strip())
        if level < 1 or level > 5:
            raise ValueError("out of range")
    except (ValueError, TypeError):
        await send_message(phone, _INVALID_LEVEL)
        return

    name = (convo.lesson_context or {}).get("name", "")

    learner = Learner(phone_number=phone, level=level, name=name or None)
    db.add(learner)

    convo.lesson_context = {"step": "complete", "name": name}
    await db.commit()

    logger.info("onboarding_complete phone=%s level=%d", phone, level)
    await send_message(phone, _MAIN_MENU)
