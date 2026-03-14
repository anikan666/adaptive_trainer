"""Exercise generator: MCQ, fill-in-blank, and translation exercises for Kannada learners."""

import json
import logging
from enum import Enum

from app.services.claude_client import SYSTEM_EXERCISE_GENERATION, ask_sonnet

logger = logging.getLogger(__name__)


class ExerciseType(str, Enum):
    MCQ = "mcq"
    FILL_IN_BLANK = "fill_in_blank"
    TRANSLATION = "translation"
    SITUATIONAL_PROMPT = "situational_prompt"


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

_SITUATIONAL_PROMPT_TEMPLATE = """\
Generate a situational-prompt exercise for a Kannada learner at level {level}/5.
Topic: {topic}{lesson_context}
Present a realistic everyday scenario (e.g. at an auto stand, at a darshini, \
asking for directions) where the learner must respond in colloquial Kannada \
(Roman transliteration). The scenario should use vocabulary from the lesson content above.

Return a JSON object with exactly these fields:
{{
  "type": "situational_prompt",
  "question": "<English description of the scenario, e.g. 'You're at a darshini. Ask for two idlis and a coffee.'>",
  "answer": "<natural colloquial Kannada response in Roman transliteration>",
  "distractors": [],
  "explanation": "<brief notes on key vocabulary, register, or cultural context>"
}}

All Kannada must be in Roman transliteration only. Return only the JSON object, no other text.
"""

_PROMPT_TEMPLATES = {
    ExerciseType.MCQ: _MCQ_PROMPT_TEMPLATE,
    ExerciseType.FILL_IN_BLANK: _FILL_IN_BLANK_PROMPT_TEMPLATE,
    ExerciseType.TRANSLATION: _TRANSLATION_PROMPT_TEMPLATE,
    ExerciseType.SITUATIONAL_PROMPT: _SITUATIONAL_PROMPT_TEMPLATE,
}

_BATCH_PROMPT_TEMPLATE = """\
Generate {count} Kannada exercises for a learner at level {level}/5.
Topic: {topic}{lesson_context}{target_words_context}
Use vocabulary and phrases from the lesson content above. Include a mix of exercise types.

Return a JSON array of exactly {count} exercise objects. Each object must have these fields:
{{
  "type": "mcq" | "fill_in_blank" | "translation" | "situational_prompt",
  "question": "<the question text>",
  "answer": "<correct answer in Roman transliteration>",
  "distractors": ["<wrong1>", "<wrong2>", "<wrong3>"],  // empty array for translation and situational_prompt
  "explanation": "<brief explanation>"
}}

For mcq: question is an English prompt 'Which Kannada word means ...?', answer and distractors are Roman transliterations.
For fill_in_blank: question is a Kannada sentence with _____, answer is the missing word.
For translation: question is an English sentence to translate, answer is the Kannada translation.
For situational_prompt: question describes a real-life scenario, answer is the natural Kannada response.

All Kannada must be in Roman transliteration only. Return only the JSON array, no other text.
"""

_TARGET_WORDS_SECTION = """\

Exercises MUST test these specific words (use each word in at least one exercise):
{words}
"""


_REQUIRED_EXERCISE_KEYS = {"type", "question", "answer", "distractors", "explanation"}
_VALID_TYPES = {e.value for e in ExerciseType}


_TYPES_REQUIRING_DISTRACTORS = {ExerciseType.MCQ.value, ExerciseType.FILL_IN_BLANK.value}


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
    # MCQ and fill_in_blank must have at least one distractor
    if ex["type"] in _TYPES_REQUIRING_DISTRACTORS and len(ex["distractors"]) == 0:
        return False
    # All string fields must be non-empty
    for key in ("type", "question", "answer", "explanation"):
        if not isinstance(ex.get(key), str) or not ex[key].strip():
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


_DIFFICULTY_ORDER = {
    ExerciseType.MCQ.value: 0,
    ExerciseType.FILL_IN_BLANK.value: 1,
    ExerciseType.TRANSLATION.value: 2,
    ExerciseType.SITUATIONAL_PROMPT.value: 3,
}


def _sort_by_difficulty(exercises: list[dict]) -> list[dict]:
    """Sort exercises by cognitive difficulty: MCQ → fill-in-blank → translation → situational prompt."""
    return sorted(exercises, key=lambda ex: _DIFFICULTY_ORDER.get(ex.get("type", ""), 99))


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
        Falls back to individual generation if batch validation fails after retry.
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
            return _sort_by_difficulty(valid[:count])

        if attempt == 0:
            continue

    # Batch failed validation after retry — fall back to individual generation
    logger.warning(
        "Batch generation failed validation (expected %d, got %d valid). "
        "Falling back to individual generation.",
        count, len(valid),
    )
    exercise_types = list(ExerciseType)
    fallback: list[dict] = list(valid)  # keep any valid exercises from batch
    for i in range(count - len(fallback)):
        ex_type = exercise_types[i % len(exercise_types)]
        ex = await generate_exercise(ex_type, level, topic, lesson_text)
        if _validate_exercise(ex):
            fallback.append(ex)
    return _dedup_consecutive_types(fallback[:count])


def _dedup_consecutive_types(exercises: list[dict]) -> list[dict]:
    """Reorder exercises so the same type doesn't appear back to back."""
    if len(exercises) <= 1:
        return exercises
    result = [exercises[0]]
    remaining = exercises[1:]
    while remaining:
        for i, ex in enumerate(remaining):
            if ex.get("type") != result[-1].get("type"):
                result.append(remaining.pop(i))
                break
        else:
            result.append(remaining.pop(0))
    return result
