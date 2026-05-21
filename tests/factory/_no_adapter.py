"""Synthetic resolver module WITHOUT an `adapt` function.

Used to verify the registry falls back to `default_adapter` when a
resolver module has no `adapt` defined.
"""

from __future__ import annotations

from typing import Any


def resolve(intention_id: str) -> dict[str, Any]:
    return {"intention_id": intention_id, "value": "no-adapter-here"}
