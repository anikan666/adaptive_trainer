"""Tests for the lesson session state machine service."""

import os
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test_access")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test_app_secret")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "test_phone_id")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")

from app.models.conversation import Conversation, ConversationMode  # noqa: E402
from app.services.exercise import ExerciseType  # noqa: E402
from app.services.lesson_session import (  # noqa: E402
    _build_feedback,
    _format_exercise,
    _resolve_mcq_answer,
    _shuffle_mcq_options,
    finish_lesson,
    handle_exercise_answer,
    start_lesson,
)

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

PHONE = "14155550001"

_MCQ_EXERCISE = {
    "type": "mcq",
    "question": "Which Kannada word means 'hello'?",
    "answer": "namaskara",
    "distractors": ["dhanyavada", "illa", "hogona"],
    "explanation": "namaskara is the standard Kannada greeting.",
    "shuffled_options": ["namaskara", "dhanyavada", "illa", "hogona"],
}

_FILL_EXERCISE = {
    "type": "fill_in_blank",
    "question": "Nanu _____ Kannada kaltini.",
    "answer": "chennagi",
    "distractors": ["ketta", "dodda", "chinna"],
    "explanation": "The sentence means 'I am learning Kannada well.'",
}

_TRANSLATION_EXERCISE = {
    "type": "translation",
    "question": "I want water.",
    "answer": "nange neeru beku",
    "distractors": [],
    "explanation": "'neeru' means water; 'beku' expresses wanting.",
}

_EVAL_CORRECT = {"correct": True, "score": 1.0, "feedback": "Correct!", "corrected_kannada": None}
_EVAL_WRONG = {
    "correct": False,
    "score": 0.0,
    "feedback": "Wrong answer.",
    "corrected_kannada": "namaskara",
}


def _make_convo(lesson_context=None, mode=ConversationMode.lesson):
    convo = MagicMock(spec=Conversation)
    convo.mode = mode
    convo.lesson_context = lesson_context
    return convo


def _make_ctx(exercises=None, current_index=0, scores=None, topic="greetings", level=2):
    return {
        "exercises": exercises or [_MCQ_EXERCISE],
        "current_index": current_index,
        "scores": scores or [],
        "topic": topic,
        "level": level,
    }


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------



def test_shuffle_mcq_options_adds_shuffled_options():
    ex = dict(_MCQ_EXERCISE)
    ex.pop("shuffled_options", None)
    _shuffle_mcq_options(ex)
    assert "shuffled_options" in ex
    assert set(ex["shuffled_options"]) == {"namaskara", "dhanyavada", "illa", "hogona"}
    assert len(ex["shuffled_options"]) == 4


def test_format_exercise_mcq():
    ex = dict(_MCQ_EXERCISE)
    ex["shuffled_options"] = ["namaskara", "dhanyavada", "illa", "hogona"]
    result = _format_exercise(ex, index=1, total=3)
    assert "Exercise 1/3" in result
    assert "A)" in result
    assert "namaskara" in result


def test_format_exercise_fill_in_blank():
    result = _format_exercise(_FILL_EXERCISE, index=2, total=4)
    assert "Fill in the blank" in result
    assert _FILL_EXERCISE["question"] in result


def test_format_exercise_translation():
    result = _format_exercise(_TRANSLATION_EXERCISE, index=3, total=4)
    assert "Translate to Kannada" in result
    assert _TRANSLATION_EXERCISE["question"] in result


def test_resolve_mcq_answer_resolves_letter():
    ex = {"shuffled_options": ["namaskara", "dhanyavada", "illa", "hogona"]}
    assert _resolve_mcq_answer(ex, ExerciseType.MCQ, "A") == "namaskara"
    assert _resolve_mcq_answer(ex, ExerciseType.MCQ, "b") == "dhanyavada"


def test_resolve_mcq_answer_passthrough_for_non_mcq():
    assert _resolve_mcq_answer({}, ExerciseType.FILL_IN_BLANK, "A") == "A"
    assert _resolve_mcq_answer({}, ExerciseType.TRANSLATION, "some text") == "some text"


def test_resolve_mcq_answer_passthrough_for_full_text():
    ex = {"shuffled_options": ["namaskara", "dhanyavada"]}
    assert _resolve_mcq_answer(ex, ExerciseType.MCQ, "namaskara") == "namaskara"


def test_build_feedback_correct():
    result = _build_feedback(_EVAL_CORRECT, _MCQ_EXERCISE)
    assert "\u2713" in result
    assert "Correct!" in result


def test_build_feedback_wrong_uses_corrected_kannada():
    result = _build_feedback(_EVAL_WRONG, _MCQ_EXERCISE)
    assert "\u2717" in result
    assert "namaskara" in result


def test_build_feedback_wrong_uses_exercise_answer_if_no_corrected():
    eval_result = {**_EVAL_WRONG, "corrected_kannada": None}
    result = _build_feedback(eval_result, _MCQ_EXERCISE)
    assert "namaskara" in result


# ---------------------------------------------------------------------------
# start_lesson
# ---------------------------------------------------------------------------

_PATCH_GET_LEVEL = "app.services.lesson_session._get_learner_ring_level"
_PATCH_GEN_LESSON = "app.services.lesson_session.generate_lesson"
_PATCH_GEN_BATCH = "app.services.lesson_session.generate_exercises_batch"
_PATCH_SEND = "app.services.lesson_session.send_message"
_PATCH_SESSION = "app.services.lesson_session.AsyncSessionLocal"
_PATCH_EVAL = "app.services.lesson_session.evaluate_answer"
_PATCH_GET_RING_LEVEL = "app.services.lesson_session._get_learner_ring_level"
_PATCH_GET_DUE = "app.services.lesson_session.get_due_items"
_PATCH_GET_LEARNER_ID = "app.services.lesson_session._get_learner_id"


def _make_db_context(convo):
    """Return a mock async context manager that provides a fake DB session."""
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=convo)))
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, mock_session


@pytest.mark.asyncio
async def test_start_lesson_gets_level_and_generates_lesson():
    convo = _make_convo()
    db_cm, _ = _make_db_context(convo)

    with (
        patch(_PATCH_GET_LEVEL, new_callable=AsyncMock, return_value=2) as mock_level,
        patch(_PATCH_GEN_LESSON, new_callable=AsyncMock, return_value="Intro text") as mock_lesson,
        patch(_PATCH_GEN_BATCH, new_callable=AsyncMock, return_value=[dict(_MCQ_EXERCISE)]),
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_SESSION, return_value=db_cm),
        patch(_PATCH_GET_DUE, new_callable=AsyncMock, return_value=[]),
        patch(_PATCH_GET_LEARNER_ID, new_callable=AsyncMock, return_value=None),
    ):
        await start_lesson(PHONE, "greetings")

    mock_level.assert_awaited_once_with(PHONE)
    mock_lesson.assert_awaited_once_with(level=2, topic="greetings", due_items=None)


@pytest.mark.asyncio
async def test_start_lesson_calls_generate_exercises_batch():
    convo = _make_convo()
    db_cm, _ = _make_db_context(convo)

    with (
        patch(_PATCH_GET_LEVEL, new_callable=AsyncMock, return_value=2),
        patch(_PATCH_GEN_LESSON, new_callable=AsyncMock, return_value="Intro text"),
        patch(_PATCH_GEN_BATCH, new_callable=AsyncMock, return_value=[dict(_MCQ_EXERCISE)]) as mock_batch,
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_SESSION, return_value=db_cm),
        patch(_PATCH_GET_DUE, new_callable=AsyncMock, return_value=[]),
        patch(_PATCH_GET_LEARNER_ID, new_callable=AsyncMock, return_value=None),
    ):
        await start_lesson(PHONE, "greetings")

    mock_batch.assert_awaited_once_with(
        count=4, level=2, topic="greetings", lesson_text="Intro text"
    )


@pytest.mark.asyncio
async def test_start_lesson_falls_back_to_level_1_on_missing_learner():
    convo = _make_convo()
    db_cm, _ = _make_db_context(convo)

    with (
        patch(_PATCH_GET_LEVEL, new_callable=AsyncMock, return_value=1),
        patch(_PATCH_GEN_LESSON, new_callable=AsyncMock, return_value="Intro") as mock_lesson,
        patch(_PATCH_GEN_BATCH, new_callable=AsyncMock, return_value=[dict(_MCQ_EXERCISE)]),
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_SESSION, return_value=db_cm),
        patch(_PATCH_GET_DUE, new_callable=AsyncMock, return_value=[]),
        patch(_PATCH_GET_LEARNER_ID, new_callable=AsyncMock, return_value=None),
    ):
        await start_lesson(PHONE, "greetings")

    mock_lesson.assert_awaited_once_with(level=1, topic="greetings", due_items=None)


@pytest.mark.asyncio
async def test_start_lesson_sends_intro_then_first_exercise():
    convo = _make_convo()
    db_cm, _ = _make_db_context(convo)

    with (
        patch(_PATCH_GET_LEVEL, new_callable=AsyncMock, return_value=1),
        patch(_PATCH_GEN_LESSON, new_callable=AsyncMock, return_value="Intro text"),
        patch(_PATCH_GEN_BATCH, new_callable=AsyncMock, return_value=[dict(_MCQ_EXERCISE)]),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_SESSION, return_value=db_cm),
        patch(_PATCH_GET_DUE, new_callable=AsyncMock, return_value=[]),
        patch(_PATCH_GET_LEARNER_ID, new_callable=AsyncMock, return_value=None),
    ):
        await start_lesson(PHONE, "greetings")

    assert mock_send.await_count == 3
    first_call_text = mock_send.call_args_list[0][0][1]
    assert first_call_text == "Starting your lesson on greetings..."
    second_call_text = mock_send.call_args_list[1][0][1]
    assert second_call_text == "Intro text"
    third_call_text = mock_send.call_args_list[2][0][1]
    assert "Exercise 1/1" in third_call_text


@pytest.mark.asyncio
async def test_start_lesson_passes_due_items_to_generate_lesson():
    convo = _make_convo()
    db_cm, _ = _make_db_context(convo)

    with (
        patch(_PATCH_GET_LEVEL, new_callable=AsyncMock, return_value=2),
        patch(_PATCH_GEN_LESSON, new_callable=AsyncMock, return_value="Intro text") as mock_lesson,
        patch(_PATCH_GEN_BATCH, new_callable=AsyncMock, return_value=[dict(_MCQ_EXERCISE)]),
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_SESSION, return_value=db_cm),
        patch(_PATCH_GET_DUE, new_callable=AsyncMock, return_value=["hegiddira", "chennagide"]),
        patch(_PATCH_GET_LEARNER_ID, new_callable=AsyncMock, return_value=42),
    ):
        await start_lesson(PHONE, "greetings")

    mock_lesson.assert_awaited_once_with(
        level=2, topic="greetings", due_items=["hegiddira", "chennagide"]
    )


# ---------------------------------------------------------------------------
# handle_exercise_answer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_answer_sends_no_lesson_when_no_context():
    convo = _make_convo(lesson_context=None)
    db_cm, _ = _make_db_context(convo)

    with (
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_SESSION, return_value=db_cm),
    ):
        await handle_exercise_answer(PHONE, "A")

    mock_send.assert_awaited_once()
    assert "No active lesson" in mock_send.call_args[0][1]


@pytest.mark.asyncio
async def test_handle_answer_evaluates_and_sends_feedback():
    # Two exercises so finish_lesson is not triggered
    exercises = [dict(_MCQ_EXERCISE), dict(_FILL_EXERCISE)]
    ctx = _make_ctx(exercises=exercises, current_index=0)
    convo = _make_convo(lesson_context=ctx)
    db_cm, _ = _make_db_context(convo)

    with (
        patch(_PATCH_EVAL, new_callable=AsyncMock, return_value=_EVAL_CORRECT) as mock_eval,
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_SESSION, return_value=db_cm),
    ):
        await handle_exercise_answer(PHONE, "namaskara")

    mock_eval.assert_awaited_once()
    assert mock_send.await_count >= 1


@pytest.mark.asyncio
async def test_handle_answer_resolves_mcq_letter():
    # Two exercises so finish_lesson is not triggered
    exercises = [dict(_MCQ_EXERCISE), dict(_FILL_EXERCISE)]
    ctx = _make_ctx(exercises=exercises, current_index=0)
    convo = _make_convo(lesson_context=ctx)
    db_cm, _ = _make_db_context(convo)

    with (
        patch(_PATCH_EVAL, new_callable=AsyncMock, return_value=_EVAL_CORRECT) as mock_eval,
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_SESSION, return_value=db_cm),
    ):
        # _MCQ_EXERCISE shuffled_options[0] == "namaskara"
        await handle_exercise_answer(PHONE, "A")

    call_kwargs = mock_eval.call_args[1]
    assert call_kwargs["learner_answer"] == "namaskara"


@pytest.mark.asyncio
async def test_handle_answer_sends_next_exercise_when_more_remain():
    exercises = [dict(_MCQ_EXERCISE), dict(_FILL_EXERCISE)]
    ctx = _make_ctx(exercises=exercises, current_index=0)
    convo = _make_convo(lesson_context=ctx)
    db_cm, _ = _make_db_context(convo)

    with (
        patch(_PATCH_EVAL, new_callable=AsyncMock, return_value=_EVAL_CORRECT),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_SESSION, return_value=db_cm),
    ):
        await handle_exercise_answer(PHONE, "namaskara")

    texts = [c[0][1] for c in mock_send.call_args_list]
    assert any("Exercise 2/2" in t for t in texts)


@pytest.mark.asyncio
async def test_handle_answer_calls_finish_lesson_when_last_exercise():
    ctx = _make_ctx(exercises=[dict(_MCQ_EXERCISE)], current_index=0, scores=[])
    convo = _make_convo(lesson_context=ctx)
    db_cm, _ = _make_db_context(convo)

    with (
        patch(_PATCH_EVAL, new_callable=AsyncMock, return_value=_EVAL_CORRECT),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_SESSION, return_value=db_cm),
        patch(_PATCH_GET_RING_LEVEL, new_callable=AsyncMock, return_value=2),
        patch("app.services.lesson_session._add_or_update_vocabulary", new_callable=AsyncMock),
    ):
        await handle_exercise_answer(PHONE, "namaskara")

    texts = [c[0][1] for c in mock_send.call_args_list]
    assert any("Session complete" in t for t in texts)


# ---------------------------------------------------------------------------
# finish_lesson
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finish_lesson_gets_ring_level():
    ctx = _make_ctx(exercises=[dict(_MCQ_EXERCISE)], scores=[1.0, 0.8])
    convo = _make_convo(lesson_context=ctx)
    db_cm, _ = _make_db_context(convo)

    with (
        patch(_PATCH_GET_RING_LEVEL, new_callable=AsyncMock, return_value=2) as mock_level,
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_SESSION, return_value=db_cm),
        patch("app.services.lesson_session._add_or_update_vocabulary", new_callable=AsyncMock),
    ):
        await finish_lesson(PHONE)

    mock_level.assert_awaited_once_with(PHONE)


@pytest.mark.asyncio
async def test_finish_lesson_sends_summary_with_score():
    ctx = _make_ctx(exercises=[dict(_MCQ_EXERCISE)], scores=[1.0, 0.0])
    convo = _make_convo(lesson_context=ctx)
    db_cm, _ = _make_db_context(convo)

    with (
        patch(_PATCH_GET_RING_LEVEL, new_callable=AsyncMock, return_value=2),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_SESSION, return_value=db_cm),
        patch("app.services.lesson_session._add_or_update_vocabulary", new_callable=AsyncMock),
    ):
        await finish_lesson(PHONE)

    summary_text = mock_send.call_args[0][1]
    assert "Session complete" in summary_text
    assert "1/2" in summary_text


@pytest.mark.asyncio
async def test_finish_lesson_shows_ring_in_summary():
    ctx = _make_ctx(exercises=[dict(_MCQ_EXERCISE)], scores=[1.0])
    convo = _make_convo(lesson_context=ctx)
    db_cm, _ = _make_db_context(convo)

    with (
        patch(_PATCH_GET_RING_LEVEL, new_callable=AsyncMock, return_value=3),
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_SESSION, return_value=db_cm),
        patch("app.services.lesson_session._add_or_update_vocabulary", new_callable=AsyncMock),
    ):
        await finish_lesson(PHONE)

    summary_text = mock_send.call_args[0][1]
    assert "Ring: 2" in summary_text


@pytest.mark.asyncio
async def test_finish_lesson_adds_vocabulary_for_each_exercise():
    exercises = [dict(_MCQ_EXERCISE), dict(_FILL_EXERCISE)]
    ctx = _make_ctx(exercises=exercises, scores=[1.0, 0.5], level=2)
    convo = _make_convo(lesson_context=ctx)
    db_cm, _ = _make_db_context(convo)

    with (
        patch(_PATCH_GET_RING_LEVEL, new_callable=AsyncMock, return_value=2),
        patch(_PATCH_SEND, new_callable=AsyncMock),
        patch(_PATCH_SESSION, return_value=db_cm),
        patch(
            "app.services.lesson_session._add_or_update_vocabulary",
            new_callable=AsyncMock,
        ) as mock_vocab,
    ):
        await finish_lesson(PHONE)

    assert mock_vocab.await_count == 2
    calls_words = {c[1]["kannada_word"] for c in mock_vocab.call_args_list}
    assert "namaskara" in calls_words
    assert "chennagi" in calls_words


@pytest.mark.asyncio
async def test_finish_lesson_noop_when_no_context():
    convo = _make_convo(lesson_context=None)
    db_cm, _ = _make_db_context(convo)

    with (
        patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send,
        patch(_PATCH_SESSION, return_value=db_cm),
    ):
        await finish_lesson(PHONE)

    mock_send.assert_not_awaited()
