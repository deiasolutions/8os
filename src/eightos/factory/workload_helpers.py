"""Helpers for inside / LLM resolvers that participate in materialized workloads.

Block 3 Piece 5. The dogfood's children read three things at dispatch
time:

1. Upstream resolution text (the JSON-encoded output of an immediately
   prior node).
2. PRISM-IR `params:` block from the workload's root intention (e.g.,
   `briefing_topic`, `top_n`).
3. Self's own depends_on / parent / intention_text (frontmatter +
   body fields).

Rather than thread these through resolver function signatures (which
would force the factory's dispatcher to know workload-specific
interfaces), the resolvers fetch them on demand via these helpers
plus `factory.context.get_repo()`.

Centralizing here keeps the four dogfood resolvers thin.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from .._frontmatter import IRRecord, parse_file
from .._yaml import load_yaml_file
from . import context

_PRISM_YAML_FENCE_RE = re.compile(
    r"```yaml\s*\n(.*?)\n\s*```",
    flags=re.DOTALL,
)


def load_intention_record(intention_id: str) -> IRRecord:
    """Load the (I, R) record for `intention_id` via the id-to-path index."""
    repo = context.get_repo()
    idx = load_yaml_file(repo / ".8os" / "index" / "id-to-path.yml") or {}
    rel = idx.get(intention_id)
    if rel is None:
        raise FileNotFoundError(
            f"intention {intention_id!r} not found in id-to-path index"
        )
    return parse_file(repo / rel)


def read_upstream_resolution_text(intention_id: str, dep_id: str) -> str:
    """Read the resolution_text of an upstream dependency.

    The upstream's `kernel.ir.resolve` event wrote `resolution_text`
    onto its (I, R) record. Most dogfood resolvers JSON-encode their
    structured output into resolution_text; downstream consumers parse.
    """
    rec = load_intention_record(dep_id)
    if rec.resolution_text is None:
        raise ValueError(
            f"upstream {dep_id!r} (depended on by {intention_id!r}) "
            f"has no resolution_text yet — not resolved"
        )
    return rec.resolution_text


def read_upstream_resolution_value(intention_id: str, dep_id: str) -> Any:
    """Read the upstream's resolution_text and JSON-decode it."""
    text = read_upstream_resolution_text(intention_id, dep_id)
    return json.loads(text)


def read_parent_prism_params(intention_id: str) -> dict[str, Any]:
    """Walk up to the workload root and extract its PRISM-IR `params:` block.

    The workload root carries the PRISM-IR doc embedded in its
    intention_text inside a ```yaml fenced block. Parses the YAML and
    returns the `params:` dict (or {} if absent).
    """
    rec = load_intention_record(intention_id)
    parent_id = rec.frontmatter.get("parent")
    while parent_id:
        rec = load_intention_record(parent_id)
        parent_id = rec.frontmatter.get("parent")
    # rec is now the root.
    fence_match = _PRISM_YAML_FENCE_RE.search(rec.intention_text)
    if fence_match is None:
        return {}
    try:
        parsed = yaml.safe_load(fence_match.group(1))
    except yaml.YAMLError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    params = parsed.get("params") or {}
    return params if isinstance(params, dict) else {}


def write_dogfood_artifact(name: str, content: str) -> Path:
    """Write a workload artifact (e.g., the briefing) to a known sidecar dir.

    Returns the absolute path. Used by `generate_briefing` to commit
    the briefing markdown alongside the (I, R) record. Sidecar
    convention parallels `kernel.bridge.cross`'s `events/raw/` —
    structured payloads that don't fit cleanly in resolution_text.
    """
    repo = context.get_repo()
    artifacts_dir = repo / ".8os" / "dogfood-scan" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    target = artifacts_dir / name
    target.write_text(content, encoding="utf-8")
    return target


__all__ = [
    "load_intention_record",
    "read_parent_prism_params",
    "read_upstream_resolution_text",
    "read_upstream_resolution_value",
    "write_dogfood_artifact",
]
