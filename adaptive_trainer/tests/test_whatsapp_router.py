"""Tests for the WhatsApp message routing dispatcher."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test_access")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test_app_secret")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "test_phone_id")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")

from app.models.conversation import Conversation, ConversationMode  # noqa: E402
from app.routers.whatsapp import _HELP_TEXT, dispatch_message  # noqa: E402
from app.schemas.webhook import IncomingTextMessage  # noqa: E402


def _make_message(text: str, phone: str = "14155550001") -> IncomingTextMessage:
    return IncomingTextMessage(
        message_id="wamid.test",
        sender_phone=phone,
        text=text,
        timestamp="1700000000",
        phone_number_id="test_phone_id",
    )


def _make_convo(mode: ConversationMode) -> Conversation:
    convo = MagicMock(spec=Conversation)
    convo.mode = mode
    return convo


# ---------------------------------------------------------------------------
# Helpers: patch DB and service calls together
# ---------------------------------------------------------------------------

_PATCH_GET_MODE = "app.routers.whatsapp._get_mode"
_PATCH_SET_MODE = "app.routers.whatsapp._set_mode"
_PATCH_SEND = "app.routers.whatsapp.send_message"
_PATCH_LESSON = "app.routers.whatsapp.generate_lesson"
_PATCH_LOOKUP = "app.routers.whatsapp._lookup"
_PATCH_LEVEL = "app.routers.whatsapp.get_learner_level"


# ---------------------------------------------------------------------------
# help keyword
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_help_sends_help_text():
    with (
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_GET_MODE, new_callable=AsyncMock) as mock_mode,
    ):
        await dispatch_message(_make_message("help"))

    mock_send.assert_awaited_once_with("14155550001", _HELP_TEXT)
    mock_mode.assert_not_awaited()


@pytest.mark.asyncio
async def test_help_case_insensitive():
    with (
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_GET_MODE, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_message("HELP"))

    mock_send.assert_awaited_once()


# ---------------------------------------------------------------------------
# lesson keyword
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lesson_keyword_triggers_lesson():
    with (
        patch(_PATCH_LEVEL, new_callable=AsyncMock, return_value=2),
        patch(_PATCH_LESSON, new_callable=AsyncMock, return_value="Lesson content") as mock_lesson,
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_SET_MODE, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_message("lesson"))

    mock_lesson.assert_awaited_once()
    call_kwargs = mock_lesson.call_args[1]
    assert call_kwargs["level"] == 2
    assert call_kwargs["topic"] == "everyday conversation"


@pytest.mark.asyncio
async def test_lesson_with_topic():
    with (
        patch(_PATCH_LEVEL, new_callable=AsyncMock, return_value=3),
        patch(_PATCH_LESSON, new_callable=AsyncMock, return_value="Lesson") as mock_lesson,
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_SET_MODE, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_message("lesson greetings"))

    call_kwargs = mock_lesson.call_args[1]
    assert call_kwargs["topic"] == "greetings"


@pytest.mark.asyncio
async def test_lesson_sends_content_and_sets_mode():
    with (
        patch(_PATCH_LEVEL, new_callable=AsyncMock, return_value=1),
        patch(_PATCH_LESSON, new_callable=AsyncMock, return_value="📚 Lesson here"),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_SET_MODE, new_callable=AsyncMock) as mock_set,
    ):
        await dispatch_message(_make_message("lesson"))

    mock_send.assert_awaited_once_with("14155550001", "📚 Lesson here")
    mock_set.assert_awaited_once_with("14155550001", ConversationMode.lesson)


@pytest.mark.asyncio
async def test_lesson_falls_back_to_level_1_if_no_learner():
    with (
        patch(_PATCH_LEVEL, new_callable=AsyncMock, side_effect=ValueError("no learner")),
        patch(_PATCH_LESSON, new_callable=AsyncMock, return_value="Lesson") as mock_lesson,
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_SET_MODE, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_message("lesson"))

    call_kwargs = mock_lesson.call_args[1]
    assert call_kwargs["level"] == 1


# ---------------------------------------------------------------------------
# lookup keyword
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lookup_keyword_triggers_lookup():
    with (
        patch(_PATCH_LOOKUP, new_callable=AsyncMock, return_value="ನಮಸ್ಕಾರ (namaskara) — greeting") as mock_lkp,
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_SET_MODE, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_message("lookup hello"))

    mock_lkp.assert_awaited_once_with("hello")


@pytest.mark.asyncio
async def test_lookup_sends_result_and_sets_mode():
    result = "ನಮಸ್ಕಾರ (namaskara) — greeting"
    with (
        patch(_PATCH_LOOKUP, new_callable=AsyncMock, return_value=result),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_SET_MODE, new_callable=AsyncMock) as mock_set,
    ):
        await dispatch_message(_make_message("lookup hello"))

    mock_send.assert_awaited_once_with("14155550001", result)
    mock_set.assert_awaited_once_with("14155550001", ConversationMode.quick_lookup)


@pytest.mark.asyncio
async def test_lookup_empty_phrase_falls_through_to_mode():
    """'lookup ' with no phrase falls through to mode-based dispatch."""
    with (
        patch(_PATCH_GET_MODE, new_callable=AsyncMock, return_value=ConversationMode.quick_lookup),
        patch(_PATCH_LOOKUP, new_callable=AsyncMock, return_value="result") as mock_lkp,
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_SET_MODE, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_message("lookup "))

    # Phrase is empty → falls through to mode dispatch on "lookup " text
    mock_lkp.assert_awaited_once()


# ---------------------------------------------------------------------------
# Mode-based routing (no keyword)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bare_text_in_quick_lookup_mode_triggers_lookup():
    with (
        patch(_PATCH_GET_MODE, new_callable=AsyncMock, return_value=ConversationMode.quick_lookup),
        patch(_PATCH_LOOKUP, new_callable=AsyncMock, return_value="res") as mock_lkp,
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_SET_MODE, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_message("how are you"))

    mock_lkp.assert_awaited_once_with("how are you")


@pytest.mark.asyncio
async def test_bare_text_in_lesson_mode_triggers_lesson():
    with (
        patch(_PATCH_GET_MODE, new_callable=AsyncMock, return_value=ConversationMode.lesson),
        patch(_PATCH_LEVEL, new_callable=AsyncMock, return_value=2),
        patch(_PATCH_LESSON, new_callable=AsyncMock, return_value="Lesson") as mock_lesson,
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_SET_MODE, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_message("food ordering"))

    mock_lesson.assert_awaited_once()
    assert mock_lesson.call_args[1]["topic"] == "food ordering"


@pytest.mark.asyncio
async def test_no_mode_defaults_to_lookup():
    """When there is no active conversation, defaults to quick_lookup."""
    with (
        patch(_PATCH_GET_MODE, new_callable=AsyncMock, return_value=ConversationMode.quick_lookup),
        patch(_PATCH_LOOKUP, new_callable=AsyncMock, return_value="res") as mock_lkp,
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_SET_MODE, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_message("thank you"))

    mock_lkp.assert_awaited_once_with("thank you")
