"""Dispatcher tests — two-case (inside vs bridge) dispatch (Shape 5)."""

from __future__ import annotations

import pytest

from eightos._frontmatter import IRRecord
from eightos.factory.dispatcher import dispatch
from eightos.factory.registry import Registry


def _intention(intention_id: str = "subj-1") -> IRRecord:
    return IRRecord(
        frontmatter={"id": intention_id, "scope": "test-scope"},
        intention_text="An intention to dispatch.",
        resolution_text=None,
    )


def test_dispatcher_inside_path_invokes_implementation(initialized, author_resolver):
    author_resolver(
        "inside-r",
        bridge=None,
        implementation="tests.factory._fake_resolvers:simple_resolve_with_adapter",
    )
    entry = Registry(initialized).get("inside-r")
    out = dispatch(entry, _intention("subj-x"), initialized)
    # Adapter ran on the resolver's structured output.
    assert "adapted" in out["resolution_text"]
    assert out["resolution_value"] == 42  # raw_value from simple_resolve_with_adapter


def test_dispatcher_inside_path_propagates_resolver_exception(initialized, author_resolver):
    author_resolver(
        "fails",
        bridge=None,
        implementation="tests.factory._fake_resolvers:failing_resolve",
    )
    entry = Registry(initialized).get("fails")
    with pytest.raises(RuntimeError, match="deliberate failure"):
        dispatch(entry, _intention(), initialized)


def test_dispatcher_inside_path_uses_default_adapter(initialized, author_resolver):
    author_resolver(
        "no-adapt-disp",
        bridge=None,
        implementation="tests.factory._no_adapter:resolve",
    )
    entry = Registry(initialized).get("no-adapt-disp")
    out = dispatch(entry, _intention("subj-na"), initialized)
    # default_adapter stringifies and emits zero-cost.
    assert "no-adapter-here" in out["resolution_text"]
    assert out["cost_actual"]["clock_ms"] == 0.0


def test_dispatcher_bridge_path_goes_through_kernel_bridge_cross(
    initialized, author_resolver, run_op
):
    # Author a synthetic bridge (I, R) directly so kernel.bridge.cross
    # can find it. The bridge schema requires bridge_status and the
    # base-frontmatter discipline; minimal field set below.
    bridge_path = initialized / "ir" / "_kernel" / "bridge" / "fake-bridge.md"
    bridge_path.parent.mkdir(parents=True, exist_ok=True)
    bridge_path.write_text(
        "---\n"
        "id: fake-bridge\n"
        "kind: ir-node\n"
        "scope: _kernel\n"
        "tier: 1\n"
        "status: open\n"
        "authority_level: hard\n"
        "authored_by: kernel.self\n"
        "authored_on: '2026-04-27T00:00:00.000Z'\n"
        "authored_via: kernel.self\n"
        "projection_types: [_kernel.bridge]\n"
        "depends_on: []\n"
        "visible_to: [_kernel]\n"
        "bridge_id: fake-bridge\n"
        "display_name: Fake bridge\n"
        "endpoint: 'inproc://test'\n"
        "bridge_status: active\n"
        "requires_authorization: false\n"
        "model: null\n"
        "model_name: null\n"
        "parent: null\n"
        "expanded_into: null\n"
        "resolution_event: null\n"
        "resolved_at: null\n"
        "resolver: null\n"
        "resolver_id: null\n"
        "revalidate_trigger: null\n"
        "superseded_by: null\n"
        "supersedes: null\n"
        "surrogate_of: null\n"
        "valid_through: null\n"
        "---\n\n"
        "# Intention\n\nA test bridge for factory dispatcher unit tests.\n"
    )
    author_resolver(
        "bridge-r",
        bridge="fake-bridge",
        implementation=None,
    )
    entry = Registry(initialized).get("bridge-r")
    out = dispatch(entry, _intention("subj-b"), initialized)
    # bridge.cross v0.2 echoes the payload back inside {"echo": ...},
    # which the default_adapter (since bridge resolver has no impl
    # module to look in) stringifies into resolution_text.
    assert "subj-b" in out["resolution_text"]
