"""Exercise generator: MCQ, fill-in-blank, and translation exercises for Kannada learners."""

import json
import re
from enum import Enum

from app.services.claude_client import SYSTEM_EXERCISE_GENERATION, ask_sonnet


class ExerciseType(str, Enum):
    MCQ = "mcq"
    FILL_IN_BLANK = "fill_in_blank"
    TRANSLATION = "translation"


_MCQ_PROMPT_TEMPLATE = """\
Generate a multiple-choice vocabulary exercise for a Kannada learner at level {level}/5.
Topic: {topic}

Choose one English word or phrase related to the topic. Generate the correct Kannada \
transliteration and three plausible but incorrect distractors.

Return a JSON object with exactly these fields:
{{
  "type": "mcq",
  "question": "<English prompt: 'Which Kannada word means ...?'>",
  "answer": "<correct Roman transliteration>",
  "distractors": ["<wrong1>", "<wrong2>", "<wrong3>"],
  "explanation": "<brief explanation of the correct answer and why distractors are wrong>"
}}

All Kannada must be in Roman transliteration only. Return only the JSON object, no other text.
"""

_FILL_IN_BLANK_PROMPT_TEMPLATE = """\
Generate a fill-in-the-blank exercise for a Kannada learner at level {level}/5.
Topic: {topic}

Write a short Kannada sentence in Roman transliteration with one word replaced by _____.
Provide the missing word (answer) and a brief English translation of the complete sentence.

Return a JSON object with exactly these fields:
{{
  "type": "fill_in_blank",
  "question": "<Kannada sentence in Roman transliteration with _____ as the blank>",
  "answer": "<the missing Kannada word in Roman transliteration>",
  "distractors": ["<wrong1>", "<wrong2>", "<wrong3>"],
  "explanation": "<English translation of the full sentence and why the answer fits>"
}}

All Kannada must be in Roman transliteration only. Return only the JSON object, no other text.
"""

_TRANSLATION_PROMPT_TEMPLATE = """\
Generate a translation exercise for a Kannada learner at level {level}/5.
Topic: {topic}

Write a short, natural English sentence related to the topic that the learner should \
translate into colloquial Kannada (Roman transliteration).

Return a JSON object with exactly these fields:
{{
  "type": "translation",
  "question": "<English sentence to translate>",
  "answer": "<correct colloquial Kannada translation in Roman transliteration>",
  "distractors": [],
  "explanation": "<notes on the translation: key vocabulary, register, or cultural context>"
}}

All Kannada must be in Roman transliteration only. Return only the JSON object, no other text.
"""

_PROMPT_TEMPLATES = {
    ExerciseType.MCQ: _MCQ_PROMPT_TEMPLATE,
    ExerciseType.FILL_IN_BLANK: _FILL_IN_BLANK_PROMPT_TEMPLATE,
    ExerciseType.TRANSLATION: _TRANSLATION_PROMPT_TEMPLATE,
}


def _extract_json(text: str) -> str:
    """Extract the first JSON object from a string."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in response: {text!r}")
    return match.group(0)


async def generate_exercise(
    exercise_type: ExerciseType,
    level: int,
    topic: str,
) -> dict:
    """Generate a single exercise of the requested type.

    Args:
        exercise_type: One of mcq, fill_in_blank, or translation.
        level: Learner proficiency level (1–5).
        topic: Exercise topic in English (e.g. "greetings", "food ordering").

    Returns:
        Dict with keys: type, question, answer, distractors, explanation.
    """
    template = _PROMPT_TEMPLATES[exercise_type]
    prompt = template.format(level=level, topic=topic)
    raw = await ask_sonnet(prompt, SYSTEM_EXERCISE_GENERATION)
    json_str = _extract_json(raw)
    return json.loads(json_str)
