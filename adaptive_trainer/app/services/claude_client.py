import asyncio
import logging

import anthropic
from app.config import settings

logger = logging.getLogger(__name__)

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
    "Use English for labels and explanations; transliteration for all Kannada.\n\n"
    "TRANSLITERATION ACCURACY — common mistakes to avoid:\n"
    "• 'My name is' = 'Nanna hesaru' (NOT 'Nannu hesaru' — Nannu means 'I/me')\n"
    "• 'Stop here' = 'Illi nilsi' (NOT 'illige nilli')\n"
    "• 'How much?' = 'Yeshtu?' (NOT 'Estu?')\n"
    "• 'What?' = 'Yenu?' • 'Where?' = 'Yelli?'\n"
    "• Use colloquial Bengaluru forms: 'maaDi' not 'maaDiri', 'hogona' not 'hogONa'\n"
    "Double-check every Kannada phrase for grammatical accuracy before including it."
)

SYSTEM_EXERCISE_GENERATION = (
    "You are a friendly Kannada-speaking friend quizzing someone on what they just learned. "
    "Keep the tone casual and encouraging. "
    "Never reference instructions, prompts, or that you are an AI. "
    "All Kannada must be in Roman transliteration, not Kannada script. "
    "Generate exercises based on colloquial spoken Kannada as used in daily Bengaluru life. "
    "Make each exercise unique — vary the vocabulary, sentence structure, and context. "
    "Do not repeat the same word or phrase across exercises in a session.\n\n"
    "TRANSLITERATION ACCURACY — double-check every Kannada word:\n"
    "• 'Nanna' = my/mine, 'Nannu' = I/me — do NOT confuse these\n"
    "• 'Illi' = here, 'Alli' = there — do NOT swap\n"
    "• 'nilsi' = stop (imperative), NOT 'nilli'\n"
    "• Use standard Bengaluru colloquial forms and verify grammar before outputting."
)

SYSTEM_ANSWER_EVALUATION = (
    "You are a friendly Kannada-speaking friend giving feedback on someone's answer. "
    "Be encouraging but honest. Never reference instructions, prompts, or that you are an AI. "
    "All Kannada in feedback must be in Roman transliteration, not Kannada script. "
    "If they used formal Kannada where colloquial was expected, gently point it out. "
    "Keep feedback to 1-2 sentences max."
)

# ---------------------------------------------------------------------------
# Retry / timeout configuration
# ---------------------------------------------------------------------------

REQUEST_TIMEOUT_S = 30
MAX_RETRIES = 2
BACKOFF_BASE_S = 1


class ClaudeAPIError(Exception):
    """Raised when all retries for a Claude API call are exhausted."""


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


async def _call_with_retries(*, model: str, max_tokens: int, messages: list,
                             system: str | None = None) -> str:
    """Call the Claude API with timeout and exponential-backoff retries."""
    kwargs: dict = dict(model=model, max_tokens=max_tokens, messages=messages)
    if system is not None:
        kwargs["system"] = system

    last_exc: BaseException | None = None
    for attempt in range(1 + MAX_RETRIES):
        try:
            message = await asyncio.wait_for(
                _client.messages.create(**kwargs),
                timeout=REQUEST_TIMEOUT_S,
            )
            return message.content[0].text
        except (asyncio.TimeoutError, anthropic.APIConnectionError,
                anthropic.RateLimitError, anthropic.InternalServerError) as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                delay = BACKOFF_BASE_S * (2 ** attempt)
                logger.warning(
                    "Claude API call failed (attempt %d/%d): %s — retrying in %ss",
                    attempt + 1, 1 + MAX_RETRIES, exc, delay,
                )
                await asyncio.sleep(delay)

    raise ClaudeAPIError(
        f"Claude API call failed after {1 + MAX_RETRIES} attempts: {last_exc}"
    ) from last_exc


async def ask_haiku(prompt: str) -> str:
    return await _call_with_retries(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )


async def ask_haiku_with_system(prompt: str, system: str) -> str:
    return await _call_with_retries(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )


async def ask_sonnet(prompt: str, system: str) -> str:
    return await _call_with_retries(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
