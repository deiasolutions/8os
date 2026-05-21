"""prism-ir-recomposer — round-trip fidelity check.

Block 3 Piece 6. The inverse direction of the decomposer: takes a
resolved (I, R) graph and returns plain-English prose describing
what the workload was for and what happened.

Round-trip purity: the recomposer is **not** given the original
PRISM-IR document or its `intention:` field. It reconstructs from
the resolved graph alone. The reconstruction is then human-judged
against the original PRISM-IR intent for fidelity.

Walking conventions:
- The recomposer's leaf carries `depends_on: [<terminal-node-id>]`.
- The terminal node has `parent: <workload-root-id>` (set by the
  materializer when the workload root was decomposed).
- The recomposer walks `depends_on[0]` -> `parent` to locate the
  workload root, then uses
  `materializer.reconstruct_graph_spec_from_records(parent_id=...)`
  to recover the graph structure.
- Each node's `resolution_text` is fetched and included in the
  prompt's user message.

`produces: value` (default). Resolution is plain text. The dispatcher
calls `kernel.ir.resolve` on the leaf with the recomposer's prose;
no materialization branch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import context
from .materializer import reconstruct_graph_spec_from_records
from .workload_helpers import load_intention_record, write_dogfood_artifact

_PROMPT_PATH = Path(__file__).parent / "prompts" / "recomposer.md"
_DEFAULT_MODEL = "claude-haiku-4-5"
_DEFAULT_MAX_TOKENS = 4096
_RESOLUTION_TRUNCATE_CHARS = 2000


def load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def build_payload(intention_text: str) -> dict[str, Any]:
    """Assemble the Anthropic Messages API payload.

    The intention_text the dispatcher passes is the recomposer
    leaf's body ("Reconstruct ... from its resolved graph"); we
    don't use it directly. The substantive input is the resolved
    graph, which we reach via factory.context's current intention id
    and the depends_on -> parent chain.
    """
    intention_id = context.get_current_intention_id()
    self_rec = load_intention_record(intention_id)
    deps = list(self_rec.frontmatter.get("depends_on") or [])
    if not deps:
        raise ValueError(
            f"recomposer leaf {intention_id!r} has no depends_on; "
            f"expected the workload's terminal node id"
        )
    terminal_id = deps[0]
    terminal_rec = load_intention_record(terminal_id)
    workload_root_id = terminal_rec.frontmatter.get("parent")
    if not workload_root_id:
        raise ValueError(
            f"terminal node {terminal_id!r} has no parent; "
            f"expected the workload root id"
        )

    scope_id = self_rec.frontmatter.get("scope") or ""
    graph_spec = reconstruct_graph_spec_from_records(
        scope_id=scope_id, parent_id=workload_root_id
    )

    nodes_with_resolutions: list[dict[str, Any]] = []
    for node in graph_spec.get("nodes") or []:
        nid = node["node_id"]
        try:
            rec = load_intention_record(nid)
        except FileNotFoundError:
            continue
        resolution_text = rec.resolution_text or "(no resolution recorded)"
        if len(resolution_text) > _RESOLUTION_TRUNCATE_CHARS:
            resolution_text = (
                resolution_text[:_RESOLUTION_TRUNCATE_CHARS]
                + f"\n\n[... truncated, full length {len(rec.resolution_text or '')} chars]"
            )
        nodes_with_resolutions.append(
            {
                "node_id": nid,
                "intention_text": node["intention_text"],
                "depends_on": list(node["depends_on"]),
                "prism_operator": node.get("prism_operator"),
                "resolution_text": resolution_text,
            }
        )

    user_msg = json.dumps(
        {
            "workload_id": workload_root_id,
            "nodes": nodes_with_resolutions,
        },
        ensure_ascii=False,
    )
    return {
        "model": _DEFAULT_MODEL,
        "system": load_prompt(),
        "messages": [{"role": "user", "content": user_msg}],
        "max_tokens": _DEFAULT_MAX_TOKENS,
    }


def adapt(bridge_result: dict[str, Any]) -> dict[str, Any]:
    """Return the LLM's prose as resolution_text + write sidecar artifact.

    The artifact is written under
    `.8os/dogfood-scan/artifacts/<intention-id>-reconstruction.md` so
    the round-trip output is readable without parsing a kernel
    record. Used by the human-judged fidelity comparison in Piece 6
    and the Piece 7 block report.
    """
    if not isinstance(bridge_result, dict):
        raise ValueError(
            f"bridge_result must be a dict (got {type(bridge_result).__name__})"
        )
    resolution = bridge_result.get("resolution")
    if resolution is None:
        raise ValueError("bridge_result has no 'resolution' field")
    prose = resolution if isinstance(resolution, str) else json.dumps(resolution)

    try:
        intention_id = context.get_current_intention_id()
        write_dogfood_artifact(f"{intention_id}-reconstruction.md", prose)
    except RuntimeError:
        # No active dispatch context — skip artifact write, just return prose.
        pass

    cost = bridge_result.get("cost_actual") or {}
    return {
        "resolution_text": prose,
        "resolution_value": prose,
        "cost_actual": {
            "clock_ms": float(cost.get("clock_ms") or 0.0),
            "coin_usd": float(cost.get("coin_usd") or 0.0),
            "carbon_g": float(cost.get("carbon_g") or 0.0),
        },
    }


__all__ = [
    "adapt",
    "build_payload",
    "load_prompt",
]
