"""Tests for the learner onboarding flow."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test_access")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test_app_secret")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "test_phone_id")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")

from app.models.conversation import Conversation, ConversationMode  # noqa: E402
from app.models.learner import Learner  # noqa: E402
from app.services.onboarding import (  # noqa: E402
    _INVALID_LEVEL,
    _MAIN_MENU,
    _WELCOME,
    handle_onboarding,
    needs_onboarding,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(learner=None, convo=None):
    """Build a minimal async DB mock."""
    db = AsyncMock()

    async def _execute(stmt):
        result = MagicMock()
        # Determine query from the table being queried via compile-time check
        # We inspect what was passed to scalar_one_or_none indirectly via fixture.
        result.scalar_one_or_none.return_value = None
        return result

    db.execute = AsyncMock(side_effect=_execute)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    return db


# ---------------------------------------------------------------------------
# needs_onboarding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_needs_onboarding_true_when_no_learner():
    """Returns True when no Learner record exists for the phone number."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.onboarding.AsyncSessionLocal", return_value=mock_db):
        result = await needs_onboarding("15551234567")

    assert result is True


@pytest.mark.asyncio
async def test_needs_onboarding_false_when_learner_exists():
    """Returns False when a Learner record already exists."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = Learner(phone_number="15551234567", level=2)

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.onboarding.AsyncSessionLocal", return_value=mock_db):
        result = await needs_onboarding("15551234567")

    assert result is False


# ---------------------------------------------------------------------------
# handle_onboarding — first contact
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_contact_sends_welcome_and_creates_convo():
    """First message from unknown number → welcome sent, onboarding convo created."""
    # Both learner and convo queries return None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.onboarding.AsyncSessionLocal", return_value=mock_db),
        patch("app.services.onboarding.send_message", new_callable=AsyncMock) as mock_send,
    ):
        await handle_onboarding("15551234567", "hi")

    mock_send.assert_awaited_once_with("15551234567", _WELCOME)
    mock_db.add.assert_called_once()
    added_convo = mock_db.add.call_args[0][0]
    assert isinstance(added_convo, Conversation)
    assert added_convo.mode == ConversationMode.onboarding
    assert added_convo.lesson_context == {"step": "ask_name"}


# ---------------------------------------------------------------------------
# handle_onboarding — ask_name step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ask_name_saves_name_and_asks_level():
    """User replies with name → convo updated, level question sent."""
    convo = Conversation(
        phone_number="15551234567",
        mode=ConversationMode.onboarding,
        lesson_context={"step": "ask_name"},
    )

    call_count = 0

    async def _execute(stmt):
        nonlocal call_count
        result = MagicMock()
        # First call: learner query → None; second call: convo query → convo
        result.scalar_one_or_none.return_value = None if call_count == 0 else convo
        call_count += 1
        return result

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=_execute)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.onboarding.AsyncSessionLocal", return_value=mock_db),
        patch("app.services.onboarding.send_message", new_callable=AsyncMock) as mock_send,
    ):
        await handle_onboarding("15551234567", "Priya")

    mock_send.assert_awaited_once()
    sent_text = mock_send.call_args[0][1]
    assert "Priya" in sent_text
    assert convo.lesson_context == {"step": "ask_level", "name": "Priya"}


@pytest.mark.asyncio
async def test_ask_name_empty_input_reprompts():
    """Empty name input → reprompt, convo not updated."""
    convo = Conversation(
        phone_number="15551234567",
        mode=ConversationMode.onboarding,
        lesson_context={"step": "ask_name"},
    )

    call_count = 0

    async def _execute(stmt):
        nonlocal call_count
        result = MagicMock()
        result.scalar_one_or_none.return_value = None if call_count == 0 else convo
        call_count += 1
        return result

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=_execute)
    mock_db.commit = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.onboarding.AsyncSessionLocal", return_value=mock_db),
        patch("app.services.onboarding.send_message", new_callable=AsyncMock) as mock_send,
    ):
        await handle_onboarding("15551234567", "   ")

    mock_send.assert_awaited_once()
    assert "name" in mock_send.call_args[0][1].lower()
    # Convo not updated
    assert convo.lesson_context == {"step": "ask_name"}
    mock_db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# handle_onboarding — ask_level step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ask_level_valid_creates_learner_and_sends_main_menu():
    """Valid level reply → Learner created, main menu sent."""
    convo = Conversation(
        phone_number="15551234567",
        mode=ConversationMode.onboarding,
        lesson_context={"step": "ask_level", "name": "Priya"},
    )

    call_count = 0

    async def _execute(stmt):
        nonlocal call_count
        result = MagicMock()
        result.scalar_one_or_none.return_value = None if call_count == 0 else convo
        call_count += 1
        return result

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=_execute)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.onboarding.AsyncSessionLocal", return_value=mock_db),
        patch("app.services.onboarding.send_message", new_callable=AsyncMock) as mock_send,
    ):
        await handle_onboarding("15551234567", "2")

    mock_send.assert_awaited_once_with("15551234567", _MAIN_MENU)
    mock_db.add.assert_called_once()
    added = mock_db.add.call_args[0][0]
    assert isinstance(added, Learner)
    assert added.phone_number == "15551234567"
    assert added.level == 2
    assert convo.lesson_context == {"step": "complete", "name": "Priya"}


@pytest.mark.asyncio
async def test_ask_level_boundary_values():
    """Level 1 and 5 are both valid."""
    for level_str in ("1", "5"):
        convo = Conversation(
            phone_number="15551234567",
            mode=ConversationMode.onboarding,
            lesson_context={"step": "ask_level", "name": "Test"},
        )

        call_count = 0

        async def _execute(stmt, _convo=convo):
            nonlocal call_count
            result = MagicMock()
            result.scalar_one_or_none.return_value = None if call_count == 0 else _convo
            call_count += 1
            return result

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=_execute)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.services.onboarding.AsyncSessionLocal", return_value=mock_db),
            patch("app.services.onboarding.send_message", new_callable=AsyncMock) as mock_send,
        ):
            await handle_onboarding("15551234567", level_str)

        mock_send.assert_awaited_once_with("15551234567", _MAIN_MENU)


@pytest.mark.asyncio
async def test_ask_level_invalid_text_reprompts():
    """Non-numeric level input → reprompt, no learner created."""
    convo = Conversation(
        phone_number="15551234567",
        mode=ConversationMode.onboarding,
        lesson_context={"step": "ask_level", "name": "Priya"},
    )

    call_count = 0

    async def _execute(stmt):
        nonlocal call_count
        result = MagicMock()
        result.scalar_one_or_none.return_value = None if call_count == 0 else convo
        call_count += 1
        return result

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=_execute)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.onboarding.AsyncSessionLocal", return_value=mock_db),
        patch("app.services.onboarding.send_message", new_callable=AsyncMock) as mock_send,
    ):
        await handle_onboarding("15551234567", "advanced")

    mock_send.assert_awaited_once_with("15551234567", _INVALID_LEVEL)
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_ask_level_out_of_range_reprompts():
    """Level 0 or 6 → reprompt."""
    for bad_level in ("0", "6", "-1"):
        convo = Conversation(
            phone_number="15551234567",
            mode=ConversationMode.onboarding,
            lesson_context={"step": "ask_level", "name": "Priya"},
        )

        call_count = 0

        async def _execute(stmt, _convo=convo):
            nonlocal call_count
            result = MagicMock()
            result.scalar_one_or_none.return_value = None if call_count == 0 else _convo
            call_count += 1
            return result

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=_execute)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.services.onboarding.AsyncSessionLocal", return_value=mock_db),
            patch("app.services.onboarding.send_message", new_callable=AsyncMock) as mock_send,
        ):
            await handle_onboarding("15551234567", bad_level)

        mock_send.assert_awaited_once_with("15551234567", _INVALID_LEVEL)


# ---------------------------------------------------------------------------
# handle_onboarding — already onboarded
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_already_onboarded_does_nothing():
    """Learner record exists → handle_onboarding returns without sending a message."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = Learner(phone_number="15551234567", level=3)

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.onboarding.AsyncSessionLocal", return_value=mock_db),
        patch("app.services.onboarding.send_message", new_callable=AsyncMock) as mock_send,
    ):
        await handle_onboarding("15551234567", "hello again")

    mock_send.assert_not_awaited()
