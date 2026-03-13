"""Tests for the SRS vocabulary review session service."""

import os
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test_access")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test_app_secret")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "test_phone_id")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")

from app.models.conversation import Conversation, ConversationMode  # noqa: E402
from app.services.review_session import (  # noqa: E402
    _build_feedback,
    _format_exercise,
    handle_review_answer,
    start_review,
)

PHONE = "14155550001"

_PATCH_SEND = "app.services.review_session.send_message"
_PATCH_DB = "app.services.review_session.AsyncSessionLocal"
_PATCH_SRS = "app.services.review_session.srs.record_review"
_PATCH_EVALUATE = "app.services.review_session.evaluate_answer"


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_format_exercise_en_to_kn():
    item = {
        "word": "how are you",
        "translations": {"roman": "hegiddira"},
        "direction": "en_to_kn",
        "question": "Translate to Kannada: how are you",
        "expected": "hegiddira",
    }
    msg = _format_exercise(item, index=1, total=3)
    assert "Word 1/3" in msg
    assert "Translate to Kannada: how are you" in msg


def test_format_exercise_kn_to_en():
    item = {
        "word": "how are you",
        "translations": {"roman": "hegiddira"},
        "direction": "kn_to_en",
        "question": "Translate to English: hegiddira",
        "expected": "how are you",
    }
    msg = _format_exercise(item, index=2, total=3)
    assert "Word 2/3" in msg
    assert "Translate to English: hegiddira" in msg


def test_build_feedback_correct():
    result = {"correct": True, "feedback": "Great!", "corrected_kannada": None}
    msg = _build_feedback(result, "expected")
    assert "\u2713" in msg
    assert "Great!" in msg


def test_build_feedback_incorrect_uses_corrected_kannada():
    result = {"correct": False, "feedback": "Wrong.", "corrected_kannada": "naanu"}
    msg = _build_feedback(result, "fallback")
    assert "\u2717" in msg
    assert "naanu" in msg


def test_build_feedback_incorrect_falls_back_to_expected():
    result = {"correct": False, "feedback": "Wrong.", "corrected_kannada": None}
    msg = _build_feedback(result, "fallback_answer")
    assert "fallback_answer" in msg


# ---------------------------------------------------------------------------
# start_review
# ---------------------------------------------------------------------------


def _make_db_ctx(learner=None, rows=None, next_date=None):
    """Build a mock AsyncSessionLocal context manager."""
    mock_session = AsyncMock()

    # Chain multiple execute calls: first for learner, then for due items, then for min date
    results = []

    # Learner result
    learner_result = MagicMock()
    learner_result.scalar_one_or_none.return_value = learner
    results.append(learner_result)

    if learner is not None:
        if rows is not None:
            # Due items result
            due_result = MagicMock()
            due_result.all.return_value = rows
            results.append(due_result)

            if not rows:
                # Min date result
                min_result = MagicMock()
                min_result.scalar_one_or_none.return_value = next_date
                results.append(min_result)

    mock_session.execute = AsyncMock(side_effect=results)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    # Simulate _get_active_convo returning None (will create new convo)
    # This is called inside _get_or_create_convo

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, mock_session


@pytest.mark.asyncio
async def test_start_review_no_learner():
    with (
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_DB) as mock_db_cls,
    ):
        ctx, session = _make_db_ctx(learner=None)
        mock_db_cls.return_value = ctx

        await start_review(PHONE)

        mock_send.assert_awaited_once()
        msg = mock_send.call_args[0][1]
        assert "lesson" in msg.lower()


@pytest.mark.asyncio
async def test_start_review_no_due_items_with_next_date():
    learner = MagicMock()
    learner.id = 1

    with (
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_DB) as mock_db_cls,
    ):
        next_date = date(2026, 3, 20)
        ctx, session = _make_db_ctx(learner=learner, rows=[], next_date=next_date)
        mock_db_cls.return_value = ctx

        await start_review(PHONE)

        mock_send.assert_awaited_once()
        msg = mock_send.call_args[0][1]
        assert "No words due" in msg
        assert "Mar 20, 2026" in msg


@pytest.mark.asyncio
async def test_start_review_no_due_items_no_vocabulary():
    learner = MagicMock()
    learner.id = 1

    with (
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_DB) as mock_db_cls,
    ):
        ctx, session = _make_db_ctx(learner=learner, rows=[], next_date=None)
        mock_db_cls.return_value = ctx

        await start_review(PHONE)

        mock_send.assert_awaited_once()
        msg = mock_send.call_args[0][1]
        assert "lesson" in msg.lower()


# ---------------------------------------------------------------------------
# handle_review_answer
# ---------------------------------------------------------------------------


def _make_convo_ctx(convo):
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


def _make_convo(mode, lesson_context):
    convo = MagicMock(spec=Conversation)
    convo.mode = mode
    convo.lesson_context = lesson_context
    return convo


@pytest.mark.asyncio
async def test_handle_review_answer_no_active_session():
    with (
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_DB) as mock_db_cls,
    ):
        ctx = _make_convo_ctx(None)
        mock_db_cls.return_value = ctx

        await handle_review_answer(PHONE, "some answer")

        mock_send.assert_awaited_once()
        msg = mock_send.call_args[0][1]
        assert "review" in msg.lower()


@pytest.mark.asyncio
async def test_handle_review_answer_correct_advances_index():
    items = [
        {
            "lv_id": 1, "word": "how are you", "translations": {"roman": "hegiddira"},
            "direction": "en_to_kn", "question": "Translate to Kannada: how are you", "expected": "hegiddira",
        },
        {
            "lv_id": 2, "word": "it is good", "translations": {"roman": "chennagide"},
            "direction": "kn_to_en", "question": "Translate to English: chennagide", "expected": "it is good",
        },
    ]
    ctx_data = {"items": items, "current_index": 0, "reviewed_count": 0}
    convo = _make_convo(ConversationMode.review, ctx_data)

    eval_result = {"correct": True, "score": 1.0, "feedback": "Perfect!", "corrected_kannada": None}

    with (
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_DB) as mock_db_cls,
        patch(_PATCH_EVALUATE, new_callable=AsyncMock, return_value=eval_result),
        patch(_PATCH_SRS, new_callable=AsyncMock),
    ):
        # First call for loading context, second for updating
        ctx = _make_convo_ctx(convo)
        mock_db_cls.return_value = ctx

        await handle_review_answer(PHONE, "hegiddira")

    calls = mock_send.call_args_list
    # feedback + next exercise
    assert len(calls) == 2
    feedback_msg = calls[0][0][1]
    assert "\u2713" in feedback_msg
    next_exercise_msg = calls[1][0][1]
    assert "Word 2/2" in next_exercise_msg


@pytest.mark.asyncio
async def test_handle_review_answer_last_item_sends_summary():
    items = [
        {
            "lv_id": 1, "word": "how are you", "translations": {"roman": "hegiddira"},
            "direction": "en_to_kn", "question": "Translate to Kannada: how are you", "expected": "hegiddira",
        },
    ]
    ctx_data = {"items": items, "current_index": 0, "reviewed_count": 0}
    convo = _make_convo(ConversationMode.review, ctx_data)

    eval_result = {"correct": True, "score": 1.0, "feedback": "Correct!", "corrected_kannada": None}

    with (
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_DB) as mock_db_cls,
        patch(_PATCH_EVALUATE, new_callable=AsyncMock, return_value=eval_result),
        patch(_PATCH_SRS, new_callable=AsyncMock),
    ):
        ctx = _make_convo_ctx(convo)
        mock_db_cls.return_value = ctx

        await handle_review_answer(PHONE, "hegiddira")

    calls = mock_send.call_args_list
    # feedback + summary
    assert len(calls) == 2
    summary_msg = calls[1][0][1]
    assert "Review complete" in summary_msg
    assert "1 word" in summary_msg


@pytest.mark.asyncio
async def test_handle_review_answer_quality_maps_score_to_sm2():
    items = [{
        "lv_id": 42, "word": "hello", "translations": {"roman": "namaskara"},
        "direction": "en_to_kn", "question": "Translate to Kannada: hello", "expected": "namaskara",
    }]
    ctx_data = {"items": items, "current_index": 0, "reviewed_count": 0}
    convo = _make_convo(ConversationMode.review, ctx_data)

    eval_result = {"correct": False, "score": 0.4, "feedback": "Almost.", "corrected_kannada": None}

    with (
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_DB) as mock_db_cls,
        patch(_PATCH_EVALUATE, new_callable=AsyncMock, return_value=eval_result),
        patch(_PATCH_SRS, new_callable=AsyncMock) as mock_record,
    ):
        ctx = _make_convo_ctx(convo)
        mock_db_cls.return_value = ctx

        await handle_review_answer(PHONE, "hi")

    # score 0.4 → quality round(0.4 * 5) = 2
    mock_record.assert_awaited_once()
    _, kwargs = mock_record.call_args
    # positional: db, lv_id, quality
    call_args = mock_record.call_args[0]
    assert call_args[1] == 42  # lv_id
    assert call_args[2] == 2   # quality
