"""filter-and-rank — inside resolver that picks top-N by score.

Block 3 Piece 5. Third node of the SCAN dogfood. Reads the upstream
`score-relevance` resolution (a JSON-encoded list of items each
augmented with a relevance score and reason), reads `top_n` from the
workload's PRISM-IR `params:` block, and returns the top-N items
ranked by score with ties broken by `source_priority` (lower = higher
priority).

The selector picks this resolver because the materialized child's
`prism_operator.resolver` (and therefore its tick-time `domain`) is
`filter-and-rank`, which matches this resolver's capability map's
sole domain key.
"""

from __future__ import annotations

import json
import time
from typing import Any

_DEFAULT_TOP_N = 5


def resolve(intention_id: str) -> dict[str, Any]:
    from ..factory.workload_helpers import (
        load_intention_record,
        read_parent_prism_params,
        read_upstream_resolution_value,
    )

    start = time.monotonic()
    self_rec = load_intention_record(intention_id)
    deps = list(self_rec.frontmatter.get("depends_on") or [])
    if not deps:
        raise ValueError(
            f"filter-and-rank intention {intention_id!r} has no depends_on; "
            f"expected one upstream score-relevance node"
        )
    upstream_id = deps[0]
    upstream_value = read_upstream_resolution_value(intention_id, upstream_id)
    scored_items = _extract_scored_items(upstream_value)

    params = read_parent_prism_params(intention_id)
    top_n = int(params.get("top_n") or _DEFAULT_TOP_N)

    ranked = sorted(
        scored_items,
        key=lambda item: (
            -float(item.get("score") or 0.0),
            int(item.get("source_priority") or 99),
        ),
    )
    top = ranked[:top_n]
    elapsed_ms = (time.monotonic() - start) * 1000.0
    return {
        "items": top,
        "total_input_count": len(scored_items),
        "top_n": top_n,
        "elapsed_ms": elapsed_ms,
        "intention_id": intention_id,
    }


def _extract_scored_items(upstream_value: Any) -> list[dict[str, Any]]:
    """Tolerate two upstream shapes: bare list or {items: [...]} wrapper."""
    if isinstance(upstream_value, list):
        return [item for item in upstream_value if isinstance(item, dict)]
    if isinstance(upstream_value, dict):
        items = upstream_value.get("items") or []
        return [item for item in items if isinstance(item, dict)]
    return []


def adapt(structured: dict[str, Any]) -> dict[str, Any]:
    items = structured.get("items") or []
    return {
        "resolution_text": json.dumps(
            {
                "items": items,
                "total_input_count": structured.get("total_input_count"),
                "top_n": structured.get("top_n"),
            }
        ),
        "resolution_value": items,
        "cost_actual": {
            "clock_ms": float(structured.get("elapsed_ms") or 0.0),
            "coin_usd": 0.0,
            "carbon_g": 0.001,
        },
    }
