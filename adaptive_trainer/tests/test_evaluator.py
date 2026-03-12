"""Tests for the answer evaluator service."""

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

from app.services.evaluator import evaluate_answer  # noqa: E402
from app.services.exercise import ExerciseType  # noqa: E402

_CORRECT_TRANSLATION_RESPONSE = json.dumps({
    "correct": True,
    "score": 0.95,
    "feedback": "Great! Your translation is natural and colloquial.",
    "corrected_kannada": None,
})

_WRONG_TRANSLATION_RESPONSE = json.dumps({
    "correct": False,
    "score": 0.3,
    "feedback": "The meaning is off. 'Neeru' means water, not food.",
    "corrected_kannada": "nange neeru beku",
})

_NEAR_MISS_CORRECT_RESPONSE = json.dumps({
    "correct": True,
    "score": 0.9,
    "feedback": "Acceptable transliteration variant.",
    "corrected_kannada": None,
})

_NEAR_MISS_WRONG_RESPONSE = json.dumps({
    "correct": False,
    "score": 0.2,
    "feedback": "That word means something else entirely.",
    "corrected_kannada": "neeru",
})


@pytest.mark.asyncio
async def test_translation_correct():
    with patch(
        "app.services.evaluator.ask_sonnet",
        new_callable=AsyncMock,
        return_value=_CORRECT_TRANSLATION_RESPONSE,
    ):
        result = await evaluate_answer(
            ExerciseType.TRANSLATION,
            question="I want to drink water.",
            expected_answer="nange neeru beku",
            learner_answer="nange neeru beku",
        )

    assert result["correct"] is True
    assert result["score"] == 0.95
    assert "Great" in result["feedback"]
    assert result["corrected_kannada"] is None


@pytest.mark.asyncio
async def test_translation_wrong():
    with patch(
        "app.services.evaluator.ask_sonnet",
        new_callable=AsyncMock,
        return_value=_WRONG_TRANSLATION_RESPONSE,
    ):
        result = await evaluate_answer(
            ExerciseType.TRANSLATION,
            question="I want to drink water.",
            expected_answer="nange neeru beku",
            learner_answer="nange thindi beku",
        )

    assert result["correct"] is False
    assert result["score"] == 0.3
    assert result["corrected_kannada"] == "nange neeru beku"


@pytest.mark.asyncio
async def test_translation_calls_claude_with_question_and_expected(
):
    with patch(
        "app.services.evaluator.ask_sonnet",
        new_callable=AsyncMock,
        return_value=_CORRECT_TRANSLATION_RESPONSE,
    ) as mock_ask:
        await evaluate_answer(
            ExerciseType.TRANSLATION,
            question="I want to drink water.",
            expected_answer="nange neeru beku",
            learner_answer="nange neeru beku",
        )

    prompt_arg = mock_ask.call_args[0][0]
    assert "nange neeru beku" in prompt_arg
    assert "I want to drink water" in prompt_arg


@pytest.mark.asyncio
async def test_mcq_exact_match_no_claude_call():
    """Exact match for MCQ must not call Claude."""
    with patch(
        "app.services.evaluator.ask_sonnet",
        new_callable=AsyncMock,
    ) as mock_ask:
        result = await evaluate_answer(
            ExerciseType.MCQ,
            question="Which Kannada word means 'water'?",
            expected_answer="neeru",
            learner_answer="neeru",
        )

    mock_ask.assert_not_called()
    assert result["correct"] is True
    assert result["score"] == 1.0


@pytest.mark.asyncio
async def test_mcq_exact_match_case_insensitive():
    with patch("app.services.evaluator.ask_sonnet", new_callable=AsyncMock) as mock_ask:
        result = await evaluate_answer(
            ExerciseType.MCQ,
            question="Which Kannada word means 'water'?",
            expected_answer="neeru",
            learner_answer="Neeru",
        )

    mock_ask.assert_not_called()
    assert result["correct"] is True


@pytest.mark.asyncio
async def test_fill_in_blank_exact_match_no_claude_call():
    with patch("app.services.evaluator.ask_sonnet", new_callable=AsyncMock) as mock_ask:
        result = await evaluate_answer(
            ExerciseType.FILL_IN_BLANK,
            question="Nim̐ma hesaru _____ ?",
            expected_answer="enu",
            learner_answer="enu",
        )

    mock_ask.assert_not_called()
    assert result["correct"] is True
    assert result["score"] == 1.0


@pytest.mark.asyncio
async def test_mcq_near_miss_calls_claude():
    with patch(
        "app.services.evaluator.ask_sonnet",
        new_callable=AsyncMock,
        return_value=_NEAR_MISS_CORRECT_RESPONSE,
    ) as mock_ask:
        result = await evaluate_answer(
            ExerciseType.MCQ,
            question="Which Kannada word means 'water'?",
            expected_answer="neeru",
            learner_answer="niru",
        )

    mock_ask.assert_called_once()
    assert result["correct"] is True


@pytest.mark.asyncio
async def test_mcq_wrong_answer():
    with patch(
        "app.services.evaluator.ask_sonnet",
        new_callable=AsyncMock,
        return_value=_NEAR_MISS_WRONG_RESPONSE,
    ):
        result = await evaluate_answer(
            ExerciseType.MCQ,
            question="Which Kannada word means 'water'?",
            expected_answer="neeru",
            learner_answer="haalu",
        )

    assert result["correct"] is False
    assert result["corrected_kannada"] == "neeru"


@pytest.mark.asyncio
async def test_evaluator_extracts_json_from_prose():
    """Evaluator must handle Claude wrapping JSON in prose."""
    wrapped = f"Here is my evaluation:\n\n{_CORRECT_TRANSLATION_RESPONSE}\n\nGood luck!"
    with patch(
        "app.services.evaluator.ask_sonnet",
        new_callable=AsyncMock,
        return_value=wrapped,
    ):
        result = await evaluate_answer(
            ExerciseType.TRANSLATION,
            question="I want to drink water.",
            expected_answer="nange neeru beku",
            learner_answer="nange neeru beku",
        )

    assert result["correct"] is True


@pytest.mark.asyncio
async def test_corrected_kannada_defaults_to_none_when_missing():
    """If Claude omits corrected_kannada, it should default to None."""
    response_without_field = json.dumps({
        "correct": True,
        "score": 1.0,
        "feedback": "Perfect!",
    })
    with patch(
        "app.services.evaluator.ask_sonnet",
        new_callable=AsyncMock,
        return_value=response_without_field,
    ):
        result = await evaluate_answer(
            ExerciseType.TRANSLATION,
            question="I want to drink water.",
            expected_answer="nange neeru beku",
            learner_answer="nange neeru beku",
        )

    assert result["corrected_kannada"] is None
