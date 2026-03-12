"""Tests for the in-memory per-phone AI call rate limiter."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.services import rate_limiter


def _clear_log() -> None:
    rate_limiter._call_log.clear()


@pytest.fixture(autouse=True)
def clear_call_log():
    _clear_log()
    yield
    _clear_log()


class TestIsAllowed:
    def test_first_call_is_allowed(self):
        assert rate_limiter.is_allowed("15551234567") is True

    def test_calls_up_to_limit_are_allowed(self):
        phone = "15550000001"
        for _ in range(rate_limiter._MAX_CALLS):
            assert rate_limiter.is_allowed(phone) is True

    def test_call_over_limit_is_denied(self):
        phone = "15550000002"
        for _ in range(rate_limiter._MAX_CALLS):
            rate_limiter.is_allowed(phone)
        assert rate_limiter.is_allowed(phone) is False

    def test_denied_call_not_recorded(self):
        phone = "15550000003"
        for _ in range(rate_limiter._MAX_CALLS):
            rate_limiter.is_allowed(phone)
        rate_limiter.is_allowed(phone)  # denied
        # Count should still be _MAX_CALLS, not _MAX_CALLS + 1
        assert rate_limiter.remaining(phone) == 0

    def test_different_phones_tracked_independently(self):
        phone_a = "15550000010"
        phone_b = "15550000011"
        for _ in range(rate_limiter._MAX_CALLS):
            rate_limiter.is_allowed(phone_a)
        # phone_a is at limit; phone_b should still be allowed
        assert rate_limiter.is_allowed(phone_a) is False
        assert rate_limiter.is_allowed(phone_b) is True

    def test_old_calls_outside_window_are_pruned(self):
        phone = "15550000020"
        # Add calls that are just outside the 1-hour window
        old_time = datetime.now(UTC) - timedelta(hours=1, seconds=1)
        for _ in range(rate_limiter._MAX_CALLS):
            rate_limiter._call_log[phone].append(old_time)
        # All old calls should be pruned; new call should be allowed
        assert rate_limiter.is_allowed(phone) is True

    def test_calls_within_window_are_counted(self):
        phone = "15550000021"
        recent_time = datetime.now(UTC) - timedelta(minutes=30)
        for _ in range(rate_limiter._MAX_CALLS - 1):
            rate_limiter._call_log[phone].append(recent_time)
        # One call remaining
        assert rate_limiter.is_allowed(phone) is True
        # Now at limit
        assert rate_limiter.is_allowed(phone) is False


class TestRemaining:
    def test_remaining_starts_at_max(self):
        assert rate_limiter.remaining("15559999001") == rate_limiter._MAX_CALLS

    def test_remaining_decrements_with_calls(self):
        phone = "15559999002"
        rate_limiter.is_allowed(phone)
        assert rate_limiter.remaining(phone) == rate_limiter._MAX_CALLS - 1

    def test_remaining_never_negative(self):
        phone = "15559999003"
        for _ in range(rate_limiter._MAX_CALLS + 5):
            rate_limiter.is_allowed(phone)
        assert rate_limiter.remaining(phone) == 0
