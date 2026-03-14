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
    0: {
        "level": 0,
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
    1: {
        "level": 1,
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
    2: {
        "level": 2,
        "title": "Getting to know a new colleague over coffee",
        "setup_text": (
            "Gateway Test: Ring 2\n\n"
            "Scenario: You've just joined a new office in Bengaluru. A colleague "
            "invites you for coffee and wants to get to know you. Talk about yourself, "
            "your family, your work, and your interests.\n\n"
            "I'll play your colleague. Respond in Kannada (Roman transliteration). "
            "Let's begin!\n\n"
            "Colleague: Hey, namaskara! Naanu Priya. Coffee hogona? Nimma bagge heli!"
        ),
        "system_prompt": (
            "You are Priya, a friendly Bengaluru office colleague meeting someone new. "
            "Speak in colloquial Bengaluru Kannada using Roman transliteration only. "
            "Keep responses short and natural like a real conversation. "
            "Never use Kannada script. Never break character.\n\n"
            "Scenario flow:\n"
            "1. You introduced yourself and asked them to share about themselves\n"
            "2. They introduce themselves — ask about their family or where they're from\n"
            "3. They share — ask about hobbies, what they like about Bengaluru, weekend plans\n"
            "4. They respond — share something about yourself too, express opinions\n"
            "5. Wrap up — say it was nice talking, suggest meeting again\n\n"
            "Evaluate whether the learner can sustain a casual conversation, "
            "express preferences, ask questions back, and use connectors naturally."
        ),
        "expected_turns": 5,
        "evaluation_criteria": [
            "Can introduce themselves (name, origin, work)",
            "Can talk about family members",
            "Expresses likes and preferences (ishta, ishta illa)",
            "Asks questions back (yaaru, yenu, yelli, hege)",
            "Uses connectors to flow naturally (aadre, adakke, matthu)",
            "Sustains 3-5 exchanges without falling back to English",
        ],
    },
    3: {
        "level": 3,
        "title": "Tell a friend about a weekend trip that went wrong",
        "setup_text": (
            "Gateway Test: Ring 3\n\n"
            "Scenario: You went on a weekend trip and things didn't go as planned. "
            "Tell your Bengaluru friend the whole story — what happened, what went wrong, "
            "how you solved problems, and what you'd do differently.\n\n"
            "I'll play your friend. Respond in Kannada (Roman transliteration). "
            "Let's begin!\n\n"
            "Friend: Hey maccha! Weekend trip hege aaythu? Yella sari aaytha?"
        ),
        "system_prompt": (
            "You are a close Bengaluru friend listening to someone's weekend trip story. "
            "Speak in colloquial Bengaluru Kannada using Roman transliteration only. "
            "React naturally — ask follow-up questions, express surprise, sympathy, humour. "
            "Never use Kannada script. Never break character.\n\n"
            "Scenario flow:\n"
            "1. You asked how their trip went\n"
            "2. They start telling — react and ask what happened next\n"
            "3. They describe problems — ask how they handled it\n"
            "4. They explain solutions — react, maybe share a similar experience\n"
            "5. They describe outcome — ask if they'd go again, compare experiences\n"
            "6. Wrap up with a joke or encouragement\n\n"
            "Evaluate whether the learner can narrate in past tense, use conditionals, "
            "describe things, solve problems, and tell a coherent story."
        ),
        "expected_turns": 6,
        "evaluation_criteria": [
            "Uses past tense naturally (hodhe, noodhe, tinde, maadide)",
            "Can describe a sequence of events (modlu, nanthara, koneyli)",
            "Uses conditionals (bandre, maadidre, gothidre)",
            "Can describe things and situations (dodda, chikka, bisi, thandi)",
            "Handles problem-solving vocabulary naturally",
            "Makes comparisons where appropriate",
            "Tells a coherent multi-turn narrative",
        ],
    },
    4: {
        "level": 4,
        "title": "Debate with a friend about Bengaluru culture",
        "setup_text": (
            "Gateway Test: Ring 4\n\n"
            "Scenario: You and a Bengaluru friend are having a lively debate about "
            "whether Bengaluru is losing its Kannada culture. Use slang, idioms, "
            "formal and informal registers, and cultural references.\n\n"
            "I'll play your friend. Respond in Kannada (Roman transliteration). "
            "Let's begin!\n\n"
            "Friend: Guru, ondu vishya helbeku. Bengaluru-alli Kannada culture "
            "kammi aagthide antha nanage ansuthe. Neenu yenu helthiya?"
        ),
        "system_prompt": (
            "You are a passionate Bengaluru local debating whether Bengaluru is losing "
            "its Kannada culture. Speak in colloquial Bengaluru Kannada using Roman "
            "transliteration only. Use slang (guru, maccha, sakkath), idioms, "
            "and mix formal/informal registers. Be opinionated but friendly. "
            "Never use Kannada script. Never break character.\n\n"
            "Scenario flow:\n"
            "1. You raised the topic — Bengaluru losing Kannada culture\n"
            "2. They respond — push back or agree, ask for specifics\n"
            "3. Discuss festivals, food culture, media, slang\n"
            "4. They share opinions — debate respectfully, use idioms\n"
            "5. Discuss solutions or silver linings\n"
            "6. Agree to disagree or find common ground, wrap up warmly\n\n"
            "Evaluate whether the learner can use Bengaluru slang, switch registers, "
            "use idioms, reference culture, and argue a point coherently."
        ),
        "expected_turns": 6,
        "evaluation_criteria": [
            "Uses Bengaluru slang naturally (guru, maccha, sakkath, mass)",
            "Can switch between formal and informal registers",
            "Uses idioms or proverbs appropriately",
            "References Kannada culture (festivals, food, media)",
            "Can argue a point and express strong opinions",
            "Understands and responds to humour or wordplay",
            "Demonstrates expressive fluency across all previous ring skills",
        ],
    },
}


def get_gateway_scenario(level: int) -> GatewayScenario | None:
    """Return the gateway scenario for the given level, or None."""
    return GATEWAY_SCENARIOS.get(level)
