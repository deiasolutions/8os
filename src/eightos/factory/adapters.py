"""Factory adapters — normalize structured resolver outputs into a flat shape.

Block 3 Piece 1, Shape 4. Resolvers return structured outputs (e.g.,
`pytest-runner` returns `{actual_resolution, exit_code, elapsed_ms,
stdout_tail, intention_id}`). `kernel.ir.resolve` accepts a single
`resolution_text` string plus a `cost_actual` object. The adapter
bridges the two: `(structured_output) -> {resolution_text,
resolution_value?, cost_actual}`.

Adapter convention: each resolver module that declares
`implementation: <module>:<function>` may also export a function named
`adapt` with signature `(dict) -> dict` returning the normalized shape.
The registry's `load_adapter` looks for this function in the same module
as the implementation. If absent, `default_adapter` is used.

Structured-payload-as-first-class is OPEN-Q-025 territory and is
deliberately deferred. The adapter is a factory-level convention that
does not touch the kernel's `ir.resolve` schema.
"""

from __future__ import annotations

from typing import Any


def default_adapter(structured: Any) -> dict[str, Any]:
    """Fallback adapter when a resolver module has no `adapt` function.

    Stringifies the structured output into `resolution_text` and emits a
    zero-cost `cost_actual` placeholder. Resolvers that need accurate
    costs or richer text MUST define their own `adapt`.
    """
    return {
        "resolution_text": str(structured),
        "resolution_value": None,
        "cost_actual": {
            "clock_ms": 0.0,
            "coin_usd": 0.0,
            "carbon_g": 0.0,
        },
    }
