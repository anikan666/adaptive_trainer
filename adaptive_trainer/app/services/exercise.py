"""Exercise generator: MCQ, fill-in-blank, and translation exercises for Kannada learners."""

import json
from enum import Enum

from app.services.claude_client import SYSTEM_EXERCISE_GENERATION, ask_sonnet


class ExerciseType(str, Enum):
    MCQ = "mcq"
    FILL_IN_BLANK = "fill_in_blank"
    TRANSLATION = "translation"


_LESSON_CONTEXT_SECTION = """\

Lesson content the learner just studied (use vocabulary and phrases from this lesson):
---
{lesson_text}
---
"""

_MCQ_PROMPT_TEMPLATE = """\
Generate a multiple-choice vocabulary exercise for a Kannada learner at level {level}/5.
Topic: {topic}{lesson_context}
Choose one specific Kannada word or phrase from the lesson content above. Generate the \
correct Kannada transliteration and three plausible but incorrect distractors.

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
Topic: {topic}{lesson_context}
Write a short Kannada sentence using vocabulary from the lesson content above, with one \
word replaced by _____. Provide the missing word (answer) and a brief English translation.

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
Topic: {topic}{lesson_context}
Write a short, natural English sentence that uses vocabulary or phrases from the lesson \
content above that the learner should translate into colloquial Kannada (Roman transliteration).

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

_BATCH_PROMPT_TEMPLATE = """\
Generate {count} Kannada exercises for a learner at level {level}/5.
Topic: {topic}{lesson_context}{target_words_context}
Use vocabulary and phrases from the lesson content above. Include a mix of exercise types.

Return a JSON array of exactly {count} exercise objects. Each object must have these fields:
{{
  "type": "mcq" | "fill_in_blank" | "translation",
  "question": "<the question text>",
  "answer": "<correct answer in Roman transliteration>",
  "distractors": ["<wrong1>", "<wrong2>", "<wrong3>"],  // empty array for translation
  "explanation": "<brief explanation>"
}}

For mcq: question is an English prompt 'Which Kannada word means ...?', answer and distractors are Roman transliterations.
For fill_in_blank: question is a Kannada sentence with _____, answer is the missing word.
For translation: question is an English sentence to translate, answer is the Kannada translation.

All Kannada must be in Roman transliteration only. Return only the JSON array, no other text.
"""

_TARGET_WORDS_SECTION = """\

Exercises MUST test these specific words (use each word in at least one exercise):
{words}
"""


_REQUIRED_EXERCISE_KEYS = {"type", "question", "answer", "distractors", "explanation"}
_VALID_TYPES = {e.value for e in ExerciseType}


def _validate_exercise(ex: dict) -> bool:
    """Return True if an exercise dict has all required keys with valid values."""
    if not isinstance(ex, dict):
        return False
    if not _REQUIRED_EXERCISE_KEYS.issubset(ex.keys()):
        return False
    if ex["type"] not in _VALID_TYPES:
        return False
    if not isinstance(ex["distractors"], list):
        return False
    return True


def _find_balanced(text: str, open_ch: str, close_ch: str) -> str | None:
    """Find the first balanced substring delimited by open_ch/close_ch."""
    start = text.find(open_ch)
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            if in_string:
                escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _extract_json(text: str) -> str:
    """Extract the first JSON object from a string."""
    result = _find_balanced(text, "{", "}")
    if result is None:
        raise ValueError(f"No JSON object found in response: {text!r}")
    return result


def _extract_json_array(text: str) -> str:
    """Extract the first JSON array from a string."""
    result = _find_balanced(text, "[", "]")
    if result is None:
        raise ValueError(f"No JSON array found in response: {text!r}")
    return result


async def generate_exercise(
    exercise_type: ExerciseType,
    level: int,
    topic: str,
    lesson_text: str = "",
) -> dict:
    """Generate a single exercise of the requested type.

    Args:
        exercise_type: One of mcq, fill_in_blank, or translation.
        level: Learner proficiency level (1–5).
        topic: Exercise topic in English (e.g. "greetings", "food ordering").
        lesson_text: Optional lesson content to ground exercises in specific vocabulary.

    Returns:
        Dict with keys: type, question, answer, distractors, explanation.
    """
    lesson_context = _LESSON_CONTEXT_SECTION.format(lesson_text=lesson_text) if lesson_text else "\n"
    template = _PROMPT_TEMPLATES[exercise_type]
    prompt = template.format(level=level, topic=topic, lesson_context=lesson_context)
    raw = await ask_sonnet(prompt, SYSTEM_EXERCISE_GENERATION)
    json_str = _extract_json(raw)
    return json.loads(json_str)


async def generate_exercises_batch(
    count: int,
    level: int,
    topic: str,
    lesson_text: str = "",
    target_words: list[dict] | None = None,
) -> list[dict]:
    """Generate multiple exercises in a single API call.

    Args:
        count: Number of exercises to generate.
        level: Learner proficiency level (1–5).
        topic: Exercise topic in English.
        lesson_text: Lesson content to ground exercises in specific vocabulary.
        target_words: Optional list of word dicts (with 'roman', 'english' keys)
            that exercises should specifically test.

    Returns:
        List of exercise dicts with keys: type, question, answer, distractors, explanation.

    Raises:
        ValueError: If exercises fail validation after one retry.
    """
    lesson_context = _LESSON_CONTEXT_SECTION.format(lesson_text=lesson_text) if lesson_text else "\n"
    target_words_context = ""
    if target_words:
        formatted = "\n".join(
            f"- {w.get('roman', '')} ({w.get('english', '')})" for w in target_words
        )
        target_words_context = _TARGET_WORDS_SECTION.format(words=formatted)
    prompt = _BATCH_PROMPT_TEMPLATE.format(
        count=count, level=level, topic=topic,
        lesson_context=lesson_context,
        target_words_context=target_words_context,
    )

    for attempt in range(2):
        raw = await ask_sonnet(prompt, SYSTEM_EXERCISE_GENERATION)
        json_str = _extract_json_array(raw)
        exercises = json.loads(json_str)

        valid = [ex for ex in exercises if _validate_exercise(ex)]

        if len(valid) >= count:
            return valid[:count]

        if attempt == 0:
            continue

    raise ValueError(
        f"Exercise generation failed validation after retry: "
        f"expected {count} valid exercises, got {len(valid)}"
    )
