"""Happy-path tests for review answer handling and gateway turn handling.

These test the full dispatch through handle_review_answer and handle_gateway_turn
to ensure the core flows work end-to-end (with mocked DB and AI).
"""

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
from app.services.review_session import handle_review_answer  # noqa: E402
from app.services.gateway_session import handle_gateway_turn  # noqa: E402

PHONE = "14155550001"

_REVIEW_SEND = "app.services.review_session.send_message"
_REVIEW_DB = "app.services.review_session.AsyncSessionLocal"
_REVIEW_SRS = "app.services.review_session.srs.record_review"
_REVIEW_EVALUATE = "app.services.review_session.evaluate_answer"
_REVIEW_STREAK = "app.services.review_session.record_session_streak"

_GATEWAY_SEND = "app.services.gateway_session.send_message"
_GATEWAY_DB = "app.services.gateway_session.AsyncSessionLocal"
_GATEWAY_ASK = "app.services.gateway_session.ask_sonnet"
_GATEWAY_GET_CONVO = "app.services.gateway_session._get_active_convo"


def _mock_db_ctx(convo):
    """Build a mock AsyncSessionLocal that returns the given convo."""
    mock_session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = convo
    mock_session.execute = AsyncMock(return_value=result)
    mock_session.commit = AsyncMock()

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


# ---------------------------------------------------------------------------
# Review happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_answer_correct_sends_feedback_and_next_exercise():
    """A correct answer sends feedback, then the next exercise."""
    items = [
        {
            "lv_id": 1, "word": "namaskara", "translations": {"roman": "hello"},
            "unit_id": 1,
            "direction": "en_to_kn", "question": "Translate to Kannada: hello",
            "expected": "namaskara",
        },
        {
            "lv_id": 2, "word": "hegiddira", "translations": {"roman": "how are you"},
            "unit_id": 1,
            "direction": "kn_to_en", "question": "Translate to English: how are you",
            "expected": "hegiddira",
        },
    ]
    ctx_data = {"items": items, "current_index": 0, "reviewed_count": 0, "total_due": 2}
    convo = MagicMock(spec=Conversation)
    convo.mode = ConversationMode.review
    convo.lesson_context = ctx_data

    eval_result = {"correct": True, "score": 1.0, "feedback": "Perfect!", "corrected_kannada": None}

    with (
        patch(_REVIEW_SEND, new_callable=AsyncMock) as mock_send,
        patch(_REVIEW_DB) as mock_db_cls,
        patch(_REVIEW_EVALUATE, new_callable=AsyncMock, return_value=eval_result),
        patch(_REVIEW_SRS, new_callable=AsyncMock),
    ):
        mock_db_cls.return_value = _mock_db_ctx(convo)
        await handle_review_answer(PHONE, "namaskara")

    calls = mock_send.call_args_list
    assert len(calls) == 2, f"Expected 2 messages (feedback + next), got {len(calls)}"
    # First message is feedback
    assert "\u2713" in calls[0][0][1]
    # Second message is next exercise
    assert "Word 2/2" in calls[1][0][1]


@pytest.mark.asyncio
async def test_review_answer_wrong_sends_correction():
    """An incorrect answer sends the correct answer in feedback."""
    items = [
        {
            "lv_id": 1, "word": "namaskara", "translations": {"roman": "hello"},
            "unit_id": 1,
            "direction": "en_to_kn", "question": "Translate to Kannada: hello",
            "expected": "namaskara",
        },
        {
            "lv_id": 2, "word": "foo", "translations": {"roman": "bar"},
            "unit_id": 1,
            "direction": "en_to_kn", "question": "q2", "expected": "bar",
        },
    ]
    ctx_data = {"items": items, "current_index": 0, "reviewed_count": 0, "total_due": 2}
    convo = MagicMock(spec=Conversation)
    convo.mode = ConversationMode.review
    convo.lesson_context = ctx_data

    eval_result = {"correct": False, "score": 0.2, "feedback": "Not quite.", "corrected_kannada": None}

    with (
        patch(_REVIEW_SEND, new_callable=AsyncMock) as mock_send,
        patch(_REVIEW_DB) as mock_db_cls,
        patch(_REVIEW_EVALUATE, new_callable=AsyncMock, return_value=eval_result),
        patch(_REVIEW_SRS, new_callable=AsyncMock),
    ):
        mock_db_cls.return_value = _mock_db_ctx(convo)
        await handle_review_answer(PHONE, "wrong answer")

    feedback_msg = mock_send.call_args_list[0][0][1]
    assert "\u2717" in feedback_msg
    assert "namaskara" in feedback_msg


@pytest.mark.asyncio
async def test_review_answer_skip_records_zero_quality():
    """Typing 'skip' should record quality=0 and move on."""
    items = [
        {
            "lv_id": 10, "word": "foo", "translations": {"roman": "bar"},
            "unit_id": 1,
            "direction": "en_to_kn", "question": "Translate: bar",
            "expected": "foo",
        },
        {
            "lv_id": 11, "word": "baz", "translations": {"roman": "qux"},
            "unit_id": 1,
            "direction": "en_to_kn", "question": "Translate: qux",
            "expected": "baz",
        },
    ]
    ctx_data = {"items": items, "current_index": 0, "reviewed_count": 0, "total_due": 2}
    convo = MagicMock(spec=Conversation)
    convo.mode = ConversationMode.review
    convo.lesson_context = ctx_data

    with (
        patch(_REVIEW_SEND, new_callable=AsyncMock) as mock_send,
        patch(_REVIEW_DB) as mock_db_cls,
        patch(_REVIEW_SRS, new_callable=AsyncMock) as mock_srs,
    ):
        mock_db_cls.return_value = _mock_db_ctx(convo)
        await handle_review_answer(PHONE, "skip")

    # SRS should be called with quality=0
    mock_srs.assert_awaited_once()
    call_args = mock_srs.call_args
    assert call_args[0][2] == 0  # quality


# ---------------------------------------------------------------------------
# Gateway happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gateway_turn_mid_conversation():
    """A mid-conversation turn generates AI response and sends it."""
    ctx = {
        "ring": 0,
        "scenario_title": "Order food at a darshini",
        "system_prompt": "You are a darshini server...",
        "expected_turns": 4,
        "evaluation_criteria": ["Uses greeting"],
        "turns": [
            {"role": "assistant", "content": "Namaskara! Yenu beku?"},
        ],
        "turn_count": 0,
    }
    convo = MagicMock(spec=Conversation)
    convo.mode = ConversationMode.gateway_test
    convo.lesson_context = ctx

    with (
        patch(_GATEWAY_SEND, new_callable=AsyncMock) as mock_send,
        patch(_GATEWAY_GET_CONVO, new_callable=AsyncMock, return_value=convo),
        patch(_GATEWAY_DB) as mock_db_cls,
        patch(_GATEWAY_ASK, new_callable=AsyncMock, return_value="Sari, ondu dosa. Bere yenu beku?"),
    ):
        mock_db_cls.return_value = _mock_db_ctx(convo)
        await handle_gateway_turn(PHONE, "Ondu dosa kodi")

    mock_send.assert_called_once_with(PHONE, "Sari, ondu dosa. Bere yenu beku?")


@pytest.mark.asyncio
async def test_gateway_turn_final_triggers_evaluation():
    """When turn_count reaches expected_turns, evaluation runs."""
    ctx = {
        "ring": 0,
        "scenario_title": "Order food",
        "system_prompt": "You are a server",
        "expected_turns": 2,
        "evaluation_criteria": ["Uses greeting"],
        "turns": [
            {"role": "assistant", "content": "Namaskara!"},
            {"role": "user", "content": "Dosa kodi"},
        ],
        "turn_count": 1,
    }
    convo = MagicMock(spec=Conversation)
    convo.mode = ConversationMode.gateway_test
    convo.lesson_context = ctx

    eval_json = '{"passed": true, "score": 0.85, "feedback": "Good job!", "strengths": ["greeting"], "areas_to_improve": []}'

    with (
        patch(_GATEWAY_SEND, new_callable=AsyncMock) as mock_send,
        patch(_GATEWAY_GET_CONVO, new_callable=AsyncMock, return_value=convo),
        patch(_GATEWAY_DB) as mock_db_cls,
        patch(_GATEWAY_ASK, new_callable=AsyncMock, return_value=eval_json),
        patch("app.services.gateway_session.advance_ring", new_callable=AsyncMock, return_value=1),
    ):
        mock_db_cls.return_value = _mock_db_ctx(convo)
        await handle_gateway_turn(PHONE, "Dhanyavada!")

    # Should send evaluation results
    assert mock_send.call_count >= 1
    result_msg = mock_send.call_args_list[0][0][1]
    assert "PASSED" in result_msg
    assert "Good job!" in result_msg


@pytest.mark.asyncio
async def test_gateway_turn_corrupt_context_resets():
    """Corrupt gateway context clears state and sends error message."""
    convo = MagicMock(spec=Conversation)
    convo.mode = ConversationMode.gateway_test
    convo.lesson_context = {"bad": "context"}  # missing required keys

    with (
        patch(_GATEWAY_SEND, new_callable=AsyncMock) as mock_send,
        patch(_GATEWAY_GET_CONVO, new_callable=AsyncMock, return_value=convo),
        patch(_GATEWAY_DB) as mock_db_cls,
    ):
        mock_db_cls.return_value = _mock_db_ctx(convo)
        await handle_gateway_turn(PHONE, "hello")

    mock_send.assert_called_once()
    assert "No active gateway test" in mock_send.call_args[0][1]
