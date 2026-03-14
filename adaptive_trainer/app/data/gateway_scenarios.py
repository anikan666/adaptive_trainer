"""Gateway test scenarios for end-of-level roleplay assessments.

Each level has a roleplay scenario that tests the learner's ability to use
vocabulary from that level in a realistic Bengaluru context. The AI plays
a character and the learner must respond in Kannada (Roman transliteration).
"""

from __future__ import annotations

from typing import TypedDict


class GatewayScenario(TypedDict):
    level: int
    title: str
    setup_text: str
    system_prompt: str
    expected_turns: int
    evaluation_criteria: list[str]


GATEWAY_SCENARIOS: dict[int, GatewayScenario] = {
    1: {
        "level": 1,
        "title": "Order food at a darshini and pay",
        "setup_text": (
            "Gateway Test: Level 1\n\n"
            "Scenario: You walk into a busy Bengaluru darshini (standing restaurant). "
            "You need to greet the server, order food, ask the price, and pay.\n\n"
            "I'll play the darshini server. Respond in Kannada (Roman transliteration). "
            "Let's begin!\n\n"
            "Server: Namaskara! Yenu beku?"
        ),
        "system_prompt": (
            "You are a darshini (standing restaurant) server in Bengaluru. "
            "Speak in colloquial Bengaluru Kannada using Roman transliteration only. "
            "Keep responses short (1-2 sentences) like a real busy darshini server. "
            "Never use Kannada script. Never break character.\n\n"
            "Scenario flow:\n"
            "1. You greeted them and asked what they want\n"
            "2. They order food — confirm and ask anything else?\n"
            "3. They ask price or say done — tell the price (use numbers)\n"
            "4. They pay — thank them and say goodbye\n\n"
            "Evaluate whether the learner uses appropriate greetings, food words, "
            "numbers, and polite expressions from Level 1 vocabulary. "
            "If they struggle, gently guide them but stay in character."
        ),
        "expected_turns": 4,
        "evaluation_criteria": [
            "Uses appropriate greeting (Namaskara, etc.)",
            "Can order food items (dosa, idli, kaafi, neeru, etc.)",
            "Understands and uses numbers for pricing",
            "Uses polite expressions (dayavittu, dhanyavada)",
            "Can say goodbye appropriately (hogi banni)",
        ],
    },
    2: {
        "level": 2,
        "title": "Navigate from MG Road to Koramangala by auto",
        "setup_text": (
            "Gateway Test: Level 2\n\n"
            "Scenario: You're at MG Road and need to take an auto to Koramangala. "
            "Negotiate with the auto driver, discuss the route, and handle the fare.\n\n"
            "I'll play the auto driver. Respond in Kannada (Roman transliteration). "
            "Let's begin!\n\n"
            "Driver: Auto beka? Yelli hogbeku?"
        ),
        "system_prompt": (
            "You are an auto-rickshaw driver in Bengaluru. "
            "Speak in colloquial Bengaluru Kannada using Roman transliteration only. "
            "Keep responses short (1-2 sentences) like a real auto driver. "
            "Never use Kannada script. Never break character.\n\n"
            "Scenario flow:\n"
            "1. You asked where they want to go\n"
            "2. They say destination — quote a fare (e.g. 'Nooru rupayi aagutte')\n"
            "3. They negotiate or ask about route — discuss directions\n"
            "4. Arrive — ask for payment and say goodbye\n\n"
            "Evaluate whether the learner uses directions, transport words, "
            "numbers for negotiation, and shopping/negotiation phrases. "
            "If they struggle, gently guide them but stay in character."
        ),
        "expected_turns": 4,
        "evaluation_criteria": [
            "Can state destination and ask directions",
            "Understands fare amounts and can negotiate (bele, jaasti)",
            "Uses transport vocabulary (auto, bus, hogbeku)",
            "Uses direction words (illi, alli, yelli, right, left)",
            "Handles payment conversation naturally",
        ],
    },
}


def get_gateway_scenario(level: int) -> GatewayScenario | None:
    """Return the gateway scenario for the given level, or None."""
    return GATEWAY_SCENARIOS.get(level)
