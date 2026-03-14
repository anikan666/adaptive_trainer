"""Tests for the gateway test session service."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test_access")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test_app_secret")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "test_phone_id")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")

from app.data.gateway_scenarios import get_gateway_scenario, GATEWAY_SCENARIOS  # noqa: E402
from app.models.conversation import Conversation, ConversationMode  # noqa: E402
from app.services.gateway_session import (  # noqa: E402
    _build_messages,
    _parse_evaluation,
    start_gateway,
    handle_gateway_turn,
)

PHONE = "14155550001"


def _make_convo(lesson_context=None, mode=ConversationMode.gateway_test):
    convo = MagicMock(spec=Conversation)
    convo.mode = mode
    convo.lesson_context = lesson_context
    return convo


# ---------------------------------------------------------------------------
# Gateway scenarios data
# ---------------------------------------------------------------------------


class TestGatewayScenarios:
    def test_level_1_scenario_exists(self):
        scenario = get_gateway_scenario(1)
        assert scenario is not None
        assert scenario["level"] == 1
        assert scenario["expected_turns"] == 4
        assert len(scenario["evaluation_criteria"]) > 0

    def test_level_2_scenario_exists(self):
        scenario = get_gateway_scenario(2)
        assert scenario is not None
        assert scenario["level"] == 2
        assert scenario["expected_turns"] == 4

    def test_nonexistent_level_returns_none(self):
        assert get_gateway_scenario(99) is None
        assert get_gateway_scenario(0) is None


# ---------------------------------------------------------------------------
# _parse_evaluation
# ---------------------------------------------------------------------------


class TestParseEvaluation:
    def test_valid_json(self):
        raw = '{"passed": true, "score": 0.8, "feedback": "Great job!", "strengths": ["greeting"], "areas_to_improve": ["numbers"]}'
        result = _parse_evaluation(raw)
        assert result["passed"] is True
        assert result["score"] == 0.8
        assert result["feedback"] == "Great job!"

    def test_json_embedded_in_text(self):
        raw = 'Here is the evaluation:\n{"passed": false, "score": 0.3, "feedback": "Needs work.", "strengths": [], "areas_to_improve": ["vocabulary"]}\nEnd.'
        result = _parse_evaluation(raw)
        assert result["passed"] is False
        assert result["score"] == 0.3

    def test_invalid_json_fallback(self):
        raw = "This is not JSON at all"
        result = _parse_evaluation(raw)
        assert result["passed"] is True
        assert result["score"] == 0.5
        assert "This is not JSON" in result["feedback"]

    def test_empty_string_fallback(self):
        result = _parse_evaluation("")
        assert result["passed"] is True
        assert result["score"] == 0.5


# ---------------------------------------------------------------------------
# _build_messages
# ---------------------------------------------------------------------------


class TestBuildMessages:
    def test_empty_turns(self):
        assert _build_messages([]) == []

    def test_single_user_turn(self):
        turns = [{"role": "user", "content": "Namaskara"}]
        messages = _build_messages(turns)
        assert len(messages) == 1
        assert messages[0]["content"] == "Namaskara"

    def test_multi_turn_builds_context(self):
        turns = [
            {"role": "assistant", "content": "Namaskara! Yenu beku?"},
            {"role": "user", "content": "Ondu dosa kodi"},
        ]
        messages = _build_messages(turns)
        assert len(messages) == 1
        assert "Namaskara! Yenu beku?" in messages[0]["content"]
        assert "Ondu dosa kodi" in messages[0]["content"]


# ---------------------------------------------------------------------------
# start_gateway
# ---------------------------------------------------------------------------


class TestStartGateway:
    @pytest.mark.asyncio
    @patch("app.services.gateway_session.send_message", new_callable=AsyncMock)
    async def test_no_scenario_for_level(self, mock_send):
        with patch("app.services.gateway_session._get_active_convo", new_callable=AsyncMock, return_value=None):
            with patch("app.services.gateway_session.AsyncSessionLocal") as mock_session_cls:
                mock_db = AsyncMock()
                mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                await start_gateway(PHONE, 99)

        mock_send.assert_called_once()
        assert "No gateway test available" in mock_send.call_args[0][1]

    @pytest.mark.asyncio
    @patch("app.services.gateway_session.send_message", new_callable=AsyncMock)
    async def test_active_session_blocks_start(self, mock_send):
        convo = _make_convo(lesson_context={"turns": [{"role": "assistant", "content": "hi"}]})

        with patch("app.services.gateway_session._get_active_convo", new_callable=AsyncMock, return_value=convo):
            with patch("app.services.gateway_session.AsyncSessionLocal") as mock_session_cls:
                mock_db = AsyncMock()
                mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                await start_gateway(PHONE, 1)

        mock_send.assert_called_once()
        assert "session in progress" in mock_send.call_args[0][1]

    @pytest.mark.asyncio
    @patch("app.services.gateway_session.send_message", new_callable=AsyncMock)
    async def test_start_gateway_success(self, mock_send):
        mock_convo = _make_convo(lesson_context=None, mode=ConversationMode.quick_lookup)

        with patch("app.services.gateway_session._get_active_convo", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [None, mock_convo]
            with patch("app.services.gateway_session._get_or_create_convo", new_callable=AsyncMock, return_value=mock_convo):
                with patch("app.services.gateway_session.AsyncSessionLocal") as mock_session_cls:
                    mock_db = AsyncMock()
                    mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                    mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                    await start_gateway(PHONE, 1)

        # Should send the scenario setup text
        mock_send.assert_called_once()
        sent_text = mock_send.call_args[0][1]
        assert "Gateway Test: Level 1" in sent_text
        assert "darshini" in sent_text


# ---------------------------------------------------------------------------
# handle_gateway_turn
# ---------------------------------------------------------------------------


class TestHandleGatewayTurn:
    @pytest.mark.asyncio
    @patch("app.services.gateway_session.send_message", new_callable=AsyncMock)
    async def test_no_active_session(self, mock_send):
        with patch("app.services.gateway_session._get_active_convo", new_callable=AsyncMock, return_value=None):
            with patch("app.services.gateway_session.AsyncSessionLocal") as mock_session_cls:
                mock_db = AsyncMock()
                mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                await handle_gateway_turn(PHONE, "Namaskara")

        mock_send.assert_called_once()
        assert "No active gateway test" in mock_send.call_args[0][1]

    @pytest.mark.asyncio
    @patch("app.services.gateway_session.send_message", new_callable=AsyncMock)
    @patch("app.services.gateway_session.ask_sonnet", new_callable=AsyncMock)
    async def test_mid_conversation_turn(self, mock_ask, mock_send):
        mock_ask.return_value = "Sari, ondu dosa. Bere yenu beku?"

        ctx = {
            "level": 1,
            "scenario_title": "Order food at a darshini and pay",
            "system_prompt": "You are a darshini server...",
            "expected_turns": 4,
            "evaluation_criteria": ["Uses greeting"],
            "turns": [
                {"role": "assistant", "content": "Namaskara! Yenu beku?"},
            ],
            "turn_count": 0,
        }
        convo = _make_convo(lesson_context=ctx)

        with patch("app.services.gateway_session._get_active_convo", new_callable=AsyncMock, return_value=convo):
            with patch("app.services.gateway_session.AsyncSessionLocal") as mock_session_cls:
                mock_db = AsyncMock()
                mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                await handle_gateway_turn(PHONE, "Ondu dosa kodi")

        mock_ask.assert_called_once()
        mock_send.assert_called_once_with(PHONE, "Sari, ondu dosa. Bere yenu beku?")

    @pytest.mark.asyncio
    @patch("app.services.gateway_session._finish_gateway", new_callable=AsyncMock)
    @patch("app.services.gateway_session.send_message", new_callable=AsyncMock)
    async def test_final_turn_triggers_finish(self, mock_send, mock_finish):
        ctx = {
            "level": 1,
            "scenario_title": "Order food",
            "system_prompt": "You are a server",
            "expected_turns": 2,
            "evaluation_criteria": [],
            "turns": [
                {"role": "assistant", "content": "Namaskara!"},
                {"role": "user", "content": "Dosa kodi"},
            ],
            "turn_count": 1,
        }
        convo = _make_convo(lesson_context=ctx)

        with patch("app.services.gateway_session._get_active_convo", new_callable=AsyncMock, return_value=convo):
            with patch("app.services.gateway_session.AsyncSessionLocal") as mock_session_cls:
                mock_db = AsyncMock()
                mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
                await handle_gateway_turn(PHONE, "Dhanyavada, hogi banni!")

        mock_finish.assert_called_once_with(PHONE)
