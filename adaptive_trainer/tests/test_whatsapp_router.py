"""Tests for the WhatsApp message routing dispatcher."""

import asyncio
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
    _GATEWAY_HELP_TEXT,
    _HELP_TEXT,
    _INPUT_TOO_LONG_TEXT,
    _LESSON_HELP_TEXT,
    _LEVEL_CHANGED_TEXT,
    _LEVEL_INVALID_TEXT,
    _MAX_INPUT_LENGTH,
    _NO_ACTIVE_SESSION_TEXT,
    _REVIEW_HELP_TEXT,
    _TYPO_MAP,
    _cancel_lesson,
    _correct_typo,
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

_PATCH_LOAD_CONVO = "app.routers.whatsapp._load_convo_and_expire"
_PATCH_SET_MODE = "app.routers.whatsapp._set_mode"
_PATCH_SEND = "app.routers.whatsapp.send_message"
_PATCH_START_LESSON = "app.routers.whatsapp.lesson_session.start_lesson"
_PATCH_HANDLE_EXERCISE = "app.routers.whatsapp.lesson_session.handle_exercise_answer"
_PATCH_LOOKUP = "app.routers.whatsapp._lookup"
_PATCH_CANCEL = "app.routers.whatsapp._cancel_lesson"


# ---------------------------------------------------------------------------
# max input length
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_message_over_max_length_is_rejected():
    long_text = "a" * (_MAX_INPUT_LENGTH + 1)
    with patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send:
        await dispatch_message(_make_message(long_text))

    mock_send.assert_awaited_once_with("14155550001", _INPUT_TOO_LONG_TEXT)


@pytest.mark.asyncio
async def test_message_at_max_length_is_accepted():
    exact_text = "a" * _MAX_INPUT_LENGTH
    with (
        patch("app.routers.whatsapp._load_convo_and_expire", new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_LOOKUP, new_callable=AsyncMock, return_value="res"),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_SET_MODE, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_message(exact_text))

    # Should NOT have sent the too-long message
    for call in mock_send.await_args_list:
        assert call.args[1] != _INPUT_TOO_LONG_TEXT


# ---------------------------------------------------------------------------
# help keyword
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_help_sends_generic_help_in_quick_lookup():
    with (
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
    ):
        await dispatch_message(_make_message("help"))

    mock_send.assert_awaited_once_with("14155550001", _HELP_TEXT)


@pytest.mark.asyncio
async def test_help_case_insensitive():
    with (
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
    ):
        await dispatch_message(_make_message("HELP"))

    mock_send.assert_awaited_once()


@pytest.mark.asyncio
async def test_help_in_lesson_mode_shows_lesson_help():
    with (
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.lesson, None, False)),
    ):
        await dispatch_message(_make_message("help"))

    mock_send.assert_awaited_once_with("14155550001", _LESSON_HELP_TEXT)


@pytest.mark.asyncio
async def test_help_in_review_mode_shows_review_help():
    with (
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.review, None, False)),
    ):
        await dispatch_message(_make_message("help"))

    mock_send.assert_awaited_once_with("14155550001", _REVIEW_HELP_TEXT)


@pytest.mark.asyncio
async def test_help_in_gateway_mode_shows_gateway_help():
    with (
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.gateway_test, None, False)),
    ):
        await dispatch_message(_make_message("help"))

    mock_send.assert_awaited_once_with("14155550001", _GATEWAY_HELP_TEXT)


# ---------------------------------------------------------------------------
# cancel / stop keyword
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_triggers_cancel_lesson():
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_CANCEL, new_callable=AsyncMock) as mock_cancel,
    ):
        await dispatch_message(_make_message("cancel"))

    mock_cancel.assert_awaited_once_with("14155550001")


@pytest.mark.asyncio
async def test_stop_triggers_cancel_lesson():
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_CANCEL, new_callable=AsyncMock) as mock_cancel,
    ):
        await dispatch_message(_make_message("stop"))

    mock_cancel.assert_awaited_once_with("14155550001")


@pytest.mark.asyncio
async def test_cancel_does_not_hit_rate_limiter():
    """cancel/stop bypasses the rate limiter (no AI call)."""
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
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
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_START_LESSON, new_callable=AsyncMock) as mock_start,
    ):
        await dispatch_message(_make_message("lesson"))

    mock_start.assert_awaited_once_with("14155550001", "everyday conversation")


@pytest.mark.asyncio
async def test_lesson_with_topic_passes_topic():
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_START_LESSON, new_callable=AsyncMock) as mock_start,
    ):
        await dispatch_message(_make_message("lesson greetings"))

    mock_start.assert_awaited_once_with("14155550001", "greetings")


@pytest.mark.asyncio
async def test_lesson_keyword_short_circuits_mode_dispatch():
    """lesson keyword short-circuits mode dispatch (no exercise handler called)."""
    with (
        patch(_PATCH_START_LESSON, new_callable=AsyncMock) as mock_start,
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_HANDLE_EXERCISE, new_callable=AsyncMock) as mock_exercise,
    ):
        await dispatch_message(_make_message("lesson"))

    mock_start.assert_awaited_once()
    mock_exercise.assert_not_awaited()


# ---------------------------------------------------------------------------
# lookup keyword
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lookup_keyword_triggers_lookup():
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_LOOKUP, new_callable=AsyncMock, return_value="namaskara — greeting") as mock_lkp,
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_SET_MODE, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_message("lookup hello"))

    mock_lkp.assert_awaited_once_with("hello")


@pytest.mark.asyncio
async def test_lookup_sends_result_and_sets_mode():
    result = "namaskara — greeting"
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
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
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
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
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
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
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.lesson, active_ctx, False)),
        patch(_PATCH_HANDLE_EXERCISE, new_callable=AsyncMock) as mock_exercise,
    ):
        await dispatch_message(_make_message("A"))

    mock_exercise.assert_awaited_once_with("14155550001", "A")


@pytest.mark.asyncio
async def test_bare_text_in_lesson_mode_no_session_starts_new_lesson():
    """Lesson mode with no active context starts a new lesson."""
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.lesson, None, False)),
        patch(_PATCH_START_LESSON, new_callable=AsyncMock) as mock_start,
    ):
        await dispatch_message(_make_message("food ordering"))

    mock_start.assert_awaited_once_with("14155550001", "everyday conversation")


@pytest.mark.asyncio
async def test_bare_text_in_lesson_mode_exhausted_session_starts_new_lesson():
    """Lesson mode with all exercises done starts a new lesson."""
    finished_ctx = {"exercises": [{"type": "mcq", "question": "q"}], "current_index": 1}
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.lesson, finished_ctx, False)),
        patch(_PATCH_START_LESSON, new_callable=AsyncMock) as mock_start,
    ):
        await dispatch_message(_make_message("something"))

    mock_start.assert_awaited_once_with("14155550001", "everyday conversation")


@pytest.mark.asyncio
async def test_no_mode_defaults_to_lookup():
    """When there is no active conversation, defaults to quick_lookup."""
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
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
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_GET_PROGRESS, new_callable=AsyncMock, return_value="Your Progress\nLevel: 2/5") as mock_prog,
        patch(_PATCH_SEND, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_message("progress"))

    mock_prog.assert_awaited_once_with("14155550001")


@pytest.mark.asyncio
async def test_progress_sends_summary():
    summary = "Your Progress\nLevel: 2/5"
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_GET_PROGRESS, new_callable=AsyncMock, return_value=summary),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
    ):
        await dispatch_message(_make_message("progress"))

    mock_send.assert_awaited_once_with("14155550001", summary)


@pytest.mark.asyncio
async def test_progress_case_insensitive():
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_GET_PROGRESS, new_callable=AsyncMock, return_value="summary"),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
    ):
        await dispatch_message(_make_message("PROGRESS"))

    mock_send.assert_awaited_once()


@pytest.mark.asyncio
async def test_progress_does_not_hit_rate_limiter():
    """progress bypasses the rate limiter (no AI call)."""
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_GET_PROGRESS, new_callable=AsyncMock, return_value="summary"),
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch("app.routers.whatsapp.rate_limiter.is_allowed") as mock_rl,
    ):
        await dispatch_message(_make_message("progress"))

    mock_rl.assert_not_called()


@pytest.mark.asyncio
async def test_progress_short_circuits_mode_dispatch():
    """progress short-circuits mode dispatch (no lookup called)."""
    with (
        patch(_PATCH_GET_PROGRESS, new_callable=AsyncMock, return_value="summary"),
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_LOOKUP, new_callable=AsyncMock) as mock_lkp,
    ):
        await dispatch_message(_make_message("progress"))

    mock_lkp.assert_not_awaited()


# ---------------------------------------------------------------------------
# typo tolerance
# ---------------------------------------------------------------------------


class TestCorrectTypo:
    """Unit tests for the _correct_typo helper."""

    @pytest.mark.parametrize("typo,expected", [
        ("hlep", "help"),
        ("hepl", "help"),
        ("hep", "help"),
        ("halp", "help"),
        ("lessn", "lesson"),
        ("leson", "lesson"),
        ("leeson", "lesson"),
        ("reveiw", "review"),
        ("reviw", "review"),
        ("progres", "progress"),
        ("progess", "progress"),
        ("cancle", "cancel"),
        ("cancal", "cancel"),
        ("stp", "stop"),
        ("sotp", "stop"),
        ("skp", "skip"),
        ("skpi", "skip"),
        ("topcs", "topics"),
        ("gatway", "gateway"),
        ("lokup", "lookup"),
    ])
    def test_single_word_typos(self, typo, expected):
        assert _correct_typo(typo) == expected

    @pytest.mark.parametrize("typo,expected", [
        ("lessn greetings", "lesson greetings"),
        ("leson food ordering", "lesson food ordering"),
        ("lokup hello", "lookup hello"),
        ("looup namaste", "lookup namaste"),
    ])
    def test_prefix_command_typos(self, typo, expected):
        assert _correct_typo(typo) == expected

    def test_correct_words_unchanged(self):
        for word in ("help", "lesson", "review", "progress", "cancel", "stop",
                     "skip", "topics", "gateway", "lookup", "level"):
            assert _correct_typo(word) == word

    def test_unknown_words_unchanged(self):
        assert _correct_typo("hello") == "hello"
        assert _correct_typo("namaste") == "namaste"
        assert _correct_typo("how are you") == "how are you"

    def test_typo_map_has_no_collisions_with_valid_commands(self):
        """No typo should map to a different valid command."""
        valid = {"help", "lesson", "review", "progress", "cancel", "stop",
                 "skip", "topics", "gateway", "lookup", "level"}
        for typo, target in _TYPO_MAP.items():
            assert typo not in valid, f"typo '{typo}' collides with valid command"
            assert target in valid, f"typo '{typo}' maps to unknown command '{target}'"


@pytest.mark.asyncio
async def test_typo_hlep_triggers_help():
    with (
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
    ):
        await dispatch_message(_make_message("hlep"))

    mock_send.assert_awaited_once_with("14155550001", _HELP_TEXT)


@pytest.mark.asyncio
async def test_typo_cancle_triggers_cancel():
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_CANCEL, new_callable=AsyncMock) as mock_cancel,
    ):
        await dispatch_message(_make_message("cancle"))

    mock_cancel.assert_awaited_once_with("14155550001")


@pytest.mark.asyncio
async def test_typo_lessn_with_topic_starts_lesson():
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_START_LESSON, new_callable=AsyncMock) as mock_start,
    ):
        await dispatch_message(_make_message("lessn greetings"))

    mock_start.assert_awaited_once_with("14155550001", "greetings")


@pytest.mark.asyncio
async def test_typo_reveiw_triggers_review():
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch("app.routers.whatsapp.review_session.start_review", new_callable=AsyncMock) as mock_review,
    ):
        await dispatch_message(_make_message("reveiw"))

    mock_review.assert_awaited_once_with("14155550001")


@pytest.mark.asyncio
async def test_typo_progres_triggers_progress():
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_GET_PROGRESS, new_callable=AsyncMock, return_value="stats") as mock_prog,
        patch(_PATCH_SEND, new_callable=AsyncMock),
    ):
        await dispatch_message(_make_message("progres"))

    mock_prog.assert_awaited_once_with("14155550001")


# ---------------------------------------------------------------------------
# Per-user lock serialization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_messages_from_same_user_are_serialized():
    """Two messages from the same phone must not overlap execution."""
    execution_order: list[str] = []

    async def slow_load_convo(phone):
        execution_order.append("enter")
        await asyncio.sleep(0.05)
        execution_order.append("exit")
        return (ConversationMode.quick_lookup, None, False)

    with (
        patch(_PATCH_LOAD_CONVO, side_effect=slow_load_convo),
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_LOOKUP, new_callable=AsyncMock, return_value="result"),
        patch(_PATCH_SET_MODE, new_callable=AsyncMock),
        patch("app.routers.whatsapp.rate_limiter.is_allowed", return_value=True),
    ):
        msg1 = _make_message("hello", phone="same_user")
        msg2 = _make_message("world", phone="same_user")
        await asyncio.gather(dispatch_message(msg1), dispatch_message(msg2))

    # With serialization: enter, exit, enter, exit (no interleaving)
    assert execution_order == ["enter", "exit", "enter", "exit"]


@pytest.mark.asyncio
async def test_concurrent_messages_from_different_users_run_in_parallel():
    """Messages from different phone numbers should NOT block each other."""
    active_count = 0
    max_concurrent = 0

    async def tracking_load_convo(phone):
        nonlocal active_count, max_concurrent
        active_count += 1
        max_concurrent = max(max_concurrent, active_count)
        await asyncio.sleep(0.05)
        active_count -= 1
        return (ConversationMode.quick_lookup, None, False)

    with (
        patch(_PATCH_LOAD_CONVO, side_effect=tracking_load_convo),
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_LOOKUP, new_callable=AsyncMock, return_value="result"),
        patch(_PATCH_SET_MODE, new_callable=AsyncMock),
        patch("app.routers.whatsapp.rate_limiter.is_allowed", return_value=True),
    ):
        msg1 = _make_message("hello", phone="user_a")
        msg2 = _make_message("world", phone="user_b")
        await asyncio.gather(dispatch_message(msg1), dispatch_message(msg2))

    # Different users should have run concurrently
    assert max_concurrent == 2


# ---------------------------------------------------------------------------
# level command
# ---------------------------------------------------------------------------

_PATCH_HANDLE_LEVEL = "app.routers.whatsapp._handle_level_change"


@pytest.mark.asyncio
async def test_level_command_dispatches_to_handler():
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_HANDLE_LEVEL, new_callable=AsyncMock) as mock_level,
    ):
        await dispatch_message(_make_message("level 3"))

    mock_level.assert_awaited_once_with("14155550001", "3")


@pytest.mark.asyncio
async def test_level_command_case_insensitive():
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_HANDLE_LEVEL, new_callable=AsyncMock) as mock_level,
    ):
        await dispatch_message(_make_message("LEVEL 2"))

    mock_level.assert_awaited_once_with("14155550001", "2")


@pytest.mark.asyncio
async def test_level_does_not_hit_rate_limiter():
    """level bypasses the rate limiter (no AI call)."""
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_HANDLE_LEVEL, new_callable=AsyncMock),
        patch("app.routers.whatsapp.rate_limiter.is_allowed") as mock_rl,
    ):
        await dispatch_message(_make_message("level 1"))

    mock_rl.assert_not_called()


@pytest.mark.asyncio
async def test_level_invalid_non_numeric():
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
    ):
        await dispatch_message(_make_message("level abc"))

    mock_send.assert_awaited_once_with("14155550001", _LEVEL_INVALID_TEXT)


@pytest.mark.asyncio
async def test_level_out_of_range_too_high():
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
    ):
        await dispatch_message(_make_message("level 5"))

    mock_send.assert_awaited_once_with("14155550001", _LEVEL_INVALID_TEXT)


@pytest.mark.asyncio
async def test_level_out_of_range_negative():
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
    ):
        await dispatch_message(_make_message("level -1"))

    mock_send.assert_awaited_once_with("14155550001", _LEVEL_INVALID_TEXT)


@pytest.mark.asyncio
async def test_level_valid_updates_learner():
    learner = MagicMock()
    learner.current_ring = 0
    learner.level = 1

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = learner

    db = AsyncMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    db.execute = AsyncMock(return_value=result_mock)
    db.commit = AsyncMock()

    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_DB_SESSION, return_value=db),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
    ):
        await dispatch_message(_make_message("level 3"))

    assert learner.current_ring == 3
    assert learner.level == 4
    mock_send.assert_awaited_once_with("14155550001", _LEVEL_CHANGED_TEXT.format(ring=3))


@pytest.mark.asyncio
async def test_level_boundary_zero():
    learner = MagicMock()
    learner.current_ring = 2
    learner.level = 3

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = learner

    db = AsyncMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    db.execute = AsyncMock(return_value=result_mock)
    db.commit = AsyncMock()

    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_DB_SESSION, return_value=db),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
    ):
        await dispatch_message(_make_message("level 0"))

    assert learner.current_ring == 0
    assert learner.level == 1
    mock_send.assert_awaited_once_with("14155550001", _LEVEL_CHANGED_TEXT.format(ring=0))


@pytest.mark.asyncio
async def test_level_boundary_four():
    learner = MagicMock()
    learner.current_ring = 0
    learner.level = 1

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = learner

    db = AsyncMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    db.execute = AsyncMock(return_value=result_mock)
    db.commit = AsyncMock()

    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_DB_SESSION, return_value=db),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
    ):
        await dispatch_message(_make_message("level 4"))

    assert learner.current_ring == 4
    assert learner.level == 5
    mock_send.assert_awaited_once_with("14155550001", _LEVEL_CHANGED_TEXT.format(ring=4))


@pytest.mark.asyncio
async def test_typo_lvl_triggers_level():
    with (
        patch(_PATCH_LOAD_CONVO, new_callable=AsyncMock,
              return_value=(ConversationMode.quick_lookup, None, False)),
        patch(_PATCH_HANDLE_LEVEL, new_callable=AsyncMock) as mock_level,
    ):
        await dispatch_message(_make_message("lvl 2"))

    mock_level.assert_awaited_once_with("14155550001", "2")
