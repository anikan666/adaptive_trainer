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
from app.routers.whatsapp import (  # noqa: E402
    _CANCEL_TEXT,
    _HELP_TEXT,
    _NO_ACTIVE_SESSION_TEXT,
    _cancel_lesson,
    dispatch_message,
)
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

_PATCH_GET_CONVO_STATE = "app.routers.whatsapp._get_convo_state"
_PATCH_SET_MODE = "app.routers.whatsapp._set_mode"
_PATCH_SEND = "app.routers.whatsapp.send_message"
_PATCH_START_LESSON = "app.routers.whatsapp.lesson_session.start_lesson"
_PATCH_HANDLE_EXERCISE = "app.routers.whatsapp.lesson_session.handle_exercise_answer"
_PATCH_LOOKUP = "app.routers.whatsapp._lookup"
_PATCH_CANCEL = "app.routers.whatsapp._cancel_lesson"


# ---------------------------------------------------------------------------
# help keyword
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_help_sends_help_text():
    with (
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_GET_CONVO_STATE, new_callable=AsyncMock) as mock_state,
    ):
        await dispatch_message(_make_message("help"))

    mock_send.assert_awaited_once_with("14155550001", _HELP_TEXT)
    mock_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_help_case_insensitive():
    with (
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_GET_CONVO_STATE, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_message("HELP"))

    mock_send.assert_awaited_once()


# ---------------------------------------------------------------------------
# cancel / stop keyword
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_triggers_cancel_lesson():
    with patch(_PATCH_CANCEL, new_callable=AsyncMock) as mock_cancel:
        await dispatch_message(_make_message("cancel"))

    mock_cancel.assert_awaited_once_with("14155550001")


@pytest.mark.asyncio
async def test_stop_triggers_cancel_lesson():
    with patch(_PATCH_CANCEL, new_callable=AsyncMock) as mock_cancel:
        await dispatch_message(_make_message("stop"))

    mock_cancel.assert_awaited_once_with("14155550001")


@pytest.mark.asyncio
async def test_cancel_does_not_hit_rate_limiter():
    """cancel/stop bypasses the rate limiter (no AI call)."""
    with (
        patch(_PATCH_CANCEL, new_callable=AsyncMock),
        patch("app.routers.whatsapp.rate_limiter.is_allowed") as mock_rl,
    ):
        await dispatch_message(_make_message("cancel"))

    mock_rl.assert_not_called()


_PATCH_GET_ACTIVE_CONVO = "app.routers.whatsapp._get_active_convo"
_PATCH_DB_SESSION = "app.routers.whatsapp.AsyncSessionLocal"


def _mock_db_session(convo):
    """Return a mock AsyncSessionLocal that yields *convo* from _get_active_convo."""
    db = AsyncMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    return db


@pytest.mark.asyncio
async def test_cancel_lesson_with_active_lesson_sends_cancel_text():
    convo = _make_convo(ConversationMode.lesson)
    db = _mock_db_session(convo)
    with (
        patch(_PATCH_DB_SESSION, return_value=db),
        patch(_PATCH_GET_ACTIVE_CONVO, new_callable=AsyncMock, return_value=convo),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
    ):
        await _cancel_lesson("14155550001")

    mock_send.assert_awaited_once_with("14155550001", _CANCEL_TEXT)


@pytest.mark.asyncio
async def test_cancel_lesson_with_active_review_sends_cancel_text():
    convo = _make_convo(ConversationMode.review)
    db = _mock_db_session(convo)
    with (
        patch(_PATCH_DB_SESSION, return_value=db),
        patch(_PATCH_GET_ACTIVE_CONVO, new_callable=AsyncMock, return_value=convo),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
    ):
        await _cancel_lesson("14155550001")

    mock_send.assert_awaited_once_with("14155550001", _CANCEL_TEXT)


@pytest.mark.asyncio
async def test_cancel_lesson_no_active_session_sends_nothing_to_cancel():
    db = _mock_db_session(None)
    with (
        patch(_PATCH_DB_SESSION, return_value=db),
        patch(_PATCH_GET_ACTIVE_CONVO, new_callable=AsyncMock, return_value=None),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
    ):
        await _cancel_lesson("14155550001")

    mock_send.assert_awaited_once_with("14155550001", _NO_ACTIVE_SESSION_TEXT)


@pytest.mark.asyncio
async def test_cancel_lesson_in_quick_lookup_mode_sends_nothing_to_cancel():
    convo = _make_convo(ConversationMode.quick_lookup)
    db = _mock_db_session(convo)
    with (
        patch(_PATCH_DB_SESSION, return_value=db),
        patch(_PATCH_GET_ACTIVE_CONVO, new_callable=AsyncMock, return_value=convo),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
    ):
        await _cancel_lesson("14155550001")

    mock_send.assert_awaited_once_with("14155550001", _NO_ACTIVE_SESSION_TEXT)


# ---------------------------------------------------------------------------
# lesson keyword
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lesson_keyword_calls_start_lesson():
    with patch(_PATCH_START_LESSON, new_callable=AsyncMock) as mock_start:
        await dispatch_message(_make_message("lesson"))

    mock_start.assert_awaited_once_with("14155550001", "everyday conversation")


@pytest.mark.asyncio
async def test_lesson_with_topic_passes_topic():
    with patch(_PATCH_START_LESSON, new_callable=AsyncMock) as mock_start:
        await dispatch_message(_make_message("lesson greetings"))

    mock_start.assert_awaited_once_with("14155550001", "greetings")


@pytest.mark.asyncio
async def test_lesson_keyword_does_not_query_mode():
    """lesson keyword short-circuits mode dispatch."""
    with (
        patch(_PATCH_START_LESSON, new_callable=AsyncMock),
        patch(_PATCH_GET_CONVO_STATE, new_callable=AsyncMock) as mock_state,
    ):
        await dispatch_message(_make_message("lesson"))

    mock_state.assert_not_awaited()


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
        patch(_PATCH_GET_CONVO_STATE, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None)),
        patch(_PATCH_LOOKUP, new_callable=AsyncMock, return_value="result") as mock_lkp,
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_SET_MODE, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_message("lookup "))

    mock_lkp.assert_awaited_once()


# ---------------------------------------------------------------------------
# Mode-based routing (no keyword)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bare_text_in_quick_lookup_mode_triggers_lookup():
    with (
        patch(_PATCH_GET_CONVO_STATE, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None)),
        patch(_PATCH_LOOKUP, new_callable=AsyncMock, return_value="res") as mock_lkp,
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_SET_MODE, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_message("how are you"))

    mock_lkp.assert_awaited_once_with("how are you")


@pytest.mark.asyncio
async def test_bare_text_in_lesson_mode_with_active_session_handles_exercise():
    """Bare text during an active lesson calls handle_exercise_answer."""
    active_ctx = {"exercises": [{"type": "mcq", "question": "q"}], "current_index": 0}
    with (
        patch(_PATCH_GET_CONVO_STATE, new_callable=AsyncMock,
              return_value=(ConversationMode.lesson, active_ctx)),
        patch(_PATCH_HANDLE_EXERCISE, new_callable=AsyncMock) as mock_exercise,
    ):
        await dispatch_message(_make_message("A"))

    mock_exercise.assert_awaited_once_with("14155550001", "A")


@pytest.mark.asyncio
async def test_bare_text_in_lesson_mode_no_session_starts_new_lesson():
    """Lesson mode with no active context starts a new lesson."""
    with (
        patch(_PATCH_GET_CONVO_STATE, new_callable=AsyncMock,
              return_value=(ConversationMode.lesson, None)),
        patch(_PATCH_START_LESSON, new_callable=AsyncMock) as mock_start,
    ):
        await dispatch_message(_make_message("food ordering"))

    mock_start.assert_awaited_once_with("14155550001", "everyday conversation")


@pytest.mark.asyncio
async def test_bare_text_in_lesson_mode_exhausted_session_starts_new_lesson():
    """Lesson mode with all exercises done starts a new lesson."""
    finished_ctx = {"exercises": [{"type": "mcq", "question": "q"}], "current_index": 1}
    with (
        patch(_PATCH_GET_CONVO_STATE, new_callable=AsyncMock,
              return_value=(ConversationMode.lesson, finished_ctx)),
        patch(_PATCH_START_LESSON, new_callable=AsyncMock) as mock_start,
    ):
        await dispatch_message(_make_message("something"))

    mock_start.assert_awaited_once_with("14155550001", "everyday conversation")


@pytest.mark.asyncio
async def test_no_mode_defaults_to_lookup():
    """When there is no active conversation, defaults to quick_lookup."""
    with (
        patch(_PATCH_GET_CONVO_STATE, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None)),
        patch(_PATCH_LOOKUP, new_callable=AsyncMock, return_value="res") as mock_lkp,
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_SET_MODE, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_message("thank you"))

    mock_lkp.assert_awaited_once_with("thank you")


# ---------------------------------------------------------------------------
# progress keyword
# ---------------------------------------------------------------------------

_PATCH_GET_PROGRESS = "app.routers.whatsapp.get_progress_summary"


@pytest.mark.asyncio
async def test_progress_calls_get_progress_summary():
    with (
        patch(_PATCH_GET_PROGRESS, new_callable=AsyncMock, return_value="📊 Your Progress\nLevel: 2/5") as mock_prog,
        patch(_PATCH_SEND, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_message("progress"))

    mock_prog.assert_awaited_once_with("14155550001")


@pytest.mark.asyncio
async def test_progress_sends_summary():
    summary = "📊 Your Progress\nLevel: 2/5"
    with (
        patch(_PATCH_GET_PROGRESS, new_callable=AsyncMock, return_value=summary),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
    ):
        await dispatch_message(_make_message("progress"))

    mock_send.assert_awaited_once_with("14155550001", summary)


@pytest.mark.asyncio
async def test_progress_case_insensitive():
    with (
        patch(_PATCH_GET_PROGRESS, new_callable=AsyncMock, return_value="summary"),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
    ):
        await dispatch_message(_make_message("PROGRESS"))

    mock_send.assert_awaited_once()


@pytest.mark.asyncio
async def test_progress_does_not_hit_rate_limiter():
    """progress bypasses the rate limiter (no AI call)."""
    with (
        patch(_PATCH_GET_PROGRESS, new_callable=AsyncMock, return_value="summary"),
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch("app.routers.whatsapp.rate_limiter.is_allowed") as mock_rl,
    ):
        await dispatch_message(_make_message("progress"))

    mock_rl.assert_not_called()


@pytest.mark.asyncio
async def test_progress_does_not_query_mode():
    """progress short-circuits mode dispatch."""
    with (
        patch(_PATCH_GET_PROGRESS, new_callable=AsyncMock, return_value="summary"),
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_GET_CONVO_STATE, new_callable=AsyncMock) as mock_state,
    ):
        await dispatch_message(_make_message("progress"))

    mock_state.assert_not_awaited()
