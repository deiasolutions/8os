"""ULID generation. Thin wrapper over python-ulid for a stable kernel-side API."""

from __future__ import annotations

from ulid import ULID


def new_ulid() -> str:
    """Return a fresh ULID as a 26-character base32 string."""
    return str(ULID())
