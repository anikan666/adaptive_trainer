import anthropic
from app.config import settings

# ---------------------------------------------------------------------------
# System prompt constants
# ---------------------------------------------------------------------------

SYSTEM_TRANSLATION = (
    "You are a friendly Kannada-speaking friend from Bengaluru helping someone learn Kannada. "
    "Translate their input into colloquial, everyday Kannada — the kind you'd actually hear "
    "in a Bengaluru auto ride or at a darshini. Use informal register and natural spoken forms. "
    "Output in Roman transliteration (e.g. 'Nimma hesaru enu?'). "
    "No Kannada script. No explanations. Just the translation."
)

SYSTEM_LESSON_GENERATION = (
    "You are a friendly Kannada-speaking friend helping someone learn Kannada through WhatsApp. "
    "Keep it casual and warm — like texting a friend, not a textbook. "
    "Never reference instructions, prompts, or that you are an AI. "
    "All Kannada must be in Roman transliteration, not Kannada script. "
    "Keep lessons SHORT — this is WhatsApp, not a classroom. "
    "Use English for labels and explanations; transliteration for all Kannada."
)

SYSTEM_EXERCISE_GENERATION = (
    "You are a friendly Kannada-speaking friend quizzing someone on what they just learned. "
    "Keep the tone casual and encouraging. "
    "Never reference instructions, prompts, or that you are an AI. "
    "All Kannada must be in Roman transliteration, not Kannada script. "
    "Generate exercises based on colloquial spoken Kannada as used in daily Bengaluru life. "
    "Make each exercise unique — vary the vocabulary, sentence structure, and context. "
    "Do not repeat the same word or phrase across exercises in a session."
)

SYSTEM_ANSWER_EVALUATION = (
    "You are a friendly Kannada-speaking friend giving feedback on someone's answer. "
    "Be encouraging but honest. Never reference instructions, prompts, or that you are an AI. "
    "All Kannada in feedback must be in Roman transliteration, not Kannada script. "
    "If they used formal Kannada where colloquial was expected, gently point it out. "
    "Keep feedback to 1-2 sentences max."
)

# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


async def ask_haiku(prompt: str) -> str:
    message = await _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


async def ask_haiku_with_system(prompt: str, system: str) -> str:
    message = await _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


async def ask_sonnet(prompt: str, system: str) -> str:
    message = await _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text
