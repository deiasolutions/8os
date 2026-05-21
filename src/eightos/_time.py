"""ISO 8601 UTC timestamps with millisecond precision."""

from __future__ import annotations

from datetime import datetime, timezone


def now_iso() -> str:
    """Return ISO 8601 UTC with ms precision, e.g. '2026-04-26T17:42:31.123Z'."""
    dt = datetime.now(timezone.utc)
    ms = dt.microsecond // 1000
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{ms:03d}Z"


def parse_iso(s: str) -> datetime:
    """Parse an ISO 8601 string back to a tz-aware datetime."""
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)
