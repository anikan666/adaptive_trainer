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

from app.services.exercise import ExerciseType, generate_exercise  # noqa: E402

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
