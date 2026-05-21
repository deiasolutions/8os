"""Tests for the Piece 5 dispatcher/walker/tick changes.

Block 3 Piece 5. Three pieces of new machinery, each tested in isolation
plus one end-to-end test that exercises the full graph-producing
dispatch path against synthetic resolvers (no LLM).

- Walker filters out records with non-null `expanded_into`. Without
  this an expanded parent stays "open" and would be re-dispatched
  forever.
- ResolverEntry exposes `produces` (default "value", "graph"
  triggers materialization branch) and `module` (Python module path
  for adapter / build_payload discovery on bridge-crossing resolvers).
- Tick's graph-producing branch calls the materializer with
  parent_id=intention_id instead of calling kernel.ir.resolve.

Real-LLM end-to-end is `test_decomposer_e2e.py` (Piece 4) and the SCAN
dogfood end-to-end test (this Piece, in `test_dogfood_e2e.py`).
"""

from __future__ import annotations

from eightos._frontmatter import IRRecord, parse_file, serialize
from eightos.factory.dispatcher import dispatch
from eightos.factory.registry import Registry, ResolverEntry
from eightos.factory.tick import tick
from eightos.factory.walker import find_dispatchable_leaves


# ---- ResolverEntry field parsing -------------------------------------------


def test_resolver_entry_default_produces_is_value():
    fm = {
        "resolver_id": "x",
        "bridge": None,
        "implementation": "mod:fn",
    }
    entry = ResolverEntry.from_frontmatter(fm)
    assert entry.produces == "value"


def test_resolver_entry_reads_produces_graph():
    fm = {
        "resolver_id": "x",
        "bridge": "anthropic",
        "implementation": None,
        "produces": "graph",
    }
    entry = ResolverEntry.from_frontmatter(fm)
    assert entry.produces == "graph"


def test_resolver_entry_reads_module():
    fm = {
        "resolver_id": "x",
        "bridge": "anthropic",
        "implementation": None,
        "module": "eightos.factory.decomposer",
    }
    entry = ResolverEntry.from_frontmatter(fm)
    assert entry.module == "eightos.factory.decomposer"


def test_resolver_entry_module_none_by_default():
    fm = {
        "resolver_id": "x",
        "bridge": None,
        "implementation": "mod:fn",
    }
    entry = ResolverEntry.from_frontmatter(fm)
    assert entry.module is None


# ---- Registry adapter / payload-builder discovery -------------------------


def test_load_adapter_via_module_for_bridge_crossing_resolver(
    initialized, author_resolver
):
    author_resolver(
        "decomp-r",
        bridge="fake-bridge",
        implementation=None,
    )
    # Hand-edit the resolver to add `module:` since author_resolver
    # doesn't expose it. The conftest helper writes via a synthetic
    # IRRecord serializer; reach into it.
    path = initialized / "ir" / "_kernel" / "resolver" / "decomp-r.md"
    rec = parse_file(path)
    rec.frontmatter["module"] = "eightos.factory.decomposer"
    path.write_text(serialize(rec))
    from eightos.sdk._runner import run as run_op
    run_op("kernel.reindex", {"mode": "rebuild"})

    entry = Registry(initialized).get("decomp-r")
    assert entry.module == "eightos.factory.decomposer"
    adapter = entry.load_adapter()
    # decomposer.adapt is the discovered function.
    from eightos.factory import decomposer
    assert adapter is decomposer.adapt


def test_load_payload_builder_via_module(initialized, author_resolver):
    author_resolver(
        "decomp-r2",
        bridge="fake-bridge",
        implementation=None,
    )
    path = initialized / "ir" / "_kernel" / "resolver" / "decomp-r2.md"
    rec = parse_file(path)
    rec.frontmatter["module"] = "eightos.factory.decomposer"
    path.write_text(serialize(rec))
    from eightos.sdk._runner import run as run_op
    run_op("kernel.reindex", {"mode": "rebuild"})

    entry = Registry(initialized).get("decomp-r2")
    builder = entry.load_payload_builder()
    from eightos.factory import decomposer
    assert builder is decomposer.build_payload


def test_load_payload_builder_returns_none_when_no_module(
    initialized, author_resolver
):
    author_resolver(
        "value-r",
        bridge=None,
        implementation="tests.factory._fake_resolvers:simple_resolve_with_adapter",
    )
    entry = Registry(initialized).get("value-r")
    # No build_payload in _fake_resolvers — should return None.
    assert entry.load_payload_builder() is None


# ---- Walker: skips expanded records ---------------------------------------


def test_walker_skips_expanded_parents(initialized, run_op, author_intention):
    # Author a parent intention.
    author_intention("expanded-parent", scope="test-scope")
    # Expand it via the kernel op.
    run_op("kernel.ir.expand", {"ir_id": "expanded-parent"})
    # Walker should not return it.
    leaves = find_dispatchable_leaves(initialized, "test-scope")
    leaf_ids = {leaf.frontmatter["id"] for leaf in leaves}
    assert "expanded-parent" not in leaf_ids


def test_walker_returns_unexpanded_open_intentions(initialized, author_intention):
    author_intention("normal-leaf", scope="test-scope")
    leaves = find_dispatchable_leaves(initialized, "test-scope")
    leaf_ids = {leaf.frontmatter["id"] for leaf in leaves}
    assert "normal-leaf" in leaf_ids


# ---- Dispatcher: build_payload routing -------------------------------------


def _intention(intention_id: str = "subj-1") -> IRRecord:
    return IRRecord(
        frontmatter={"id": intention_id, "scope": "test-scope"},
        intention_text="Decompose this PRISM-IR doc.",
        resolution_text=None,
    )


def test_dispatcher_uses_module_build_payload_when_available(
    initialized, author_resolver, monkeypatch
):
    """When a bridge-crossing resolver's module exposes build_payload,
    the dispatcher uses its output as the bridge.cross inner payload."""
    # Author bridge + resolver records.
    bridge_path = initialized / "ir" / "_kernel" / "bridge" / "fake-bridge.md"
    bridge_path.parent.mkdir(parents=True, exist_ok=True)
    bridge_path.write_text(
        "---\n"
        "id: fake-bridge\nkind: ir-node\nscope: _kernel\ntier: 1\nstatus: open\n"
        "authority_level: hard\nauthored_by: kernel.self\n"
        "authored_on: '2026-04-27T00:00:00.000Z'\nauthored_via: kernel.self\n"
        "projection_types: [_kernel.bridge]\ndepends_on: []\nvisible_to: [_kernel]\n"
        "bridge_id: fake-bridge\ndisplay_name: Fake bridge\nendpoint: 'inproc://test'\n"
        "bridge_status: active\nrequires_authorization: false\n"
        "model: null\nmodel_name: null\nparent: null\nexpanded_into: null\n"
        "resolution_event: null\nresolved_at: null\nresolver: null\nresolver_id: null\n"
        "revalidate_trigger: null\nsuperseded_by: null\nsupersedes: null\n"
        "surrogate_of: null\nvalid_through: null\n"
        "---\n\n# Intention\n\nA test bridge.\n"
    )
    author_resolver(
        "builder-r",
        bridge="fake-bridge",
        implementation=None,
    )
    rpath = initialized / "ir" / "_kernel" / "resolver" / "builder-r.md"
    rec = parse_file(rpath)
    rec.frontmatter["module"] = "eightos.factory.decomposer"
    rpath.write_text(serialize(rec))
    from eightos.sdk._runner import run as run_op
    run_op("kernel.reindex", {"mode": "rebuild"})

    # Capture run_op calls — check the bridge.cross payload carries the
    # decomposer's prompt as `system` (proof that build_payload ran).
    captured = {}

    def fake_run_op(op: str, payload: dict) -> dict:
        if op == "kernel.bridge.cross":
            captured["payload"] = payload
            # Return a synthetic response that decomposer.adapt accepts.
            return {
                "data": {
                    "response": {
                        "resolution": '{"nodes": []}',
                        "cost_actual": {"clock_ms": 0, "coin_usd": 0, "carbon_g": 0},
                    },
                },
                "event_id": "evt",
                "indexes_updated": [],
            }
        # Fall through to real for any other op.
        return run_op(op, payload)

    monkeypatch.setattr("eightos.factory.dispatcher.run_op", fake_run_op)

    entry = Registry(initialized).get("builder-r")
    dispatch(entry, _intention("subj-bp"), initialized)

    # build_payload threaded the system prompt + user message through.
    inner = captured["payload"]["payload"]
    assert "system" in inner
    assert "PRISM-IR" in inner["system"]
    assert inner["messages"][0]["content"] == "Decompose this PRISM-IR doc."


def test_dispatcher_falls_back_to_minimal_payload_when_no_builder(
    initialized, author_resolver, monkeypatch
):
    """Resolvers without build_payload get the Piece 1 minimal echo payload."""
    bridge_path = initialized / "ir" / "_kernel" / "bridge" / "fake-bridge2.md"
    bridge_path.parent.mkdir(parents=True, exist_ok=True)
    bridge_path.write_text(
        "---\n"
        "id: fake-bridge2\nkind: ir-node\nscope: _kernel\ntier: 1\nstatus: open\n"
        "authority_level: hard\nauthored_by: kernel.self\n"
        "authored_on: '2026-04-27T00:00:00.000Z'\nauthored_via: kernel.self\n"
        "projection_types: [_kernel.bridge]\ndepends_on: []\nvisible_to: [_kernel]\n"
        "bridge_id: fake-bridge2\ndisplay_name: Fake bridge 2\n"
        "endpoint: 'inproc://test'\nbridge_status: active\n"
        "requires_authorization: false\nmodel: null\nmodel_name: null\n"
        "parent: null\nexpanded_into: null\nresolution_event: null\n"
        "resolved_at: null\nresolver: null\nresolver_id: null\n"
        "revalidate_trigger: null\nsuperseded_by: null\nsupersedes: null\n"
        "surrogate_of: null\nvalid_through: null\n"
        "---\n\n# Intention\n\nAnother test bridge.\n"
    )
    author_resolver("plain-bridge-r", bridge="fake-bridge2", implementation=None)
    captured = {}

    def fake_run_op(op: str, payload: dict) -> dict:
        if op == "kernel.bridge.cross":
            captured["payload"] = payload
            return {
                "data": {
                    "response": {
                        "echo": payload.get("payload"),
                    },
                },
                "event_id": "evt",
                "indexes_updated": [],
            }
        from eightos.sdk._runner import run as r
        return r(op, payload)

    monkeypatch.setattr("eightos.factory.dispatcher.run_op", fake_run_op)
    entry = Registry(initialized).get("plain-bridge-r")
    dispatch(entry, _intention("subj-mp"), initialized)
    inner = captured["payload"]["payload"]
    assert inner == {
        "intention_id": "subj-mp",
        "intention_text": "Decompose this PRISM-IR doc.",
    }


# ---- Tick: graph-producing branch -----------------------------------------


def test_tick_graph_producing_branch_materializes_children(
    initialized, run_op, author_resolver, author_intention
):
    """When the selected resolver has produces=graph, tick materializes
    the resolution_value as children of the leaf instead of calling
    kernel.ir.resolve."""
    # Author an inside graph-producing resolver pointing at a
    # synthetic implementation that returns a canned graph spec.
    author_resolver(
        "synthetic-graph-resolver",
        bridge=None,
        implementation="tests.factory._graph_resolver:produce_graph",
    )
    # Patch in produces=graph.
    rpath = (
        initialized / "ir" / "_kernel" / "resolver" / "synthetic-graph-resolver.md"
    )
    rec = parse_file(rpath)
    rec.frontmatter["produces"] = "graph"
    # Cap selector picks: declare a domain and capability the leaf will match.
    rec.frontmatter["capability"] = {
        "graph-test": {
            "sigma": {"declared": 1.0, "measured": None},
            "pi": {"declared": 1.0, "measured": None},
            "alpha": {"declared": 1.0, "measured": None},
            "rho": {"declared": 1.0, "measured": None},
        }
    }
    rpath.write_text(serialize(rec))
    run_op("kernel.reindex", {"mode": "rebuild"})

    # Author a leaf intention with matching domain.
    author_intention("graph-leaf", scope="test-scope", domain="graph-test")

    # Tick.
    summary = tick(initialized, "test-scope", domain="graph-test")
    dispatched = summary["dispatched"]
    leaf_results = [d for d in dispatched if d["intention_id"] == "graph-leaf"]
    assert len(leaf_results) == 1
    res = leaf_results[0]
    assert res["ok"] is True
    assert res["resolver_id"] == "synthetic-graph-resolver"
    assert res.get("materialized_children") == 2

    # Children should now exist under the expanded parent.
    parent_folder = initialized / "ir" / "test-scope" / "graph-leaf"
    assert (parent_folder / "_node.md").exists()
    assert (parent_folder / "child-a.md").exists()
    assert (parent_folder / "child-b.md").exists()

    # Parent should be expanded (expanded_into is non-null).
    parent_rec = parse_file(parent_folder / "_node.md")
    assert parent_rec.frontmatter["expanded_into"] == "graph-leaf"
    # Walker shouldn't pick it up again.
    leaves = find_dispatchable_leaves(initialized, "test-scope")
    leaf_ids = {leaf.frontmatter["id"] for leaf in leaves}
    assert "graph-leaf" not in leaf_ids


def test_tick_value_producing_branch_unchanged(
    initialized, run_op, author_resolver, author_intention
):
    """Default produces=value path still calls kernel.ir.resolve — sanity
    that Piece 5 didn't regress Pieces 1-4 behavior."""
    author_resolver(
        "value-r",
        bridge=None,
        implementation="tests.factory._fake_resolvers:simple_resolve_with_adapter",
    )
    rpath = initialized / "ir" / "_kernel" / "resolver" / "value-r.md"
    rec = parse_file(rpath)
    rec.frontmatter["capability"] = {
        "value-test": {
            "sigma": {"declared": 1.0, "measured": None},
            "pi": {"declared": 1.0, "measured": None},
            "alpha": {"declared": 1.0, "measured": None},
            "rho": {"declared": 1.0, "measured": None},
        }
    }
    rpath.write_text(serialize(rec))
    run_op("kernel.reindex", {"mode": "rebuild"})

    author_intention("value-leaf", scope="test-scope", domain="value-test")
    summary = tick(initialized, "test-scope", domain="value-test")
    dispatched = summary["dispatched"]
    res = next(d for d in dispatched if d["intention_id"] == "value-leaf")
    assert res["ok"] is True
    assert "materialized_children" not in res

    # Leaf should now be resolved.
    rec = parse_file(initialized / "ir" / "test-scope" / "value-leaf.md")
    assert rec.frontmatter["status"] == "resolved"
