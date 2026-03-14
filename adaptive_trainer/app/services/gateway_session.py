"""Gateway test session: roleplay-based assessment at the end of each level.

When all units in a level are complete, the learner can take a gateway test —
a multi-turn roleplay conversation that tests their ability to use level
vocabulary in a realistic Bengaluru context.
"""

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.gateway_scenarios import get_gateway_scenario
from app.db.queries import get_active_convo as _get_active_convo
from app.db.session import AsyncSessionLocal
from app.models.conversation import Conversation, ConversationMode
from app.models.learner import Learner
from app.services.claude_client import ask_sonnet
from app.services.curriculum import check_level_progression
from app.services.whatsapp_sender import send_message

logger = logging.getLogger(__name__)

_NO_GATEWAY_TEXT = "No active gateway test. Send 'lesson' to continue learning."

SYSTEM_GATEWAY_EVALUATION = (
    "You are evaluating a Kannada learner's performance in a roleplay gateway test. "
    "Assess their responses across the conversation. "
    "All Kannada must be in Roman transliteration.\n\n"
    "Return a JSON object with:\n"
    '- "passed": true/false (true if they demonstrated basic competency)\n'
    '- "score": 0.0-1.0 (overall performance)\n'
    '- "feedback": brief encouraging feedback (2-3 sentences)\n'
    '- "strengths": list of things they did well\n'
    '- "areas_to_improve": list of areas to work on\n\n'
    "Be encouraging but honest. Pass them if they showed genuine effort and "
    "got the basic communication across, even with mistakes."
)


async def start_gateway(phone: str, level: int) -> None:
    """Initiate a gateway roleplay test for the given level.

    Args:
        phone: Learner's phone number in E.164 format.
        level: The curriculum level to test (matches gateway scenario).
    """
    scenario = get_gateway_scenario(level)
    if scenario is None:
        await send_message(
            phone,
            f"No gateway test available for level {level} yet. "
            "Send 'lesson' to continue learning.",
        )
        return

    # Check for active session
    async with AsyncSessionLocal() as db:
        convo = await _get_active_convo(db, phone)
        if convo is not None and convo.mode in (
            ConversationMode.lesson,
            ConversationMode.review,
            ConversationMode.gateway_test,
        ):
            ctx = convo.lesson_context
            if ctx and (ctx.get("exercises") or ctx.get("items") or ctx.get("turns")):
                await send_message(
                    phone,
                    "You have a session in progress. "
                    "Type 'cancel' to end it or reply to continue.",
                )
                return

    gateway_context = {
        "level": level,
        "scenario_title": scenario["title"],
        "system_prompt": scenario["system_prompt"],
        "expected_turns": scenario["expected_turns"],
        "evaluation_criteria": scenario["evaluation_criteria"],
        "turns": [],
        "turn_count": 0,
    }

    # Add the initial AI message to the conversation history
    gateway_context["turns"].append({
        "role": "assistant",
        "content": scenario["setup_text"],
    })

    async with AsyncSessionLocal() as db:
        convo = await _get_or_create_convo(db, phone)
        convo.lesson_context = gateway_context
        convo.mode = ConversationMode.gateway_test
        await db.commit()

    logger.info(
        "start_gateway phone=%s level=%d scenario=%s",
        phone, level, scenario["title"],
    )
    await send_message(phone, scenario["setup_text"])


async def handle_gateway_turn(phone: str, answer: str) -> None:
    """Process a learner's response during a gateway roleplay.

    Args:
        phone: Learner's phone number in E.164 format.
        answer: The learner's roleplay response text.
    """
    async with AsyncSessionLocal() as db:
        convo = await _get_active_convo(db, phone)
        if convo is None or not convo.lesson_context:
            await send_message(phone, _NO_GATEWAY_TEXT)
            return
        ctx = dict(convo.lesson_context)

    required_keys = ("turns", "turn_count", "system_prompt", "expected_turns")
    if not all(k in ctx for k in required_keys):
        logger.warning("Corrupt gateway context for phone=%s", phone)
        async with AsyncSessionLocal() as db:
            convo = await _get_active_convo(db, phone)
            if convo is not None:
                convo.lesson_context = None
                convo.mode = ConversationMode.quick_lookup
                await db.commit()
        await send_message(phone, _NO_GATEWAY_TEXT)
        return

    turns = list(ctx["turns"])
    turn_count = ctx["turn_count"] + 1
    expected_turns = ctx["expected_turns"]

    # Record learner's response
    turns.append({"role": "user", "content": answer})

    # Check if we've reached the expected number of turns
    if turn_count >= expected_turns:
        # Save final turn and evaluate
        ctx["turns"] = turns
        ctx["turn_count"] = turn_count
        async with AsyncSessionLocal() as db:
            convo = await _get_active_convo(db, phone)
            if convo is not None:
                convo.lesson_context = ctx
                await db.commit()
        await _finish_gateway(phone)
        return

    # Generate the AI character's next response
    messages = _build_messages(turns)
    ai_response = await ask_sonnet(
        prompt=messages[-1]["content"] if messages else answer,
        system=ctx["system_prompt"],
    )

    turns.append({"role": "assistant", "content": ai_response})

    updated_ctx = {**ctx, "turns": turns, "turn_count": turn_count}
    async with AsyncSessionLocal() as db:
        convo = await _get_active_convo(db, phone)
        if convo is not None:
            convo.lesson_context = updated_ctx
            await db.commit()

    await send_message(phone, ai_response)


async def _finish_gateway(phone: str) -> None:
    """Evaluate the gateway roleplay and send results."""
    async with AsyncSessionLocal() as db:
        convo = await _get_active_convo(db, phone)
        if convo is None or not convo.lesson_context:
            return
        ctx = dict(convo.lesson_context)

    level = ctx.get("level", 1)
    turns = ctx.get("turns", [])
    criteria = ctx.get("evaluation_criteria", [])
    scenario_title = ctx.get("scenario_title", "Gateway Test")

    # Build evaluation prompt
    conversation_text = "\n".join(
        f"{'Learner' if t['role'] == 'user' else 'Character'}: {t['content']}"
        for t in turns
    )

    eval_prompt = (
        f"Scenario: {scenario_title}\n"
        f"Level: {level}\n\n"
        f"Evaluation criteria:\n"
        + "\n".join(f"- {c}" for c in criteria)
        + f"\n\nConversation:\n{conversation_text}\n\n"
        "Evaluate the learner's performance and return JSON."
    )

    try:
        raw = await ask_sonnet(eval_prompt, system=SYSTEM_GATEWAY_EVALUATION)
        evaluation = _parse_evaluation(raw)
    except Exception:
        logger.exception("Gateway evaluation failed for phone=%s", phone)
        evaluation = {
            "passed": True,
            "score": 0.5,
            "feedback": "Great effort! Keep practicing.",
            "strengths": [],
            "areas_to_improve": [],
        }

    passed = evaluation.get("passed", False)
    score = evaluation.get("score", 0.0)
    feedback = evaluation.get("feedback", "")
    strengths = evaluation.get("strengths", [])
    areas = evaluation.get("areas_to_improve", [])

    # Build result message
    result_parts = [f"Gateway Test Complete: {scenario_title}\n"]
    result_parts.append(f"Result: {'PASSED' if passed else 'NOT YET'}")
    result_parts.append(f"Score: {score:.0%}\n")
    result_parts.append(feedback)

    if strengths:
        result_parts.append("\nStrengths:")
        for s in strengths:
            result_parts.append(f"  + {s}")
    if areas:
        result_parts.append("\nAreas to improve:")
        for a in areas:
            result_parts.append(f"  - {a}")

    if passed:
        result_parts.append("\nCongratulations! You've passed the gateway test!")
        progression_level = await check_level_progression(phone)
        if progression_level is not None:
            result_parts.append(f"Advanced to Level {progression_level}!")
        result_parts.append("Send 'lesson' to continue learning.")
    else:
        result_parts.append(
            "\nKeep practicing! Review the vocabulary and try again. "
            "Send 'lesson' to continue studying, or 'review' to practice words."
        )

    await send_message(phone, "\n".join(result_parts))

    logger.info(
        "finish_gateway phone=%s level=%d passed=%s score=%.2f",
        phone, level, passed, score,
    )

    # Clear gateway state
    async with AsyncSessionLocal() as db:
        convo = await _get_active_convo(db, phone)
        if convo is not None:
            convo.lesson_context = None
            convo.mode = ConversationMode.quick_lookup
            await db.commit()


def _build_messages(turns: list[dict]) -> list[dict]:
    """Build a simplified message list from turn history for the AI prompt."""
    # For ask_sonnet we only pass the last user message as the prompt.
    # The system prompt handles character context.
    # We build a concatenated conversation context as the prompt.
    if not turns:
        return []

    # Build conversation context for the AI
    context_parts = []
    for t in turns[:-1]:  # All but last
        role_label = "Learner" if t["role"] == "user" else "You"
        context_parts.append(f"{role_label}: {t['content']}")

    last = turns[-1]
    if context_parts:
        context = "\n".join(context_parts)
        prompt = f"Previous conversation:\n{context}\n\nLearner: {last['content']}\n\nRespond in character:"
    else:
        prompt = last["content"]

    return [{"role": "user", "content": prompt}]


def _parse_evaluation(raw: str) -> dict:
    """Parse the JSON evaluation from the AI response."""
    # Try to extract JSON from the response
    try:
        # Look for JSON block
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: assume they passed with moderate score
    return {
        "passed": True,
        "score": 0.5,
        "feedback": raw[:200] if raw else "Good effort!",
        "strengths": [],
        "areas_to_improve": [],
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_or_create_convo(db: AsyncSession, phone: str) -> Conversation:
    """Return the active conversation, creating one if needed."""
    convo = await _get_active_convo(db, phone)
    if convo is None:
        convo = Conversation(
            phone_number=phone,
            mode=ConversationMode.gateway_test,
            lesson_context=None,
        )
        db.add(convo)
        await db.flush()
    return convo
