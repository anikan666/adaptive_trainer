"""Answer evaluator: assess learner responses and generate feedback."""

import json
import re
import unicodedata

from app.services.claude_client import SYSTEM_ANSWER_EVALUATION, ask_sonnet
from app.services.exercise import ExerciseType, _extract_json


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation/accents, collapse whitespace."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


_TRANSLATION_EVAL_PROMPT = """\
Exercise type: translation
Question (English sentence to translate): {question}
Expected answer (colloquial Kannada, Roman transliteration): {expected}
Learner's answer: {learner}

Evaluate the learner's answer. Consider:
1. Semantic correctness — does it convey the same meaning?
2. Natural register — is it appropriately colloquial?
3. Minor spelling variations in transliteration are acceptable.

Return a JSON object with exactly these fields:
{{
  "correct": <true if essentially correct, false otherwise>,
  "score": <float 0.0–1.0>,
  "feedback": "<concise English feedback explaining correctness or errors>",
  "corrected_kannada": "<if incorrect, provide the ideal Kannada answer in Roman transliteration; omit or null if correct>"
}}

Return only the JSON object, no other text.
"""

_SITUATIONAL_EVAL_PROMPT = """\
Exercise type: situational_prompt
Scenario: {question}
Expected response (colloquial Kannada, Roman transliteration): {expected}
Learner's response: {learner}

Evaluate the learner's response to this scenario. Consider:
1. Contextual appropriateness — does the response fit the scenario?
2. Semantic correctness — does it convey the right meaning?
3. Natural register — is it appropriately colloquial for the situation?
4. Minor spelling variations in transliteration are acceptable.

Return a JSON object with exactly these fields:
{{
  "correct": <true if contextually appropriate and essentially correct, false otherwise>,
  "score": <float 0.0–1.0>,
  "feedback": "<concise English feedback on how well the response fits the scenario>",
  "corrected_kannada": "<if incorrect, provide a natural Kannada response in Roman transliteration; omit or null if correct>"
}}

Return only the JSON object, no other text.
"""

_NEAR_MISS_EVAL_PROMPT = """\
Exercise type: {exercise_type}
Question: {question}
Expected answer (Roman transliteration): {expected}
Learner's answer: {learner}

The learner's answer did not exactly match the expected answer but may still be \
acceptable. Evaluate whether it is semantically equivalent or a valid alternative.

Return a JSON object with exactly these fields:
{{
  "correct": <true if acceptable, false otherwise>,
  "score": <float 0.0–1.0>,
  "feedback": "<concise English feedback>",
  "corrected_kannada": "<ideal Roman transliteration if learner was wrong; null if correct>"
}}

Return only the JSON object, no other text.
"""


def _exact_match_result(question: str) -> dict:
    return {
        "correct": True,
        "score": 1.0,
        "feedback": "Correct!",
        "corrected_kannada": None,
    }


async def evaluate_answer(
    exercise_type: ExerciseType,
    question: str,
    expected_answer: str,
    learner_answer: str,
) -> dict:
    """Evaluate a learner's answer to an exercise.

    Args:
        exercise_type: One of mcq, fill_in_blank, or translation.
        question: The exercise question text.
        expected_answer: The correct answer (Roman transliteration for Kannada).
        learner_answer: The learner's submitted answer.

    Returns:
        Dict with keys:
            correct (bool): Whether the answer is correct.
            score (float): 0.0–1.0 correctness score.
            feedback (str): English feedback string.
            corrected_kannada (str | None): Correct form if wrong, else None.
    """
    if exercise_type == ExerciseType.TRANSLATION:
        prompt = _TRANSLATION_EVAL_PROMPT.format(
            question=question,
            expected=expected_answer,
            learner=learner_answer,
        )
        raw = await ask_sonnet(prompt, SYSTEM_ANSWER_EVALUATION)
        result = json.loads(_extract_json(raw))
        result.setdefault("corrected_kannada", None)
        return result

    if exercise_type == ExerciseType.SITUATIONAL_PROMPT:
        prompt = _SITUATIONAL_EVAL_PROMPT.format(
            question=question,
            expected=expected_answer,
            learner=learner_answer,
        )
        raw = await ask_sonnet(prompt, SYSTEM_ANSWER_EVALUATION)
        result = json.loads(_extract_json(raw))
        result.setdefault("corrected_kannada", None)
        return result

    # MCQ / fill-in-blank: exact match first
    if _normalize(learner_answer) == _normalize(expected_answer):
        return _exact_match_result(question)

    # Near-miss: ask Claude
    prompt = _NEAR_MISS_EVAL_PROMPT.format(
        exercise_type=exercise_type.value,
        question=question,
        expected=expected_answer,
        learner=learner_answer,
    )
    raw = await ask_sonnet(prompt, SYSTEM_ANSWER_EVALUATION)
    result = json.loads(_extract_json(raw))
    result.setdefault("corrected_kannada", None)
    return result
