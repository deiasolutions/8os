"""Graph-spec round-trip — materialize then reconstruct, no LLM.

Block 3 Piece 4. De-risks Piece 6's recomposer by exercising the
structural layer end-to-end without an LLM in the loop. A hand-built
canonical graph spec is materialized into kernel records under a
parent intention; the reconstruction walks the parent's children and
produces a graph spec that must match the original.

Tests use `parent_id` mode exclusively — that's the canonical shape
Piece 6's recomposer will use (it dispatches against a known parent
intention and walks its children). The flat-scope reconstructor mode
exists for debugging but isn't covered here because the user scope
also holds kernel.init's bootstrap record, which is not part of any
workload graph.

If this round-trip ever drifts, the recomposer's English output will
also drift; failures here are an early signal for Piece 6.
"""

from __future__ import annotations

import pytest

from eightos.factory.materializer import (
    materialize,
    reconstruct_graph_spec_from_records,
)


def _canonical_spec() -> dict:
    """A four-node spec covering the dogfood shape (Piece 5 preview).

    Sequential edges: fetch → score → rank → brief. Each node carries a
    distinct prism_operator (script + 2x llm + script) so the
    embedding/extraction round-trip is exercised across operator types.
    """
    return {
        "nodes": [
            {
                "node_id": "rt-fetch-sources",
                "intention_text": "Fetch top stories and recent items from declared sources.",
                "depends_on": [],
                "prism_operator": {
                    "op": "script",
                    "resolver": "fetch-sources",
                    "model": None,
                },
            },
            {
                "node_id": "rt-score-relevance",
                "intention_text": "Score each fetched item's relevance to the briefing topic.",
                "depends_on": ["rt-fetch-sources"],
                "prism_operator": {
                    "op": "llm",
                    "resolver": "score-relevance",
                    "model": "claude-haiku-4-5",
                },
            },
            {
                "node_id": "rt-filter-and-rank",
                "intention_text": "Pick the top-N items by score.",
                "depends_on": ["rt-score-relevance"],
                "prism_operator": {
                    "op": "script",
                    "resolver": "filter-and-rank",
                    "model": None,
                },
            },
            {
                "node_id": "rt-generate-briefing",
                "intention_text": "Compose a structured briefing artifact from the top items.",
                "depends_on": ["rt-filter-and-rank"],
                "prism_operator": {
                    "op": "llm",
                    "resolver": "generate-briefing",
                    "model": "claude-sonnet-4-6",
                },
            },
        ]
    }


def _index_by_id(spec: dict) -> dict[str, dict]:
    return {n["node_id"]: n for n in spec["nodes"]}


@pytest.fixture
def workload_root(initialized, run_op):
    """Author a parent intention so materialize+reconstruct can run under it."""
    run_op(
        "kernel.ir.new",
        {
            "scope_id": "test-scope",
            "slug": "rt-root",
            "tier": 1,
            "intention_text": "Root.",
            "authority_level": "convention",
            "authored_by": "test",
            "authored_via": "outside",
        },
    )
    return "rt-root"


def test_roundtrip_canonical_spec_under_parent(workload_root):
    canonical = _canonical_spec()
    materialize(
        canonical,
        scope_id="test-scope",
        authored_by="t",
        parent_id=workload_root,
    )

    reconstructed = reconstruct_graph_spec_from_records(
        scope_id="test-scope", parent_id=workload_root
    )

    by_id = _index_by_id(reconstructed)
    assert set(by_id) == {n["node_id"] for n in canonical["nodes"]}
    for orig in canonical["nodes"]:
        recon = by_id[orig["node_id"]]
        assert recon["intention_text"] == orig["intention_text"]
        assert recon["depends_on"] == orig["depends_on"]
        assert recon["prism_operator"] == orig["prism_operator"]


def test_roundtrip_preserves_null_prism_operator(workload_root):
    spec = {
        "nodes": [
            {
                "node_id": "rt-plain",
                "intention_text": "Just plain text, no operator.",
                "depends_on": [],
                "prism_operator": None,
            }
        ]
    }
    materialize(
        spec,
        scope_id="test-scope",
        authored_by="t",
        parent_id=workload_root,
    )
    recon = reconstruct_graph_spec_from_records(
        scope_id="test-scope", parent_id=workload_root
    )
    by_id = _index_by_id(recon)
    assert "rt-plain" in by_id
    assert by_id["rt-plain"]["prism_operator"] is None
    assert by_id["rt-plain"]["intention_text"] == "Just plain text, no operator."


def test_roundtrip_unauthored_parent_returns_empty(workload_root):
    """An expanded parent with no children yields an empty graph spec."""
    from eightos.sdk._runner import run as run_op

    run_op("kernel.ir.expand", {"ir_id": workload_root})
    recon = reconstruct_graph_spec_from_records(
        scope_id="test-scope", parent_id=workload_root
    )
    assert recon == {"nodes": []}
