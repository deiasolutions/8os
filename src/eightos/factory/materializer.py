"""Graph-spec materializer — translate decomposer output into kernel records.

Block 3 Piece 4. Consumes a graph spec (the validated output of
`decomposer.parse_response`) and authors one (I, R) per node via
`kernel.ir.new` / `kernel.ir.expand`. Uses only the existing SDK
operations; introduces no kernel changes.

Topological order is enforced: predecessors are authored before
successors so each `depends_on` reference exists in the kernel's
`id-to-path` index by the time the dependent record's `kernel.ir.new`
call validates it.

PRISM-operator embedding: the `prism_operator` field on each graph
node (capturing PRISM-IR's `op:` declaration) is embedded as a YAML
fenced block at the end of the materialized record's `intention_text`
body, NOT as a frontmatter extension. Same constraint as the
`implementation:` field on resolvers (OPEN-Q-026): no vendored
projection body declares `prism_operator`, so authoring it as a
frontmatter extension would fail `validate_extensions`. Body
embedding round-trips cleanly through YAML parsing in the recomposer
(Piece 6) and via `reconstruct_graph_spec_from_records` here.

`reconstruct_graph_spec_from_records` is the structural inverse of
`materialize` — no LLM in the loop. It exists so Piece 4 can run a
deterministic round-trip test (canonical spec → records → spec) that
de-risks Piece 6's recomposer.
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from ..sdk._runner import run as run_op


class MaterializationError(Exception):
    """Raised when a graph spec cannot be materialized as kernel records."""


def materialize(
    graph_spec: dict[str, Any],
    *,
    scope_id: str,
    authored_by: str,
    authored_via: str = "outside",
    parent_id: str | None = None,
    authority_level: str = "convention",
) -> list[str]:
    """Author the graph spec as kernel-hosted (I, R) records.

    Args:
        graph_spec: validated output of `decomposer.parse_response`.
        scope_id: scope to author records into. Must already exist.
        authored_by: provenance — typically the decomposer's resolver_id.
        authored_via: bridge through which authoring happened (the
            anthropic bridge for decomposer-driven materialization;
            `"outside"` for hand-built test specs).
        parent_id: when non-null, every node is authored as a child of
            this (I, R). The parent is expanded if currently collapsed.
        authority_level: authority level for the authored records.

    Returns the list of authored (I, R) ids in topological order.
    Raises `MaterializationError` on cycles, dangling deps, or other
    structural issues; `KernelError` propagates from `kernel.ir.new`.
    """
    nodes = list(graph_spec.get("nodes") or [])
    if not nodes:
        return []

    if parent_id is not None:
        _ensure_parent_expanded(parent_id)

    ordered = _toposort(nodes)
    authored: list[str] = []
    for node in ordered:
        nid = node["node_id"]
        intention_text = _format_intention_text(node)
        payload: dict[str, Any] = {
            "scope_id": scope_id,
            "slug": nid,
            "tier": 1,
            "intention_text": intention_text,
            "authority_level": authority_level,
            "authored_by": authored_by,
            "authored_via": authored_via,
            "depends_on": list(node["depends_on"]),
        }
        if parent_id is not None:
            payload["parent_id"] = parent_id
        run_op("kernel.ir.new", payload)
        authored.append(nid)
    return authored


def reconstruct_graph_spec_from_records(
    *,
    scope_id: str,
    parent_id: str | None = None,
) -> dict[str, Any]:
    """Walk authored records and reconstruct the graph spec.

    The structural inverse of `materialize`, no LLM involved. Used by
    the Piece 4 round-trip test and by Piece 6's recomposer as the
    structural foundation it composes English over.

    When `parent_id` is given, walks the children of that expanded
    parent. Otherwise walks the flat scope directory at
    `ir/<scope_id>/`. Tier 1 records only; subdirectory records (e.g.,
    `_calibration-policies/`) are skipped — those are kernel-config
    territory, not workload nodes.
    """
    from .._frontmatter import parse_file
    from .._paths import scope_dir
    from .._yaml import load_yaml_file
    from ..sdk._common import repo_root_or_raise

    repo = repo_root_or_raise()

    if parent_id is not None:
        idx = load_yaml_file(repo / ".8os" / "index" / "id-to-path.yml") or {}
        rel = idx.get(parent_id)
        if rel is None or not rel.endswith("/_node.md"):
            raise MaterializationError(
                f"parent {parent_id!r} is not expanded; "
                f"cannot reconstruct graph spec from its children"
            )
        folder = (repo / rel).parent
        candidate_paths = sorted(
            p for p in folder.glob("*.md") if p.name != "_node.md"
        )
    else:
        sd = scope_dir(repo, scope_id)
        if not sd.exists():
            return {"nodes": []}
        candidate_paths = sorted(
            p for p in sd.glob("*.md")
            if not p.name.startswith("_")
        )

    nodes: list[dict[str, Any]] = []
    for path in candidate_paths:
        try:
            rec = parse_file(path)
        except Exception:
            continue
        fm = rec.frontmatter
        if int(fm.get("tier", 0)) != 1:
            continue
        nid = fm.get("id")
        if not nid:
            continue
        intention_text, prism_op = _extract_prism_operator(rec.intention_text)
        nodes.append(
            {
                "node_id": nid,
                "intention_text": intention_text,
                "depends_on": list(fm.get("depends_on") or []),
                "prism_operator": prism_op,
            }
        )
    return {"nodes": nodes}


def _ensure_parent_expanded(parent_id: str) -> None:
    """Expand `parent_id` if currently collapsed.

    `kernel.ir.new` with `parent_id` requires the parent's on-disk
    file to be `_node.md` (already expanded). Idempotent: returns
    silently when the parent is already expanded.
    """
    from .._yaml import load_yaml_file
    from ..sdk._common import repo_root_or_raise

    repo = repo_root_or_raise()
    idx = load_yaml_file(repo / ".8os" / "index" / "id-to-path.yml") or {}
    rel = idx.get(parent_id)
    if rel is None:
        raise MaterializationError(
            f"parent {parent_id!r} not found in id-to-path index"
        )
    if rel.endswith("/_node.md"):
        return  # already expanded
    run_op("kernel.ir.expand", {"ir_id": parent_id})


def _toposort(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Kahn's algorithm with stable source-order tie-break.

    A node is ready when all its `depends_on` predecessors have been
    emitted. Among ready nodes, the one with the lowest source-order
    index goes first — keeping output ordering reproducible across
    runs.
    """
    by_id: dict[str, dict[str, Any]] = {}
    for n in nodes:
        nid = n["node_id"]
        if nid in by_id:
            raise MaterializationError(
                f"duplicate node_id {nid!r} in graph spec"
            )
        by_id[nid] = n

    rev: dict[str, list[str]] = {nid: [] for nid in by_id}
    in_deg: dict[str, int] = {}
    for n in nodes:
        nid = n["node_id"]
        deps = n["depends_on"]
        in_deg[nid] = len(deps)
        for dep in deps:
            if dep not in by_id:
                raise MaterializationError(
                    f"node {nid!r} depends_on {dep!r} which is not in this spec"
                )
            rev[dep].append(nid)

    source_order = {n["node_id"]: i for i, n in enumerate(nodes)}
    ready = sorted(
        (nid for nid, d in in_deg.items() if d == 0),
        key=lambda x: source_order[x],
    )
    out: list[dict[str, Any]] = []
    while ready:
        nid = ready.pop(0)
        out.append(by_id[nid])
        newly_ready: list[str] = []
        for succ in rev[nid]:
            in_deg[succ] -= 1
            if in_deg[succ] == 0:
                newly_ready.append(succ)
        ready.extend(newly_ready)
        ready.sort(key=lambda x: source_order[x])

    if len(out) != len(nodes):
        unprocessed = [nid for nid in by_id if in_deg[nid] > 0]
        raise MaterializationError(
            f"cycle detected in graph spec; could not order: {unprocessed!r}"
        )
    return out


def _format_intention_text(node: dict[str, Any]) -> str:
    """Compose the intention_text body, embedding `prism_operator` as YAML.

    The PRISM operator declaration is embedded as a trailing YAML
    fenced block. `reconstruct_graph_spec_from_records` parses it back
    out by matching the same fence shape.
    """
    text = node["intention_text"]
    op = node.get("prism_operator")
    if op is None:
        return text
    serialized = yaml.safe_dump({"prism_operator": op}, sort_keys=False).rstrip()
    return f"{text}\n\n```yaml\n{serialized}\n```"


_PRISM_OP_FENCE_RE = re.compile(
    r"\s*```yaml\s*\n(.*?)\n\s*```\s*$",
    flags=re.DOTALL,
)


def extract_prism_resolver(intention_text: str) -> str | None:
    """Return the resolver named in a materialized intention's prism_operator
    YAML block, or None when no such block exists.

    Used by the factory's tick (Piece 5) to derive a leaf's domain from
    its embedded PRISM-IR operator declaration. The decomposer-emitted
    graph specs carry `prism_operator: {op, resolver, model}` per node;
    the materializer encodes that into the intention body via
    `_format_intention_text`. Tick uses the resolver name as the
    selector's domain — each downstream dogfood resolver declares its
    own name as a capability domain key, so selector matching collapses
    to "pick the resolver named in the PRISM-IR doc."
    """
    _, op = _extract_prism_operator(intention_text)
    if op is None:
        return None
    resolver = op.get("resolver")
    return resolver if isinstance(resolver, str) and resolver else None


def _extract_prism_operator(
    text: str,
) -> tuple[str, dict[str, Any] | None]:
    """Inverse of `_format_intention_text` — pull the YAML block back.

    Returns `(text_without_block, prism_operator_or_None)`. When the
    trailing block is absent or doesn't carry a `prism_operator` key,
    the original text is returned unchanged with `None` for the op.
    """
    match = _PRISM_OP_FENCE_RE.search(text)
    if match is None:
        return text, None
    yaml_body = match.group(1)
    try:
        parsed = yaml.safe_load(yaml_body)
    except yaml.YAMLError:
        return text, None
    if not isinstance(parsed, dict) or "prism_operator" not in parsed:
        return text, None
    pre_text = text[: match.start()].rstrip()
    op = parsed["prism_operator"]
    if op is None or isinstance(op, dict):
        return pre_text, op
    return text, None


__all__ = [
    "MaterializationError",
    "extract_prism_resolver",
    "materialize",
    "reconstruct_graph_spec_from_records",
]
