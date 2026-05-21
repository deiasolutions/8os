"""generate-briefing — bridge-crossing LLM resolver, terminal SCAN node.

Block 3 Piece 5. Reads the upstream filter-and-rank ranked list and
the briefing topic from the workload root's PRISM-IR params, calls
Claude Sonnet 4.6 via the Anthropic bridge, and produces the daily
briefing as markdown.

The `resolution_text` IS the briefing artifact. We also write a
sidecar copy under `.8os/dogfood-scan/artifacts/<intention-id>.md`
for ergonomics — the briefing is the launch artifact and a reader
shouldn't have to dig into a kernel-internal record format to read
it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import context
from .workload_helpers import (
    load_intention_record,
    read_parent_prism_params,
    read_upstream_resolution_value,
    write_dogfood_artifact,
)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "generate_briefing.md"
_DEFAULT_MODEL = "claude-haiku-4-5"
_DEFAULT_MAX_TOKENS = 4096


def load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def build_payload(intention_text: str) -> dict[str, Any]:
    intention_id = context.get_current_intention_id()
    self_rec = load_intention_record(intention_id)
    deps = list(self_rec.frontmatter.get("depends_on") or [])
    if not deps:
        raise ValueError(
            f"generate-briefing leaf {intention_id!r} has no depends_on; "
            f"expected upstream filter-and-rank node"
        )
    upstream_value = read_upstream_resolution_value(intention_id, deps[0])
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
    if not isinstance(bridge_result, dict):
        raise ValueError(f"bridge_result must be a dict (got {type(bridge_result).__name__})")
    resolution = bridge_result.get("resolution")
    if resolution is None:
        raise ValueError("bridge_result has no 'resolution' field")
    briefing_md = (
        resolution if isinstance(resolution, str) else json.dumps(resolution)
    )

    # Write the briefing as a sidecar artifact so the launch artifact
    # is readable without parsing a kernel record. Best-effort — the
    # factory.context may be unavailable in unusual call paths.
    try:
        intention_id = context.get_current_intention_id()
        write_dogfood_artifact(f"{intention_id}.md", briefing_md)
    except RuntimeError:
        pass

    cost = bridge_result.get("cost_actual") or {}
    return {
        "resolution_text": briefing_md,
        "resolution_value": briefing_md,
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
