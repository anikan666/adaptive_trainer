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

Scoring rubric (use these anchors for consistency):
- 1.0: Perfect or near-perfect. Meaning, register, and grammar all correct. \
Trivial transliteration differences only (e.g. "neeru" vs "niru").
- 0.8: Correct meaning with minor issues — slightly formal register, small \
grammar slip, or one wrong word that doesn't change meaning.
- 0.5: Partially correct — conveys roughly the right idea but with significant \
errors (wrong verb form, missing key word, mixed-up subject/object).
- 0.3: Mostly wrong — recognizable topic but meaning is substantially different \
or garbled.
- 0.0: Completely wrong, nonsensical, or unrelated to the question.

Set "correct" to true only for scores >= 0.7.

Return a JSON object with exactly these fields:
{{
  "correct": <true if essentially correct (score >= 0.7), false otherwise>,
  "score": <float 0.0–1.0, using the rubric above>,
  "feedback": "<concise English feedback explaining correctness or errors>",
  "corrected_kannada": "<if incorrect, provide the ideal Kannada answer in Roman transliteration; omit or null if correct>",
  "error_type": "<one of: wrong_word, wrong_form, wrong_register, wrong_order, partial, spelling, none — categorize the primary error>",
  "explanation": "<1-2 sentence explanation of WHY the answer is wrong and what the learner should understand. For correct answers, briefly affirm what they got right. E.g. 'You used the formal form _haagide_ but the colloquial form is _aite_.' or 'You translated _come_ as _hogi_ which means _go_ — the correct word is _baa_.'>"
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

Scoring rubric (use these anchors for consistency):
- 1.0: Perfect or near-perfect. Meaning, register, and situational fit all correct. \
Trivial transliteration differences only.
- 0.8: Correct meaning and fits the scenario, but minor issues — slightly formal \
register, small grammar slip, or one awkward word choice.
- 0.5: Partially appropriate — recognizable attempt at the right response but with \
significant errors (wrong politeness level, missing key phrase, meaning drift).
- 0.3: Mostly wrong — the response doesn't fit the scenario well or conveys a \
substantially different meaning.
- 0.0: Completely wrong, nonsensical, or unrelated to the scenario.

Set "correct" to true only for scores >= 0.7.

Return a JSON object with exactly these fields:
{{
  "correct": <true if contextually appropriate and essentially correct (score >= 0.7), false otherwise>,
  "score": <float 0.0–1.0, using the rubric above>,
  "feedback": "<concise English feedback on how well the response fits the scenario>",
  "corrected_kannada": "<if incorrect, provide a natural Kannada response in Roman transliteration; omit or null if correct>",
  "error_type": "<one of: wrong_word, wrong_register, wrong_context, partial, spelling, none — categorize the primary error>",
  "explanation": "<1-2 sentence explanation of WHY the answer is wrong and what the learner should understand. For correct answers, briefly affirm what they got right. E.g. 'This situation calls for a polite request but you used a casual command form.' or 'You greeted correctly but _namaskara_ is too formal for talking to a friend — use _hey_ or _yeno_.>'>"
}}

Return only the JSON object, no other text.
"""


def _exact_match_result(question: str) -> dict:
    return {
        "correct": True,
        "score": 1.0,
        "feedback": "Correct!",
        "corrected_kannada": None,
        "error_type": "none",
        "explanation": "You got it right!",
    }


def _wrong_match_result(expected_answer: str) -> dict:
    return {
        "correct": False,
        "score": 0.0,
        "feedback": f"Not quite. The correct answer is: {expected_answer}",
        "corrected_kannada": expected_answer,
        "error_type": "wrong_word",
        "explanation": f"The expected answer was '{expected_answer}'. Review this word and try to remember it for next time.",
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
        result.setdefault("error_type", "none")
        result.setdefault("explanation", "")
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
        result.setdefault("error_type", "none")
        result.setdefault("explanation", "")
        return result

    # MCQ / fill-in-blank: exact match only (no Claude fallback)
    if _normalize(learner_answer) == _normalize(expected_answer):
        return _exact_match_result(question)

    return _wrong_match_result(expected_answer)
