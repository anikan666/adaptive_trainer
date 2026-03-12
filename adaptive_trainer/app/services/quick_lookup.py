"""Quick lookup service: translate an English phrase to colloquial Kannada.

Returns a compact response (Kannada script + romanization + usage note) sized
for WhatsApp readability (~200 chars).
"""

from app.services.claude_client import ask_haiku_with_system

SYSTEM_QUICK_LOOKUP = (
    "You are a Kannada language assistant. "
    "Given an English phrase, return the colloquial Kannada equivalent as spoken in everyday Bengaluru. "
    "Format your response EXACTLY as one line: <script> (<roman>) — <note>\n"
    "Where:\n"
    "  script  = the phrase in Kannada Unicode script\n"
    "  roman   = pronunciation guide in Roman transliteration\n"
    "  note    = one short phrase describing usage context (max 40 chars)\n"
    "Rules: no extra text, no newlines, total response under 200 characters."
)


async def quick_lookup(phrase: str) -> str:
    """Translate an English phrase to colloquial Kannada via claude-haiku.

    Args:
        phrase: English word or phrase to translate.

    Returns:
        One-line string in the format: ``<script> (<roman>) — <note>``
        e.g. ``ಅದು ತುಂಬಾ ಚೆನ್ನಾಗಿದೆ (adu tumba channagide) — complimenting something``
    """
    return await ask_haiku_with_system(phrase, SYSTEM_QUICK_LOOKUP)
