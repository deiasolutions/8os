"""Success and error envelope construction (Block 1 §7.2)."""

from __future__ import annotations

from typing import Any

from .errors import KernelError

SCHEMA_VERSION = 1


def success(
    op: str,
    data: dict[str, Any],
    *,
    event_id: str | None = None,
    indexes_updated: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "op": op,
        "status": "ok",
        "data": data,
        "event_id": event_id,
        "indexes_updated": indexes_updated or [],
    }


def error_from_exception(op: str, exc: KernelError) -> dict[str, Any]:
    context: dict[str, Any] = {
        "axiom_violated": exc.axiom_violated,
        "input_field": exc.input_field,
        "offending_value": exc.offending_value,
        "suggested_action": exc.suggested_action,
    }
    for k, v in exc.extra_context.items():
        context[k] = v
    return {
        "schema_version": SCHEMA_VERSION,
        "op": op,
        "status": "error",
        "code": exc.code,
        "message": exc.message,
        "context": context,
    }
