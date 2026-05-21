"""score-relevance — bridge-crossing LLM resolver for item scoring.

Block 3 Piece 5. The factory's dispatcher discovers this module via
the resolver record's `module:` field and looks for `build_payload` /
`adapt`. The dispatcher routes the call through `kernel.bridge.cross`
on the Anthropic bridge.

Inputs flow as JSON-encoded resolution_text from the upstream
fetch-sources node; the briefing topic flows from the workload root's
PRISM-IR `params:` block. The factory's context provides
`get_current_intention_id()` so this module can resolve "self" and
walk to upstream / parent without thread-unsafe signature changes
elsewhere.

Output: a JSON-encoded list of items each carrying `score` and
`reason` fields injected by the LLM. filter-and-rank consumes this
list directly.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import context
from .workload_helpers import (
    load_intention_record,
    read_parent_prism_params,
    read_upstream_resolution_value,
)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "score_relevance.md"
_DEFAULT_MODEL = "claude-haiku-4-5"
_DEFAULT_MAX_TOKENS = 8192


def load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def build_payload(intention_text: str) -> dict[str, Any]:
    """Assemble the Anthropic Messages API payload.

    Reads the upstream items list and the briefing topic via the
    factory context's current intention id. The intention_text passed
    by the dispatcher is the leaf's body (a thin "score per-item
    relevance" sentence + the embedded prism_operator block); we
    don't use it directly — the substantive inputs come from elsewhere
    in the graph.
    """
    intention_id = context.get_current_intention_id()
    self_rec = load_intention_record(intention_id)
    deps = list(self_rec.frontmatter.get("depends_on") or [])
    if not deps:
        raise ValueError(
            f"score-relevance leaf {intention_id!r} has no depends_on; "
            f"expected upstream fetch-sources node"
        )
    upstream_id = deps[0]
    upstream_value = read_upstream_resolution_value(intention_id, upstream_id)
    items = _extract_items(upstream_value)
    params = read_parent_prism_params(intention_id)
    briefing_topic = params.get("briefing_topic") or "(unspecified topic)"

    user_msg = json.dumps(
        {"briefing_topic": briefing_topic, "items": items},
        ensure_ascii=False,
    )
    return {
        "model": _DEFAULT_MODEL,
        "system": load_prompt(),
        "messages": [{"role": "user", "content": user_msg}],
        "max_tokens": _DEFAULT_MAX_TOKENS,
    }


def adapt(bridge_result: dict[str, Any]) -> dict[str, Any]:
    """Parse `{scores: [{id, score, reason}]}`; merge onto the items list.

    Re-fetches the upstream items list to merge in `score` / `reason`
    per id, so filter-and-rank receives a single combined list.
    """
    if not isinstance(bridge_result, dict):
        raise ValueError(f"bridge_result must be a dict (got {type(bridge_result).__name__})")
    resolution = bridge_result.get("resolution")
    if resolution is None:
        raise ValueError("bridge_result has no 'resolution' field")
    text = resolution if isinstance(resolution, str) else json.dumps(resolution)
    score_map = _parse_score_map(text)

    intention_id = context.get_current_intention_id()
    self_rec = load_intention_record(intention_id)
    deps = list(self_rec.frontmatter.get("depends_on") or [])
    if not deps:
        raise ValueError(
            f"score-relevance leaf {intention_id!r} has no depends_on"
        )
    upstream_value = read_upstream_resolution_value(intention_id, deps[0])
    items = _extract_items(upstream_value)
    merged: list[dict[str, Any]] = []
    for item in items:
        iid = item.get("id")
        score_entry = score_map.get(iid) if isinstance(iid, str) else None
        if score_entry is not None:
            merged.append(
                {**item, "score": score_entry["score"], "reason": score_entry["reason"]}
            )
        else:
            merged.append({**item, "score": 0.0, "reason": "(no score returned)"})

    cost = bridge_result.get("cost_actual") or {}
    return {
        "resolution_text": json.dumps({"items": merged}),
        "resolution_value": merged,
        "cost_actual": {
            "clock_ms": float(cost.get("clock_ms") or 0.0),
            "coin_usd": float(cost.get("coin_usd") or 0.0),
            "carbon_g": float(cost.get("carbon_g") or 0.0),
        },
    }


def _extract_items(upstream_value: Any) -> list[dict[str, Any]]:
    if isinstance(upstream_value, list):
        return [it for it in upstream_value if isinstance(it, dict)]
    if isinstance(upstream_value, dict):
        items = upstream_value.get("items") or []
        return [it for it in items if isinstance(it, dict)]
    return []


def _parse_score_map(text: str) -> dict[str, dict[str, Any]]:
    """Parse the LLM's `{scores: [...]}` and index by id. Tolerant to
    fenced-output / prose-prefix variants per the prompt's caveat."""
    candidates: list[str] = []
    stripped = text.strip()
    if stripped.startswith("{"):
        candidates.append(stripped)
    fence = re.search(
        r"```(?:json)?\s*\n(.*?)\n\s*```", text, flags=re.DOTALL
    )
    if fence:
        candidates.append(fence.group(1).strip())
    if not candidates:
        idx = text.find("{")
        if idx >= 0:
            candidates.append(text[idx:])

    for cand in candidates:
        try:
            parsed = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        scores = parsed.get("scores")
        if not isinstance(scores, list):
            continue
        out: dict[str, dict[str, Any]] = {}
        for entry in scores:
            if not isinstance(entry, dict):
                continue
            iid = entry.get("id")
            if not isinstance(iid, str):
                continue
            try:
                score = float(entry.get("score") or 0.0)
            except (TypeError, ValueError):
                score = 0.0
            out[iid] = {
                "score": max(0.0, min(1.0, score)),
                "reason": entry.get("reason") or "",
            }
        return out
    return {}
