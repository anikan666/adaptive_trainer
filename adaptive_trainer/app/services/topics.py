"""Topic suggestion service: level-appropriate Bengaluru scenario suggestions."""

import logging
import random

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.learner import Learner

logger = logging.getLogger(__name__)

_TOPIC_POOLS: dict[str, list[tuple[str, str]]] = {
    "beginner": [
        ("greetings", "Basic hello/goodbye with auto drivers and shopkeepers"),
        ("numbers", "Counting and prices at local markets"),
        ("auto rickshaw", "Telling the driver where to go in Bengaluru"),
        ("ordering food", "Ordering dosa, idli, or coffee at a darshini"),
        ("asking directions", "Finding your way around MG Road or Jayanagar"),
        ("introducing yourself", "Telling people your name and where you're from"),
        ("buying vegetables", "Shopping at the local pushcart or KR Market"),
        ("at the bus stop", "Asking which BMTC bus to take"),
    ],
    "intermediate": [
        ("bargaining at markets", "Negotiating prices at Commercial Street"),
        ("phone conversations", "Making appointments or calling a plumber"),
        ("describing people", "Talking about family members and friends"),
        ("giving opinions", "Sharing what you think about food or movies"),
        ("weekend plans", "Discussing plans to visit Nandi Hills or Lalbagh"),
        ("at the doctor", "Explaining symptoms at a clinic"),
        ("restaurant review", "Recommending your favourite Bengaluru eatery"),
        ("festival talk", "Chatting about Dasara, Ugadi, or Sankranti"),
    ],
    "advanced": [
        ("idioms", "Common Kannada idioms and when to use them"),
        ("humor", "Understanding Kannada jokes and wordplay"),
        ("news discussion", "Talking about local Bengaluru news"),
        ("storytelling", "Narrating a short story or incident"),
        ("debate", "Agreeing and disagreeing politely in Kannada"),
        ("office small talk", "Water-cooler chat with Kannada-speaking colleagues"),
        ("local history", "Discussing Bengaluru landmarks and their history"),
        ("movie reviews", "Discussing Kannada films and actors"),
    ],
}

_SUGGESTIONS_COUNT = 6

_NOT_ONBOARDED_TEXT = (
    "You haven't started learning yet!\n"
    "Send *lesson* to begin your first Kannada lesson."
)


def _bracket_for_ring(ring: int) -> str:
    if ring <= 1:
        return "beginner"
    if ring <= 3:
        return "intermediate"
    return "advanced"


async def get_topic_suggestions(phone: str) -> str:
    """Return a formatted list of topic suggestions for the learner's level."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Learner).where(Learner.phone_number == phone)
        )
        learner = result.scalar_one_or_none()

    if learner is None:
        return _NOT_ONBOARDED_TEXT

    bracket = _bracket_for_ring(learner.current_ring)
    pool = _TOPIC_POOLS[bracket]
    picks = random.sample(pool, min(_SUGGESTIONS_COUNT, len(pool)))

    lines = [f"Topics for your level ({bracket}):"]
    for i, (name, desc) in enumerate(picks, 1):
        lines.append(f"{i}. *{name}* — {desc}")
    lines.append("\nSend *lesson <topic>* to start!")

    return "\n".join(lines)
