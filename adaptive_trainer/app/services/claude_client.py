import anthropic

from app.config import settings

# ---------------------------------------------------------------------------
# System prompt constants
# ---------------------------------------------------------------------------

SYSTEM_TRANSLATION = (
    "You are a Kannada language assistant. "
    "Translate the user's input into colloquial, everyday Kannada as spoken by "
    "native speakers in Bengaluru. Use informal register and natural spoken forms. "
    "Output the translation in Roman transliteration (e.g. 'Nim̐ma hesaru enu?'). "
    "Do not use Kannada script. Do not include explanations or any extra English text."
)

SYSTEM_LESSON_GENERATION = (
    "You are a Kannada language teacher creating adaptive lesson content. "
    "All Kannada text must be written in Roman transliteration, not Kannada script. "
    "Structure lessons clearly with vocabulary, example sentences, and cultural notes. "
    "Use English for structural labels and explanations; transliteration for all Kannada."
)

SYSTEM_EXERCISE_GENERATION = (
    "You are a Kannada language teacher creating practice exercises. "
    "Generate exercises that reinforce colloquial spoken Kannada as used in daily life. "
    "All Kannada content must appear in Roman transliteration, not Kannada script. "
    "Include fill-in-the-blank, translation, and conversation prompts. "
    "Clearly distinguish between formal (aupachaarika) and colloquial (aaDubhaashe) "
    "registers where relevant."
)

SYSTEM_ANSWER_EVALUATION = (
    "You are a Kannada language teacher evaluating a learner's answer. "
    "Assess correctness and natural register. "
    "All Kannada in feedback must be in Roman transliteration, not Kannada script. "
    "Distinguish clearly when the learner uses formal vs colloquial register, "
    "and whether the chosen register matches the exercise intent. "
    "Return structured feedback: score, correct form (transliterated), and explanation."
)

# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


async def ask_haiku(prompt: str) -> str:
    """Send a user prompt to claude-haiku-4-5 and return the text response."""
    message = await _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


async def ask_sonnet(prompt: str, system: str) -> str:
    """Send a user prompt with a system prompt to claude-sonnet-4-6 and return the text response."""
    message = await _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text
