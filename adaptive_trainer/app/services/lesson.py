"""Lesson generator: Claude-powered adaptive Kannada lesson content."""

from app.services.claude_client import SYSTEM_LESSON_GENERATION, ask_sonnet

_LESSON_PROMPT_TEMPLATE = """\
Teach me a quick Kannada lesson on: {topic}
My level: {level}/5

Keep it bite-sized for WhatsApp:
- 1-2 sentence intro (no heading, no "Overview")
- 3 key phrases: "transliteration — English meaning"
- 2 example sentences: "transliteration — English translation"
- 1 quick cultural tip (one sentence)

{srs_context}{words_context}All Kannada in Roman transliteration only. No markdown headers. Keep the whole thing under 500 characters.
"""

_SRS_PREFIX = "Work these review words into the lesson: {items}\n\n"

_NEW_WORDS_PREFIX = "Focus on teaching these new words:\n{words}\n\n"

_REVIEW_WORDS_PREFIX = "Also weave in these review words from previous lessons: {items}\n\n"


async def generate_lesson(
    level: int,
    topic: str,
    due_items: list[str] | None = None,
    new_words: list[dict] | None = None,
    review_words: list[str] | None = None,
) -> str:
    """Generate a lesson, optionally curriculum-aware with target words.

    Args:
        level: Learner proficiency level (1-5).
        topic: Lesson topic in English.
        due_items: Legacy SRS due items (used when no curriculum words provided).
        new_words: Curriculum new words (dicts with 'word', 'roman', 'english' keys).
        review_words: Review words from previous units to weave in.
    """
    srs_context = ""
    words_context = ""

    if new_words:
        formatted = "\n".join(
            f"- {w.get('roman', w.get('word', ''))} — {w.get('english', '')}"
            for w in new_words
        )
        words_context = _NEW_WORDS_PREFIX.format(words=formatted)
        if review_words:
            words_context += _REVIEW_WORDS_PREFIX.format(items=", ".join(review_words))
    elif due_items:
        srs_context = _SRS_PREFIX.format(items=", ".join(due_items))

    prompt = _LESSON_PROMPT_TEMPLATE.format(
        level=level,
        topic=topic,
        srs_context=srs_context,
        words_context=words_context,
    )
    return await ask_sonnet(prompt, SYSTEM_LESSON_GENERATION)
