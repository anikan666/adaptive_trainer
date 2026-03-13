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

{srs_context}All Kannada in Roman transliteration only. No markdown headers. Keep the whole thing under 500 characters.
"""

_SRS_PREFIX = "Work these review words into the lesson: {items}\n\n"


async def generate_lesson(level: int, topic: str, due_items: list[str] | None = None) -> str:
    srs_context = ""
    if due_items:
        srs_context = _SRS_PREFIX.format(items=", ".join(due_items))

    prompt = _LESSON_PROMPT_TEMPLATE.format(
        level=level,
        topic=topic,
        srs_context=srs_context,
    )
    return await ask_sonnet(prompt, SYSTEM_LESSON_GENERATION)
