"""PRISM-IR decomposer — translate a PRISM-IR doc body into a graph spec.

Block 3 Piece 4. The decomposer is a bridge-crossing resolver
(`bridge: anthropic`, `implementation: null`) registered at
`ir/_kernel/resolver/prism-ir-decomposer.md`. Its work happens through
the Anthropic Messages API; this module assembles the API request,
parses the response, and exposes the parsed graph spec to the factory's
materializer.

Two entry points:

- `decompose(prism_ir_body, *, for_ir_id, ...)` — top-level helper used
  by the workload runner in Piece 5. Cross the Anthropic bridge directly
  via `kernel.bridge.cross`, parse the response, return the graph spec.
- `adapt(bridge_result)` — registry-convention adapter. Used when the
  factory's generic dispatcher (Piece 5+) routes the decomposer through
  the standard tick path. Takes a bridge response dict, returns
  `{resolution_text, resolution_value: <graph_spec>, cost_actual}`.

Output shape (the graph spec):

    {
        "nodes": [
            {
                "node_id": "<slug>",
                "intention_text": "<plain English>",
                "depends_on": ["<other_node_id>", ...],
                "prism_operator": {"op": ..., "resolver": ..., "model": ...} | None,
            },
            ...
        ]
    }

The factory's materializer (`materializer.py`) consumes this dict and
authors kernel-hosted (I, R) records via `kernel.ir.new` /
`kernel.ir.expand`. The graph spec format is internal to the factory in
this block — it is not a kernel projection.

Why `prism_operator` and not `kind: bridge | inside`: the factory looks
up resolvers at dispatch time by their `bridge` field on disk. Whether
the resolver named in `prism_operator` is bridge-crossing is a property
of that resolver's own (I, R) record, not the decomposer's choice. The
decomposer faithfully captures PRISM-IR's `op:` declaration; the factory
does the bridge-vs-inside check separately. (Decision: the prior session
draft had `kind: bridge | inside` here; renamed to `prism_operator` so
that fact stays one-sided.)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PROMPT_PATH = Path(__file__).parent / "prompts" / "decomposer.md"
DEFAULT_MODEL = "claude-haiku-4-5"
RESOLVER_ID = "prism-ir-decomposer"
BRIDGE_ID = "anthropic"
STANDING_AUTHORIZATION_ID = "anthropic-standing"

# A single Anthropic Messages API call returning a few-hundred-line JSON
# graph spec is comfortably under this. Larger PRISM-IR docs may need a
# higher cap; revisit when a workload trips it.
_DEFAULT_MAX_TOKENS = 8192


class DecomposerError(Exception):
    """Raised when a bridge response cannot be parsed into a graph spec."""


def load_prompt() -> str:
    """Read the vendored decomposer prompt."""
    return PROMPT_PATH.read_text(encoding="utf-8")


def build_payload(
    prism_ir_body: str,
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> dict[str, Any]:
    """Assemble a Messages API payload for the Anthropic bridge.

    System message = the vendored decomposer prompt. User message =
    the PRISM-IR document body verbatim. The bridge's
    `_coerce_to_messages_request` recognizes payloads that already
    carry `messages` and passes them through.
    """
    return {
        "model": model,
        "system": load_prompt(),
        "messages": [{"role": "user", "content": prism_ir_body}],
        "max_tokens": max_tokens,
    }


_JSON_FENCE_RE = re.compile(
    r"```(?:json)?\s*\n(.*?)\n\s*```",
    flags=re.DOTALL,
)


def parse_response(response_text: str) -> dict[str, Any]:
    """Extract and validate a graph spec from an LLM text response.

    The prompt instructs the model to emit pure JSON. Real models still
    occasionally wrap the output in markdown fences or prepend a brief
    sentence. Try the strict path first, fall back to fence extraction,
    then to balanced-brace scanning.

    Raises `DecomposerError` on any parse / validation failure.
    """
    candidates: list[str] = []

    stripped = response_text.strip()
    if stripped.startswith("{"):
        candidates.append(stripped)

    fence_match = _JSON_FENCE_RE.search(response_text)
    if fence_match:
        candidates.append(fence_match.group(1).strip())

    if not candidates:
        balanced = _extract_first_json_object(response_text)
        if balanced is not None:
            candidates.append(balanced)

    if not candidates:
        raise DecomposerError(
            f"no JSON object found in response (first 200 chars: "
            f"{response_text[:200]!r})"
        )

    last_err: Exception | None = None
    for cand in candidates:
        try:
            parsed = json.loads(cand)
        except json.JSONDecodeError as e:
            last_err = e
            continue
        if not isinstance(parsed, dict):
            last_err = DecomposerError(
                f"parsed JSON is not an object (got {type(parsed).__name__})"
            )
            continue
        if "nodes" not in parsed:
            last_err = DecomposerError(
                f"parsed JSON missing 'nodes' key (got keys "
                f"{sorted(parsed.keys())!r})"
            )
            continue
        return _normalize_graph_spec(parsed)

    raise DecomposerError(
        f"could not parse graph spec from response: {last_err}"
    )


def _extract_first_json_object(text: str) -> str | None:
    """Scan for the first balanced `{...}` object in `text`.

    Tolerates string-literal contents (skips braces inside `"..."`).
    Returns None when no balanced object is found.
    """
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _normalize_graph_spec(parsed: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize the parsed graph spec.

    Enforces the field shape documented in the vendored prompt:
    `node_id` non-empty unique strings, `intention_text` non-empty,
    `depends_on` an array of node_ids that exist in the spec,
    `prism_operator` an object or null. Trims whitespace on
    `intention_text` so downstream comparisons are stable.
    """
    raw_nodes = parsed.get("nodes")
    if not isinstance(raw_nodes, list):
        raise DecomposerError(
            f"'nodes' must be an array (got {type(raw_nodes).__name__})"
        )

    nodes: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for i, node in enumerate(raw_nodes):
        if not isinstance(node, dict):
            raise DecomposerError(
                f"nodes[{i}] is not an object (got {type(node).__name__})"
            )
        nid = node.get("node_id")
        if not isinstance(nid, str) or not nid:
            raise DecomposerError(
                f"nodes[{i}].node_id missing or empty"
            )
        if nid in seen_ids:
            raise DecomposerError(
                f"nodes[{i}].node_id {nid!r} duplicates an earlier node"
            )
        seen_ids.add(nid)
        text = node.get("intention_text")
        if not isinstance(text, str) or not text.strip():
            raise DecomposerError(
                f"nodes[{i}].intention_text missing or empty "
                f"(node_id={nid!r})"
            )
        deps = node.get("depends_on") or []
        if not isinstance(deps, list) or not all(
            isinstance(d, str) for d in deps
        ):
            raise DecomposerError(
                f"nodes[{i}].depends_on must be an array of strings "
                f"(node_id={nid!r})"
            )
        op = node.get("prism_operator")
        if op is not None and not isinstance(op, dict):
            raise DecomposerError(
                f"nodes[{i}].prism_operator must be an object or null "
                f"(node_id={nid!r})"
            )
        nodes.append(
            {
                "node_id": nid,
                "intention_text": text.strip(),
                "depends_on": list(deps),
                "prism_operator": op,
            }
        )

    for node in nodes:
        for dep in node["depends_on"]:
            if dep not in seen_ids:
                raise DecomposerError(
                    f"node {node['node_id']!r} depends_on {dep!r} which is "
                    f"not a node in this spec"
                )

    return {"nodes": nodes}


def adapt(bridge_result: dict[str, Any]) -> dict[str, Any]:
    """Registry-convention adapter for the decomposer resolver.

    Called by the factory's generic dispatcher with the bridge
    function's return value. The Anthropic bridge returns
    `{resolution: <text>, cost_actual: {...}, audit: {...}}`; we parse
    the resolution text into a graph spec and surface it on
    `resolution_value`.
    """
    if not isinstance(bridge_result, dict):
        raise DecomposerError(
            f"bridge_result must be a dict (got {type(bridge_result).__name__})"
        )
    resolution = bridge_result.get("resolution")
    if resolution is None:
        raise DecomposerError("bridge_result has no 'resolution' field")
    resolution_text = (
        resolution if isinstance(resolution, str) else json.dumps(resolution)
    )
    graph_spec = parse_response(resolution_text)
    cost = bridge_result.get("cost_actual") or {}
    return {
        "resolution_text": resolution_text,
        "resolution_value": graph_spec,
        "cost_actual": {
            "clock_ms": float(cost.get("clock_ms") or 0.0),
            "coin_usd": float(cost.get("coin_usd") or 0.0),
            "carbon_g": float(cost.get("carbon_g") or 0.0),
        },
    }


def decompose(
    prism_ir_body: str,
    *,
    for_ir_id: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> dict[str, Any]:
    """Cross the Anthropic bridge and return a parsed graph spec.

    Top-level entry point used by the workload runner in Piece 5. Calls
    `kernel.bridge.cross` directly with the assembled Messages API
    payload; returns the same shape `adapt()` produces.

    Raises `DecomposerError` on parse failure; `KernelError` propagates
    on bridge failure (BRIDGE_FAILED, AUTHORIZATION_REQUIRED, etc.).
    """
    from ..sdk._runner import run as run_op

    payload = build_payload(prism_ir_body, model=model, max_tokens=max_tokens)
    envelope = run_op(
        "kernel.bridge.cross",
        {
            "bridge_id": BRIDGE_ID,
            "resolver_id": RESOLVER_ID,
            "for_ir_id": for_ir_id,
            "authorization_id": STANDING_AUTHORIZATION_ID,
            "payload": payload,
        },
    )
    response = envelope["data"]["response"]
    return adapt(response)


__all__ = [
    "BRIDGE_ID",
    "DEFAULT_MODEL",
    "DecomposerError",
    "PROMPT_PATH",
    "RESOLVER_ID",
    "STANDING_AUTHORIZATION_ID",
    "adapt",
    "build_payload",
    "decompose",
    "load_prompt",
    "parse_response",
]
