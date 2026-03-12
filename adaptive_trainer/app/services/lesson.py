"""Lesson generator: Claude-powered adaptive Kannada lesson content."""

from app.services.claude_client import SYSTEM_LESSON_GENERATION, ask_sonnet

_LESSON_PROMPT_TEMPLATE = """\
Generate a Kannada language lesson for a learner at level {level}/5.
Topic: {topic}

Structure the lesson as follows:
1. Brief explanation (2-3 sentences)
2. Key vocabulary (5 words/phrases): each entry as "Roman transliteration — English meaning"
3. Example sentences (3-5): each as "Roman transliteration — English translation"
4. One cultural note relevant to the topic

{srs_context}All Kannada must be in Roman transliteration only.
"""

_SRS_PREFIX = "Prioritise these vocabulary items the learner is due to review: {items}\n\n"


async def generate_lesson(level: int, topic: str, due_items: list[str] | None = None) -> str:
    """Generate an adaptive lesson for the given learner level and topic.

    Args:
        level: Learner proficiency level (1–5).
        topic: Lesson topic in English (e.g. "greetings", "food ordering").
        due_items: Optional list of SRS-due vocabulary items to weave in.

    Returns:
        Formatted lesson text ready to send via WhatsApp.
    """
    srs_context = ""
    if due_items:
        srs_context = _SRS_PREFIX.format(items=", ".join(due_items))

    prompt = _LESSON_PROMPT_TEMPLATE.format(
        level=level,
        topic=topic,
        srs_context=srs_context,
    )
    return await ask_sonnet(prompt, SYSTEM_LESSON_GENERATION)
