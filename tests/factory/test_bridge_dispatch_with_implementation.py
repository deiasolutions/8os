"""Factory dispatcher's bridge path — verifies bridge_ops dispatch (Piece 3) flows through.

Block 3 Piece 3 wired `kernel.bridge.cross` to dispatch via the bridge
(I, R)'s `implementation:` field. The factory's dispatcher's bridge
path was unchanged from Piece 1 — it still calls
`run_op("kernel.bridge.cross", ...)`. This test verifies the seam: a
factory dispatch through a bridge with `implementation:` set produces
a real bridge response (not the v0.2 echo), and the factory's
dispatcher passes that response through its adapter.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from eightos._frontmatter import IRRecord, serialize
from eightos.factory.dispatcher import dispatch
from eightos.factory.registry import Registry


def _bridge_impl(bridge_id: str, payload: Any, authorization, repo) -> dict[str, Any]:
    """Test bridge implementation called via bridge (I, R)'s implementation: field."""
    intention_id = (
        payload.get("intention_id") if isinstance(payload, dict) else "?"
    )
    return {
        "resolution": f"bridge-impl ran: intention={intention_id}",
        "cost_actual": {
            "clock_ms": 7.0,
            "coin_usd": 0.0001,
            "carbon_g": 0.05,
            "model_name": "test-model",
            "tokens_in": 25,
            "tokens_out": 12,
        },
        "audit": {"source": "factory-bridge-test"},
    }


def _author_bridge_with_impl(repo: Path, bridge_id: str, impl_spec: str) -> None:
    fm = {
        "id": bridge_id,
        "kind": "ir-node",
        "scope": "_kernel",
        "tier": 1,
        "status": "open",
        "authority_level": "hard",
        "authored_by": "kernel.self",
        "authored_on": "2026-04-27T00:00:00.000Z",
        "authored_via": "kernel.self",
        "projection_types": ["_kernel.bridge"],
        "depends_on": [],
        "visible_to": ["_kernel"],
        "bridge_id": bridge_id,
        "display_name": f"Test {bridge_id}",
        "bridge_type": "api",
        "requires_authorization": False,
        "scope_of_authority": "single",
        "cost_envelope": {"clock_ms_max": 1000, "coin_usd_max": 1.0, "carbon_g_max": 10.0},
        "endpoint": "test://localhost",
        "bridge_status": "active",
        "implementation": impl_spec,
        "parent": None,
        "expanded_into": None,
        "resolution_event": None,
        "resolved_at": None,
        "resolver": None,
        "resolver_id": None,
        "revalidate_trigger": None,
        "superseded_by": None,
        "supersedes": None,
        "surrogate_of": None,
        "valid_through": None,
    }
    rec = IRRecord(
        frontmatter=fm,
        intention_text=f"Test bridge {bridge_id}.",
        resolution_text=None,
    )
    p = repo / "ir" / "_kernel" / "bridge" / f"{bridge_id}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(serialize(rec))


def test_factory_dispatch_uses_bridge_implementation(
    initialized,
    author_resolver,
    run_op,
):
    """Factory's bridge dispatch path consumes the real bridge response
    produced by bridge_ops dispatching via implementation:."""
    impl_spec = (
        "tests.factory.test_bridge_dispatch_with_implementation:_bridge_impl"
    )
    _author_bridge_with_impl(initialized, "test-bridge", impl_spec)
    author_resolver(
        "bridge-resolver",
        bridge="test-bridge",
        implementation=None,  # bridge resolvers omit implementation
    )
    # Reindex so the bridge record is in id-to-path index (the
    # author_resolver fixture reindexes after writing the resolver,
    # which also catches the bridge written above).
    run_op("kernel.reindex", {"mode": "rebuild"})

    intention = IRRecord(
        frontmatter={"id": "subj-x", "scope": "test-scope"},
        intention_text="Cross the bridge.",
        resolution_text=None,
    )
    entry = Registry(initialized).get("bridge-resolver")
    out = dispatch(entry, intention, initialized)
    # Dispatcher passed the bridge response through default_adapter
    # (bridge resolvers have no impl module to look in for `adapt`).
    # default_adapter stringifies the structured response.
    assert "bridge-impl ran" in out["resolution_text"]
    assert "subj-x" in out["resolution_text"]
