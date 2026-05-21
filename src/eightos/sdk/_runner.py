"""Operation runner — input validation, dispatch, output validation.

Every CLI invocation flows through `run(op, payload)`:

1. Canonicalize op name.
2. Validate payload against `<op>.v1.input.json`.
3. Dispatch to the handler.
4. Wrap the returned data into a success envelope.
5. Validate the envelope against `<op>.v1.output.json`.

Handlers raise `KernelError` for expected failures. Unexpected exceptions
bubble up and become `INVALID_STATE` errors at the CLI boundary so internal
crashes never surface as silent successes.
"""

from __future__ import annotations

from typing import Any

from .._envelope import success
from .._validation import validate_input, validate_output
from ..errors import SCHEMA_INVALID, KernelError
from . import OP_HANDLERS, canonicalize


def run(op: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Execute an operation end-to-end and return its success envelope."""
    try:
        canonical = canonicalize(op)
    except KeyError:
        raise KernelError(
            SCHEMA_INVALID,
            f"unknown operation: {op!r}",
            input_field="op",
            offending_value=op,
            suggested_action=f"one of {sorted(OP_HANDLERS)}",
        )

    payload = _apply_sdk_defaults(canonical, payload)
    validate_input(canonical, payload)
    handler = OP_HANDLERS[canonical]
    handler_result = handler(payload)
    # Handlers may either return raw data dict OR a tuple-like structure.
    # We standardize on dict[data, event_id, indexes_updated].
    data = handler_result.get("data", handler_result)
    if not isinstance(data, dict):
        raise KernelError(
            "INVALID_STATE",
            f"handler for {canonical} returned non-dict data",
        )
    envelope = success(
        canonical,
        data,
        event_id=handler_result.get("event_id"),
        indexes_updated=handler_result.get("indexes_updated"),
    )
    validate_output(canonical, envelope)
    return envelope


def _apply_sdk_defaults(op: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Apply SDK-boundary defaults before kernel validation.

    v1.0.1-partial Amendment 2: kernel.ir.new requires authored_via. For
    non-internal callers entering the kernel through the SDK boundary who
    don't supply it, the SDK fills in `"outside"` — the generic outside-
    bridge per axiom 0. Internal kernel ops (init, reindex, migration,
    bridge.cross self-events) author records directly via IRRecord +
    commit_staged and never come through this path; they pass
    `"kernel.self"` explicitly on the records they write.
    """
    if op in ("kernel.ir.new", "kernel.ir.cancel"):
        if "authored_via" not in payload:
            payload = dict(payload)
            payload["authored_via"] = "outside"
    return payload
