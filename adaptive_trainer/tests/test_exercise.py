"""Tests for the exercise generator service."""

import json
import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test_access")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test_app_secret")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "test_phone_id")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")

from app.services.exercise import (  # noqa: E402
    ExerciseType,
    _validate_exercise,
    generate_exercise,
    generate_exercises_batch,
)

_MCQ_RESPONSE = json.dumps({
    "type": "mcq",
    "question": "Which Kannada word means 'water'?",
    "answer": "neeru",
    "distractors": ["haalu", "anna", "kai"],
    "explanation": "Neeru means water. Haalu is milk, anna is rice, kai is hand.",
})

_FILL_RESPONSE = json.dumps({
    "type": "fill_in_blank",
    "question": "Nim̐ma hesaru _____ ?",
    "answer": "enu",
    "distractors": ["ide", "alla", "beku"],
    "explanation": "Full sentence: 'What is your name?' — enu means 'what'.",
})

_TRANSLATION_RESPONSE = json.dumps({
    "type": "translation",
    "question": "I want to drink water.",
    "answer": "nange neeru beku",
    "distractors": [],
    "explanation": "nange = to me/I want; neeru = water; beku = want/need.",
})


@pytest.mark.asyncio
async def test_generate_mcq_returns_dict():
    with patch(
        "app.services.exercise.ask_sonnet",
        new_callable=AsyncMock,
        return_value=_MCQ_RESPONSE,
    ):
        result = await generate_exercise(ExerciseType.MCQ, level=2, topic="food and drink")

    assert result["type"] == "mcq"
    assert result["question"] == "Which Kannada word means 'water'?"
    assert result["answer"] == "neeru"
    assert len(result["distractors"]) == 3
    assert "explanation" in result


@pytest.mark.asyncio
async def test_generate_mcq_sends_level_and_topic():
    with patch(
        "app.services.exercise.ask_sonnet",
        new_callable=AsyncMock,
        return_value=_MCQ_RESPONSE,
    ) as mock_ask:
        await generate_exercise(ExerciseType.MCQ, level=3, topic="greetings")

    prompt_arg = mock_ask.call_args[0][0]
    assert "3/5" in prompt_arg
    assert "greetings" in prompt_arg


@pytest.mark.asyncio
async def test_generate_fill_in_blank():
    with patch(
        "app.services.exercise.ask_sonnet",
        new_callable=AsyncMock,
        return_value=_FILL_RESPONSE,
    ):
        result = await generate_exercise(ExerciseType.FILL_IN_BLANK, level=1, topic="greetings")

    assert result["type"] == "fill_in_blank"
    assert "_____" in result["question"]
    assert result["answer"] == "enu"
    assert len(result["distractors"]) == 3


@pytest.mark.asyncio
async def test_generate_translation():
    with patch(
        "app.services.exercise.ask_sonnet",
        new_callable=AsyncMock,
        return_value=_TRANSLATION_RESPONSE,
    ):
        result = await generate_exercise(ExerciseType.TRANSLATION, level=2, topic="food and drink")

    assert result["type"] == "translation"
    assert result["distractors"] == []
    assert result["answer"] == "nange neeru beku"


@pytest.mark.asyncio
async def test_generate_exercise_extracts_json_from_prose():
    """Service must extract JSON even if Claude wraps it in extra text."""
    wrapped = f"Here is your exercise:\n\n{_MCQ_RESPONSE}\n\nHope that helps!"
    with patch(
        "app.services.exercise.ask_sonnet",
        new_callable=AsyncMock,
        return_value=wrapped,
    ):
        result = await generate_exercise(ExerciseType.MCQ, level=1, topic="greetings")

    assert result["answer"] == "neeru"


@pytest.mark.asyncio
async def test_generate_exercise_raises_on_missing_json():
    with patch(
        "app.services.exercise.ask_sonnet",
        new_callable=AsyncMock,
        return_value="Sorry, I cannot help with that.",
    ):
        with pytest.raises((ValueError, Exception)):
            await generate_exercise(ExerciseType.MCQ, level=1, topic="greetings")


# ---------------------------------------------------------------------------
# _validate_exercise tests
# ---------------------------------------------------------------------------

_VALID_EX = {
    "type": "mcq",
    "question": "Which word means water?",
    "answer": "neeru",
    "distractors": ["haalu", "anna", "kai"],
    "explanation": "neeru means water",
}


def test_validate_exercise_accepts_valid():
    assert _validate_exercise(_VALID_EX) is True


def test_validate_exercise_rejects_missing_key():
    for key in ("type", "question", "answer", "distractors", "explanation"):
        bad = {k: v for k, v in _VALID_EX.items() if k != key}
        assert _validate_exercise(bad) is False, f"should reject missing {key}"


def test_validate_exercise_rejects_invalid_type():
    bad = {**_VALID_EX, "type": "multiple_choice"}
    assert _validate_exercise(bad) is False


def test_validate_exercise_rejects_non_list_distractors():
    bad = {**_VALID_EX, "distractors": "wrong"}
    assert _validate_exercise(bad) is False


def test_validate_exercise_rejects_non_dict():
    assert _validate_exercise("not a dict") is False
    assert _validate_exercise(None) is False


# ---------------------------------------------------------------------------
# generate_exercises_batch validation tests
# ---------------------------------------------------------------------------

_BATCH_VALID = json.dumps([
    {
        "type": "mcq",
        "question": "Which word means water?",
        "answer": "neeru",
        "distractors": ["haalu", "anna", "kai"],
        "explanation": "neeru means water",
    },
    {
        "type": "fill_in_blank",
        "question": "Nange _____ beku",
        "answer": "neeru",
        "distractors": ["haalu", "anna", "kai"],
        "explanation": "I want water",
    },
])


@pytest.mark.asyncio
async def test_batch_returns_valid_exercises():
    with patch(
        "app.services.exercise.ask_sonnet",
        new_callable=AsyncMock,
        return_value=_BATCH_VALID,
    ):
        result = await generate_exercises_batch(count=2, level=2, topic="food")

    assert len(result) == 2
    assert all(_validate_exercise(ex) for ex in result)


@pytest.mark.asyncio
async def test_batch_retries_on_invalid_then_succeeds():
    """First call returns invalid exercises, second returns valid ones."""
    bad_response = json.dumps([{"type": "bad"}])
    mock = AsyncMock(side_effect=[bad_response, _BATCH_VALID])
    with patch("app.services.exercise.ask_sonnet", mock):
        result = await generate_exercises_batch(count=2, level=2, topic="food")

    assert len(result) == 2
    assert mock.call_count == 2


@pytest.mark.asyncio
async def test_batch_raises_after_two_failures():
    """Both attempts return invalid exercises — should raise ValueError."""
    bad_response = json.dumps([{"type": "bad"}])
    mock = AsyncMock(return_value=bad_response)
    with patch("app.services.exercise.ask_sonnet", mock):
        with pytest.raises(ValueError, match="failed validation after retry"):
            await generate_exercises_batch(count=2, level=2, topic="food")

    assert mock.call_count == 2


@pytest.mark.asyncio
async def test_batch_filters_invalid_items_from_mixed_response():
    """If response has a mix of valid and invalid, only valid ones are kept."""
    mixed = json.dumps([
        _VALID_EX,
        {"type": "bad_type", "question": "q", "answer": "a", "distractors": [], "explanation": "e"},
        {**_VALID_EX, "type": "fill_in_blank"},
    ])
    with patch(
        "app.services.exercise.ask_sonnet",
        new_callable=AsyncMock,
        return_value=mixed,
    ):
        result = await generate_exercises_batch(count=2, level=2, topic="food")

    assert len(result) == 2
    assert all(_validate_exercise(ex) for ex in result)
