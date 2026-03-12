"""In-memory per-phone AI call rate limiter (v1, no Redis required).

Tracks the number of AI calls made by each phone number within a sliding
1-hour window.  Not thread-safe across processes; suitable for a single
Uvicorn worker.  Replace with a Redis-backed implementation for multi-worker
deployments.
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta

_WINDOW = timedelta(hours=1)
_MAX_CALLS = 20

# phone -> list of UTC datetimes of AI calls within the current window
_call_log: dict[str, list[datetime]] = defaultdict(list)


def _prune(phone: str, now: datetime) -> list[datetime]:
    """Remove timestamps older than the window and return the pruned list."""
    cutoff = now - _WINDOW
    calls = _call_log[phone]
    calls[:] = [t for t in calls if t > cutoff]
    return calls


def is_allowed(phone: str) -> bool:
    """Return True and record the call if the phone is within the rate limit.

    Returns False (without recording) if the limit has already been reached.
    """
    now = datetime.now(UTC)
    calls = _prune(phone, now)
    if len(calls) >= _MAX_CALLS:
        return False
    calls.append(now)
    return True


def remaining(phone: str) -> int:
    """Return the number of AI calls remaining in the current window."""
    now = datetime.now(UTC)
    calls = _prune(phone, now)
    return max(0, _MAX_CALLS - len(calls))
