"""Synthetic resolver implementations for factory unit tests.

These modules exist so the factory's registry has real importable
modules to resolve `implementation: <module>:<function>` strings
against, without depending on the kernel's actual vendored resolvers.
"""

from __future__ import annotations

from typing import Any


def simple_resolve(intention_id: str) -> dict[str, Any]:
    """Inside resolver returning a flat structured output."""
    return {
        "intention_id": intention_id,
        "ok": True,
        "elapsed_ms": 12.0,
    }


def simple_resolve_with_adapter(intention_id: str) -> dict[str, Any]:
    """Inside resolver paired with the `adapt` function below."""
    return {
        "intention_id": intention_id,
        "raw_value": 42,
        "elapsed_ms": 7.5,
    }


def adapt(structured: dict[str, Any]) -> dict[str, Any]:
    """Adapter convention: same module, function name `adapt`.

    Note: the registry's `load_adapter` looks for `adapt` in the module
    referenced by `implementation:`. This module is referenced by both
    `simple_resolve` and `simple_resolve_with_adapter`, so both pick up
    this adapter (which is fine for tests — the assertions key off the
    transformed shape).
    """
    return {
        "resolution_text": f"adapted: raw_value={structured.get('raw_value', '?')}",
        "resolution_value": structured.get("raw_value"),
        "cost_actual": {
            "clock_ms": float(structured.get("elapsed_ms", 0)),
            "coin_usd": 0.0,
            "carbon_g": 0.01,
        },
    }


def failing_resolve(intention_id: str) -> dict[str, Any]:
    """Inside resolver that raises on every call."""
    raise RuntimeError(f"deliberate failure for {intention_id}")
