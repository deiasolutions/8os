"""Recomposer module tests — prompt loading, payload assembly, adapter.

Block 3 Piece 6. The recomposer is bridge-crossing; these tests cover
everything except the actual API call. The end-to-end test against
real Claude is in `test_recomposer_e2e.py` (gated on
RUN_REAL_BRIDGE_TESTS=1).
"""

from __future__ import annotations

import json

import pytest

from eightos.factory import context, recomposer
from eightos.factory.materializer import materialize
from eightos.sdk._runner import run as run_op


# ---- prompt --------------------------------------------------------------


def test_load_prompt_returns_nonempty_string():
    text = recomposer.load_prompt()
    assert isinstance(text, str)
    assert len(text) > 0
    # Sanity — the prompt should mention round-trip and prose-only contracts.
    assert "round-trip" in text.lower() or "reconstruction" in text.lower()
    assert "prose" in text.lower()


# ---- workload fixture ----------------------------------------------------


@pytest.fixture
def workload_with_resolutions(initialized):
    """Author a small workload graph with resolved children and a
    pending recomposer leaf so build_payload has real records to walk."""
    import shutil
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]

    # Copy scope and the four dogfood resolver records (so kernel.ir.resolve
    # can validate resolver_id refs).
    scope_path = initialized / "ir" / "_kernel" / "scope" / "dogfood-scan.md"
    scope_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(
        repo_root / "ir" / "_kernel" / "scope" / "dogfood-scan.md", scope_path
    )
    for rid in (
        "fetch-sources",
        "score-relevance",
        "filter-and-rank",
        "generate-briefing",
        "prism-ir-recomposer",
    ):
        src = repo_root / "ir" / "_kernel" / "resolver" / f"{rid}.md"
        dst = initialized / "ir" / "_kernel" / "resolver" / f"{rid}.md"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)

    # Workload root with PRISM-IR doc body.
    root_dir = initialized / "ir" / "dogfood-scan"
    root_dir.mkdir(parents=True, exist_ok=True)
    root_path = root_dir / "rt-root.md"
    root_path.write_text(
        "---\n"
        "id: rt-root\nkind: ir-node\ntier: 1\nstatus: open\n"
        "scope: dogfood-scan\nauthority_level: convention\n"
        "authored_by: t\nauthored_on: '2026-04-28T00:00:00.000Z'\n"
        "authored_via: outside\nprojection_types: []\ndepends_on: []\n"
        "visible_to: [dogfood-scan]\nparent: null\nexpanded_into: null\n"
        "resolution_event: null\nresolved_at: null\nresolver: null\n"
        "revalidate_trigger: null\nsuperseded_by: null\nsupersedes: null\n"
        "surrogate_of: null\nvalid_through: null\n"
        "collapsed_summary: workload root\n"
        "---\n\n# Intention\n\nWorkload root for recomposer test.\n"
    )
    run_op("kernel.reindex", {"mode": "rebuild"})

    spec = {
        "nodes": [
            {
                "node_id": "rt-fetch",
                "intention_text": "Fetch items.",
                "depends_on": [],
                "prism_operator": {"op": "script", "resolver": "fetch-sources", "model": None},
            },
            {
                "node_id": "rt-brief",
                "intention_text": "Compose briefing.",
                "depends_on": ["rt-fetch"],
                "prism_operator": {"op": "llm", "resolver": "generate-briefing", "model": None},
            },
        ]
    }
    materialize(
        spec,
        scope_id="dogfood-scan",
        authored_by="t",
        authored_via="outside",
        parent_id="rt-root",
    )
    # Resolve the children synthetically so the recomposer has resolution_text.
    run_op(
        "kernel.ir.resolve",
        {
            "ir_id": "rt-fetch",
            "resolver_id": "fetch-sources",
            "resolution_text": json.dumps(
                {"items": [{"id": "x", "title": "An item", "source": "hackernews"}]}
            ),
            "cost_actual": {"clock_ms": 0, "coin_usd": 0, "carbon_g": 0},
        },
    )
    run_op(
        "kernel.ir.resolve",
        {
            "ir_id": "rt-brief",
            "resolver_id": "generate-briefing",
            "resolution_text": "# Today's briefing\n\nA short summary.",
            "cost_actual": {"clock_ms": 0, "coin_usd": 0, "carbon_g": 0},
        },
    )

    # Author the recomposer leaf (peer of the workload root, depending on
    # the terminal node).
    rt_check_path = root_dir / "rt-check.md"
    rt_check_path.write_text(
        "---\n"
        "id: rt-check\nkind: ir-node\ntier: 1\nstatus: open\n"
        "scope: dogfood-scan\nauthority_level: convention\n"
        "authored_by: t\nauthored_on: '2026-04-28T00:00:00.000Z'\n"
        "authored_via: outside\nprojection_types: []\n"
        "depends_on: [rt-brief]\n"
        "visible_to: [dogfood-scan]\nparent: null\nexpanded_into: null\n"
        "resolution_event: null\nresolved_at: null\nresolver: null\n"
        "revalidate_trigger: null\nsuperseded_by: null\nsupersedes: null\n"
        "surrogate_of: null\nvalid_through: null\n"
        "domain: prism-ir-recomposition\n"
        "collapsed_summary: round-trip check\n"
        "---\n\n# Intention\n\nReconstruct the workload.\n"
    )
    run_op("kernel.reindex", {"mode": "rebuild"})
    return initialized


# ---- build_payload --------------------------------------------------------


def test_build_payload_assembles_request_from_resolved_graph(workload_with_resolutions):
    context.set_repo(workload_with_resolutions)
    context.set_current_intention_id("rt-check")
    try:
        payload = recomposer.build_payload("Reconstruct the workload.")
    finally:
        context.clear()

    assert payload["model"] == "claude-haiku-4-5"
    assert "PRISM-IR recomposer" in payload["system"]
    user = json.loads(payload["messages"][0]["content"])
    assert user["workload_id"] == "rt-root"
    assert len(user["nodes"]) == 2
    fetch_node = next(n for n in user["nodes"] if n["node_id"] == "rt-fetch")
    brief_node = next(n for n in user["nodes"] if n["node_id"] == "rt-brief")
    assert fetch_node["prism_operator"]["resolver"] == "fetch-sources"
    assert brief_node["depends_on"] == ["rt-fetch"]
    assert "An item" in fetch_node["resolution_text"]
    assert "Today's briefing" in brief_node["resolution_text"]


def test_build_payload_truncates_long_resolutions(workload_with_resolutions):
    """Resolution_text > 2000 chars gets truncated with a note."""
    long_text = "x" * 5000
    run_op(
        "kernel.ir.resolve",
        {
            "ir_id": "rt-fetch.s1",
            "resolver_id": "fetch-sources",
            "resolution_text": long_text,
            "cost_actual": {"clock_ms": 0, "coin_usd": 0, "carbon_g": 0},
        },
    ) if False else None  # placeholder; actual long-resolution case below

    # Supersede rt-brief with a long resolution text instead.
    # Simpler: directly modify the file.
    from eightos._frontmatter import parse_file, serialize
    brief_path = workload_with_resolutions / "ir" / "dogfood-scan" / "rt-root" / "rt-brief.md"
    rec = parse_file(brief_path)
    rec.resolution_text = long_text
    brief_path.write_text(serialize(rec))
    run_op("kernel.reindex", {"mode": "rebuild"})

    context.set_repo(workload_with_resolutions)
    context.set_current_intention_id("rt-check")
    try:
        payload = recomposer.build_payload("Reconstruct.")
    finally:
        context.clear()
    user = json.loads(payload["messages"][0]["content"])
    brief_node = next(n for n in user["nodes"] if n["node_id"] == "rt-brief")
    assert len(brief_node["resolution_text"]) < len(long_text)
    assert "truncated" in brief_node["resolution_text"]


def test_build_payload_raises_when_no_depends_on(workload_with_resolutions):
    """The recomposer leaf must depend on the terminal node — missing this
    dep is a misconfiguration, not a hallucination opportunity."""
    # Author a leaf with no depends_on.
    bad_path = workload_with_resolutions / "ir" / "dogfood-scan" / "bad-leaf.md"
    bad_path.write_text(
        "---\n"
        "id: bad-leaf\nkind: ir-node\ntier: 1\nstatus: open\n"
        "scope: dogfood-scan\nauthority_level: convention\n"
        "authored_by: t\nauthored_on: '2026-04-28T00:00:00.000Z'\n"
        "authored_via: outside\nprojection_types: []\n"
        "depends_on: []\nvisible_to: [dogfood-scan]\nparent: null\n"
        "expanded_into: null\nresolution_event: null\nresolved_at: null\n"
        "resolver: null\nrevalidate_trigger: null\nsuperseded_by: null\n"
        "supersedes: null\nsurrogate_of: null\nvalid_through: null\n"
        "domain: prism-ir-recomposition\ncollapsed_summary: bad\n"
        "---\n\n# Intention\n\nBad leaf.\n"
    )
    run_op("kernel.reindex", {"mode": "rebuild"})

    context.set_repo(workload_with_resolutions)
    context.set_current_intention_id("bad-leaf")
    try:
        with pytest.raises(ValueError, match="depends_on"):
            recomposer.build_payload("x")
    finally:
        context.clear()


# ---- adapt ---------------------------------------------------------------


def test_adapt_returns_prose_as_resolution_text(initialized):
    context.set_repo(initialized)
    context.set_current_intention_id("dummy-id")
    try:
        out = recomposer.adapt(
            {
                "resolution": "The workload's purpose was to produce a briefing.",
                "cost_actual": {"clock_ms": 100, "coin_usd": 0.01, "carbon_g": 0.5},
            }
        )
    finally:
        context.clear()
    assert out["resolution_text"] == "The workload's purpose was to produce a briefing."
    assert out["resolution_value"] == out["resolution_text"]
    assert out["cost_actual"]["coin_usd"] == 0.01


def test_adapt_writes_sidecar_artifact(initialized):
    context.set_repo(initialized)
    context.set_current_intention_id("test-rt-id")
    try:
        recomposer.adapt(
            {
                "resolution": "Reconstruction prose.",
                "cost_actual": {},
            }
        )
    finally:
        context.clear()
    artifact = (
        initialized
        / ".8os"
        / "dogfood-scan"
        / "artifacts"
        / "test-rt-id-reconstruction.md"
    )
    assert artifact.exists()
    assert artifact.read_text() == "Reconstruction prose."


def test_adapt_raises_when_no_resolution():
    with pytest.raises(ValueError, match="no 'resolution'"):
        recomposer.adapt({"cost_actual": {}})


def test_adapt_raises_on_non_dict_input():
    with pytest.raises(ValueError, match="must be a dict"):
        recomposer.adapt("not a dict")
