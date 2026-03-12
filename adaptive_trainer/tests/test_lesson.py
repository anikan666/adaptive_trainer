"""Tests for the lesson generator service."""

import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test_access")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test_app_secret")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "test_phone_id")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")

from app.services.lesson import generate_lesson  # noqa: E402

SAMPLE_LESSON = """\
1. Explanation: Greetings are central to Kannada daily life...
2. Vocabulary: hegiddira — how are you; chennagide — it is good
3. Examples: Nim̐ma hesaru enu? — What is your name?
4. Cultural note: Always greet elders first.
"""


@pytest.mark.asyncio
async def test_generate_lesson_calls_sonnet():
    with patch(
        "app.services.lesson.ask_sonnet",
        new_callable=AsyncMock,
        return_value=SAMPLE_LESSON,
    ) as mock_ask:
        result = await generate_lesson(level=2, topic="greetings")

    assert mock_ask.awaited
    assert result == SAMPLE_LESSON


@pytest.mark.asyncio
async def test_generate_lesson_includes_level_in_prompt():
    with patch(
        "app.services.lesson.ask_sonnet",
        new_callable=AsyncMock,
        return_value=SAMPLE_LESSON,
    ) as mock_ask:
        await generate_lesson(level=3, topic="food")

    prompt_arg = mock_ask.call_args[0][0]
    assert "3/5" in prompt_arg
    assert "food" in prompt_arg


@pytest.mark.asyncio
async def test_generate_lesson_includes_srs_items():
    due = ["hegiddira", "chennagide"]
    with patch(
        "app.services.lesson.ask_sonnet",
        new_callable=AsyncMock,
        return_value=SAMPLE_LESSON,
    ) as mock_ask:
        await generate_lesson(level=1, topic="greetings", due_items=due)

    prompt_arg = mock_ask.call_args[0][0]
    assert "hegiddira" in prompt_arg
    assert "chennagide" in prompt_arg


@pytest.mark.asyncio
async def test_generate_lesson_no_srs_items():
    with patch(
        "app.services.lesson.ask_sonnet",
        new_callable=AsyncMock,
        return_value=SAMPLE_LESSON,
    ) as mock_ask:
        await generate_lesson(level=1, topic="greetings", due_items=None)

    prompt_arg = mock_ask.call_args[0][0]
    assert "Prioritise" not in prompt_arg
