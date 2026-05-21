"""Materializer tests — hand-built graph specs to kernel records.

Block 3 Piece 4. Deterministic, no LLM. Hand-build a graph spec, run
it through `materialize`, assert the kernel records were authored with
the right shape.
"""

from __future__ import annotations

import pytest

from eightos._frontmatter import parse_file
from eightos._yaml import load_yaml_file
from eightos.factory.materializer import (
    MaterializationError,
    materialize,
)


def _two_node_spec() -> dict:
    return {
        "nodes": [
            {
                "node_id": "fetch",
                "intention_text": "Fetch data.",
                "depends_on": [],
                "prism_operator": {
                    "op": "script",
                    "resolver": "fetch-data",
                    "model": None,
                },
            },
            {
                "node_id": "summarize",
                "intention_text": "Summarize the fetched data.",
                "depends_on": ["fetch"],
                "prism_operator": {
                    "op": "llm",
                    "resolver": "summarizer",
                    "model": None,
                },
            },
        ]
    }


def _diamond_spec() -> dict:
    """Source -> {a, b} -> sink. Tests parallel-fork-style topology."""
    return {
        "nodes": [
            {
                "node_id": "src",
                "intention_text": "Source.",
                "depends_on": [],
                "prism_operator": None,
            },
            {
                "node_id": "branch-a",
                "intention_text": "Branch A.",
                "depends_on": ["src"],
                "prism_operator": None,
            },
            {
                "node_id": "branch-b",
                "intention_text": "Branch B.",
                "depends_on": ["src"],
                "prism_operator": None,
            },
            {
                "node_id": "sink",
                "intention_text": "Sink.",
                "depends_on": ["branch-a", "branch-b"],
                "prism_operator": None,
            },
        ]
    }


# ---- materialize: happy paths ----------------------------------------------


def test_materialize_authors_records_in_topological_order(initialized):
    ids = materialize(
        _two_node_spec(),
        scope_id="test-scope",
        authored_by="prism-ir-decomposer",
    )
    assert ids == ["fetch", "summarize"]
    # Both records on disk
    fetch_path = initialized / "ir" / "test-scope" / "fetch.md"
    summarize_path = initialized / "ir" / "test-scope" / "summarize.md"
    assert fetch_path.exists()
    assert summarize_path.exists()


def test_materialize_preserves_depends_on_in_frontmatter(initialized):
    materialize(
        _two_node_spec(),
        scope_id="test-scope",
        authored_by="prism-ir-decomposer",
    )
    summarize_rec = parse_file(
        initialized / "ir" / "test-scope" / "summarize.md"
    )
    assert summarize_rec.frontmatter["depends_on"] == ["fetch"]


def test_materialize_records_authored_by_and_via(initialized):
    materialize(
        _two_node_spec(),
        scope_id="test-scope",
        authored_by="prism-ir-decomposer",
        authored_via="anthropic",
    )
    rec = parse_file(initialized / "ir" / "test-scope" / "fetch.md")
    assert rec.frontmatter["authored_by"] == "prism-ir-decomposer"
    assert rec.frontmatter["authored_via"] == "anthropic"


def test_materialize_default_authority_level_is_convention(initialized):
    materialize(
        _two_node_spec(),
        scope_id="test-scope",
        authored_by="prism-ir-decomposer",
    )
    rec = parse_file(initialized / "ir" / "test-scope" / "fetch.md")
    assert rec.frontmatter["authority_level"] == "convention"


def test_materialize_embeds_prism_operator_as_yaml_block(initialized):
    materialize(
        _two_node_spec(),
        scope_id="test-scope",
        authored_by="prism-ir-decomposer",
    )
    fetch_rec = parse_file(initialized / "ir" / "test-scope" / "fetch.md")
    assert "```yaml" in fetch_rec.intention_text
    assert "prism_operator:" in fetch_rec.intention_text
    assert "fetch-data" in fetch_rec.intention_text


def test_materialize_omits_yaml_block_when_prism_operator_null(initialized):
    spec = {
        "nodes": [
            {
                "node_id": "noop-x",
                "intention_text": "Plain text only.",
                "depends_on": [],
                "prism_operator": None,
            }
        ]
    }
    materialize(spec, scope_id="test-scope", authored_by="t")
    rec = parse_file(initialized / "ir" / "test-scope" / "noop-x.md")
    assert rec.intention_text == "Plain text only."


def test_materialize_diamond_orders_sink_last(initialized):
    ids = materialize(
        _diamond_spec(),
        scope_id="test-scope",
        authored_by="t",
    )
    # src first, sink last; branches in source order between them.
    assert ids[0] == "src"
    assert ids[-1] == "sink"
    assert set(ids[1:3]) == {"branch-a", "branch-b"}
    # Source-order tie-break: branch-a before branch-b.
    assert ids[1] == "branch-a"


def test_materialize_empty_spec_returns_empty_list(initialized):
    assert materialize({"nodes": []}, scope_id="test-scope", authored_by="t") == []
    assert materialize({}, scope_id="test-scope", authored_by="t") == []


def test_materialize_updates_id_to_path_index(initialized):
    materialize(
        _two_node_spec(),
        scope_id="test-scope",
        authored_by="t",
    )
    idx = load_yaml_file(initialized / ".8os" / "index" / "id-to-path.yml") or {}
    assert "fetch" in idx
    assert "summarize" in idx


# ---- materialize: error paths ----------------------------------------------


def test_materialize_cycle_raises(initialized):
    spec = {
        "nodes": [
            {
                "node_id": "a",
                "intention_text": "A.",
                "depends_on": ["b"],
                "prism_operator": None,
            },
            {
                "node_id": "b",
                "intention_text": "B.",
                "depends_on": ["a"],
                "prism_operator": None,
            },
        ]
    }
    with pytest.raises(MaterializationError, match="cycle"):
        materialize(spec, scope_id="test-scope", authored_by="t")


def test_materialize_dangling_dep_raises(initialized):
    spec = {
        "nodes": [
            {
                "node_id": "a",
                "intention_text": "A.",
                "depends_on": ["nonexistent"],
                "prism_operator": None,
            }
        ]
    }
    with pytest.raises(MaterializationError, match="not in this spec"):
        materialize(spec, scope_id="test-scope", authored_by="t")


def test_materialize_duplicate_node_id_raises(initialized):
    spec = {
        "nodes": [
            {
                "node_id": "x",
                "intention_text": "First.",
                "depends_on": [],
                "prism_operator": None,
            },
            {
                "node_id": "x",
                "intention_text": "Second.",
                "depends_on": [],
                "prism_operator": None,
            },
        ]
    }
    with pytest.raises(MaterializationError, match="duplicate"):
        materialize(spec, scope_id="test-scope", authored_by="t")


# ---- materialize: parent_id wiring -----------------------------------------


def test_materialize_with_parent_id_authors_under_parent(initialized, run_op):
    """When parent_id is given, records are authored as children of the
    expanded parent's folder."""
    # Author a root intention via the SDK (no projection extensions, so
    # this works directly through kernel.ir.new).
    run_op(
        "kernel.ir.new",
        {
            "scope_id": "test-scope",
            "slug": "root-decomp",
            "tier": 1,
            "intention_text": "Root decomposition intent.",
            "authority_level": "convention",
            "authored_by": "test",
            "authored_via": "outside",
        },
    )

    ids = materialize(
        _two_node_spec(),
        scope_id="test-scope",
        authored_by="prism-ir-decomposer",
        parent_id="root-decomp",
    )
    assert ids == ["fetch", "summarize"]

    # Parent should now be expanded; children live under its folder.
    parent_folder = initialized / "ir" / "test-scope" / "root-decomp"
    assert (parent_folder / "_node.md").exists()
    assert (parent_folder / "fetch.md").exists()
    assert (parent_folder / "summarize.md").exists()


def test_materialize_with_already_expanded_parent_is_idempotent(
    initialized, run_op
):
    run_op(
        "kernel.ir.new",
        {
            "scope_id": "test-scope",
            "slug": "root-x",
            "tier": 1,
            "intention_text": "Root.",
            "authority_level": "convention",
            "authored_by": "test",
            "authored_via": "outside",
        },
    )
    run_op("kernel.ir.expand", {"ir_id": "root-x"})
    # Calling materialize against an already-expanded parent should not raise.
    spec = {
        "nodes": [
            {
                "node_id": "child-1",
                "intention_text": "Child.",
                "depends_on": [],
                "prism_operator": None,
            }
        ]
    }
    ids = materialize(
        spec, scope_id="test-scope", authored_by="t", parent_id="root-x"
    )
    assert ids == ["child-1"]


def test_materialize_unknown_parent_raises(initialized):
    spec = {
        "nodes": [
            {
                "node_id": "x",
                "intention_text": "x",
                "depends_on": [],
                "prism_operator": None,
            }
        ]
    }
    with pytest.raises(MaterializationError, match="not found"):
        materialize(
            spec,
            scope_id="test-scope",
            authored_by="t",
            parent_id="nonexistent-parent",
        )
