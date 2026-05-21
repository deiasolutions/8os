"""kernel.bridge.cross dispatch via bridge (I, R) `implementation:` field.

Block 3 Piece 3 wired the v0.2-deferred outside-contact dispatch into
`kernel.bridge.cross`. These tests verify:

- Bridges WITHOUT `implementation:` keep using the v0.2 echo path
  (backward compat — `kernel.self` and any pre-Block-3 bridges).
- Bridges WITH `implementation:` get dispatched to the named function;
  the returned `{resolution, cost_actual, audit}` is recorded in the
  tier 3 event with the real cost vector replacing the prior zero
  placeholder.
- Bridge function exceptions surface as `BRIDGE_FAILED` with the
  underlying error in context.
- Missing module / bad spec / bad function name all surface as
  `BRIDGE_FAILED`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from eightos._frontmatter import IRRecord, serialize


# A test bridge implementation — used as the import target via the
# bridge (I, R)'s `implementation:` field.
def _stub_cross(bridge_id: str, payload: Any, authorization, repo) -> dict[str, Any]:
    return {
        "resolution": f"stub-cross got bridge={bridge_id} payload={payload!r}",
        "cost_actual": {
            "clock_ms": 42.5,
            "coin_usd": 0.0125,
            "carbon_g": 0.5,
            "model_name": "test-model",
            "tokens_in": 100,
            "tokens_out": 50,
        },
        "audit": {"source": "test-stub", "auth_present": authorization is not None},
    }


def _failing_cross(bridge_id, payload, authorization, repo):
    raise RuntimeError("deliberate bridge failure for test")


# Resolve where this test module is so the implementation: spec can
# point at the module's qualified path.
_THIS_MODULE = "tests.kernel.test_bridge_ops_implementation"


def _bridge_record(
    bridge_id: str,
    *,
    implementation: str | None = None,
    requires_authorization: bool = False,
) -> IRRecord:
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
        "requires_authorization": requires_authorization,
        "scope_of_authority": "single",
        "cost_envelope": {"clock_ms_max": 1000, "coin_usd_max": 1.0, "carbon_g_max": 10.0},
        "endpoint": "test://localhost",
        "bridge_status": "active",
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
    if implementation:
        fm["implementation"] = implementation
    return IRRecord(
        frontmatter=fm,
        intention_text=f"Test bridge {bridge_id}.",
        resolution_text=None,
    )


def _resolver_record_for_bridge(resolver_id: str, bridge_id: str) -> IRRecord:
    fm = {
        "id": resolver_id,
        "kind": "ir-node",
        "scope": "_kernel",
        "tier": 1,
        "status": "open",
        "authority_level": "hard",
        "authored_by": "kernel.self",
        "authored_on": "2026-04-27T00:00:00.000Z",
        "authored_via": "kernel.self",
        "projection_types": ["_kernel.resolver"],
        "depends_on": [],
        "visible_to": ["_kernel"],
        "resolver_id": resolver_id,
        "display_name": resolver_id,
        "bridge": bridge_id,
        "cost": {"clock_ms": 1, "coin_usd": 0, "carbon_g": 0, "currency": "USD"},
        "capability": {
            "test/domain": {
                "sigma": {"declared": 0.5, "measured": None},
                "pi": {"declared": 0.5, "measured": None},
                "alpha": {"declared": 0.5, "measured": None},
                "rho": {"declared": 0.5, "measured": None},
            }
        },
        "cost_model": "fixed",
        "model_name": None,
        "parent": None,
        "expanded_into": None,
        "resolution_event": None,
        "resolved_at": None,
        "resolver": None,
        "revalidate_trigger": None,
        "superseded_by": None,
        "supersedes": None,
        "surrogate_of": None,
        "valid_through": None,
        "collapsed_summary": resolver_id,
    }
    return IRRecord(
        frontmatter=fm,
        intention_text=f"Resolver {resolver_id} crossing {bridge_id}.",
        resolution_text=None,
    )


def _author_bridge_and_resolver(
    repo: Path, run_op, *, bridge_id: str, implementation: str | None
) -> None:
    # Hand-author bridge + resolver records (per OPEN-Q-026 expanded
    # to cover bridges; SDK-authored bridges can't carry
    # implementation:).
    bp = repo / "ir" / "_kernel" / "bridge" / f"{bridge_id}.md"
    bp.parent.mkdir(parents=True, exist_ok=True)
    bp.write_text(serialize(_bridge_record(bridge_id, implementation=implementation)))
    rp = repo / "ir" / "_kernel" / "resolver" / f"r-for-{bridge_id}.md"
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(
        serialize(_resolver_record_for_bridge(f"r-for-{bridge_id}", bridge_id))
    )
    run_op("kernel.reindex", {"mode": "rebuild"})


def _author_subject_intention(repo: Path, run_op, intention_id: str = "subj-1") -> None:
    run_op(
        "kernel.ir.new",
        {
            "scope_id": "test-scope",
            "slug": intention_id,
            "tier": 1,
            "intention_text": f"Subject of bridge crossing {intention_id}.",
            "authority_level": "convention",
            "authored_by": "test",
        },
    )


def _read_events(repo: Path) -> list[dict]:
    out = []
    for p in (repo / ".8os" / "events").rglob("*.jsonl"):
        for ln in p.read_text().splitlines():
            if ln.strip():
                out.append(json.loads(ln))
    return out


def test_v02_echo_path_when_no_implementation(initialized: Path, run_op):
    """Backward-compat: bridge without `implementation:` uses v0.2 echo."""
    _author_bridge_and_resolver(
        initialized, run_op, bridge_id="echo-bridge", implementation=None
    )
    _author_subject_intention(initialized, run_op)
    env = run_op(
        "kernel.bridge.cross",
        {
            "bridge_id": "echo-bridge",
            "resolver_id": "r-for-echo-bridge",
            "for_ir_id": "subj-1",
            "payload": {"hello": "world"},
        },
    )
    # v0.2 echo response shape: {echo: <payload>}
    assert env["data"]["response"] == {"echo": {"hello": "world"}}
    # Zero-cost placeholder (the v0.2 default).
    assert env["data"]["cost_actual"]["coin_usd"] == 0


def test_dispatches_via_implementation_when_field_present(initialized: Path, run_op):
    """Bridges with `implementation:` dispatch to the named function;
    real cost_actual surfaces."""
    _author_bridge_and_resolver(
        initialized,
        run_op,
        bridge_id="real-bridge",
        implementation=f"{_THIS_MODULE}:_stub_cross",
    )
    _author_subject_intention(initialized, run_op)
    env = run_op(
        "kernel.bridge.cross",
        {
            "bridge_id": "real-bridge",
            "resolver_id": "r-for-real-bridge",
            "for_ir_id": "subj-1",
            "payload": "test-payload",
        },
    )
    # Bridge function's structured response surfaces in env.data.response.
    response = env["data"]["response"]
    assert "stub-cross got bridge=real-bridge" in response["resolution"]
    # Real cost vector from the bridge function (not the v0.2 zero placeholder).
    assert env["data"]["cost_actual"]["coin_usd"] == 0.0125
    assert env["data"]["cost_actual"]["clock_ms"] == 42.5
    assert env["data"]["cost_actual"]["tokens_in"] == 100


def test_tier3_event_records_real_cost_and_audit(initialized: Path, run_op):
    """The crossing's tier 3 event captures the real cost and the bridge's audit dict."""
    _author_bridge_and_resolver(
        initialized,
        run_op,
        bridge_id="aud-bridge",
        implementation=f"{_THIS_MODULE}:_stub_cross",
    )
    _author_subject_intention(initialized, run_op)
    env = run_op(
        "kernel.bridge.cross",
        {
            "bridge_id": "aud-bridge",
            "resolver_id": "r-for-aud-bridge",
            "for_ir_id": "subj-1",
            "payload": {"x": 1},
        },
    )
    event_id = env["event_id"]
    events = _read_events(initialized)
    ev = next(e for e in events if e["event_id"] == event_id)
    assert ev["cost_actual"]["coin_usd"] == 0.0125
    assert ev["cost_actual"]["model_name"] == "test-model"
    assert ev["resolution"]["audit"] == {"source": "test-stub", "auth_present": False}


def test_bridge_function_exception_surfaces_as_BRIDGE_FAILED(
    initialized: Path, run_op
):
    """Bridge function raising an exception → BRIDGE_FAILED."""
    from eightos.errors import BRIDGE_FAILED, KernelError

    _author_bridge_and_resolver(
        initialized,
        run_op,
        bridge_id="bad-bridge",
        implementation=f"{_THIS_MODULE}:_failing_cross",
    )
    _author_subject_intention(initialized, run_op)
    with pytest.raises(KernelError) as exc_info:
        run_op(
            "kernel.bridge.cross",
            {
                "bridge_id": "bad-bridge",
                "resolver_id": "r-for-bad-bridge",
                "for_ir_id": "subj-1",
            },
        )
    assert exc_info.value.code == BRIDGE_FAILED
    assert "deliberate bridge failure" in exc_info.value.message


def test_bad_implementation_spec_surfaces_as_BRIDGE_FAILED(
    initialized: Path, run_op
):
    """Malformed `implementation:` (missing colon) → BRIDGE_FAILED."""
    from eightos.errors import BRIDGE_FAILED, KernelError

    _author_bridge_and_resolver(
        initialized, run_op, bridge_id="malformed", implementation="no.colon.here"
    )
    _author_subject_intention(initialized, run_op)
    with pytest.raises(KernelError) as exc_info:
        run_op(
            "kernel.bridge.cross",
            {
                "bridge_id": "malformed",
                "resolver_id": "r-for-malformed",
                "for_ir_id": "subj-1",
            },
        )
    assert exc_info.value.code == BRIDGE_FAILED


def test_missing_module_surfaces_as_BRIDGE_FAILED(initialized: Path, run_op):
    """Unknown module in `implementation:` → BRIDGE_FAILED."""
    from eightos.errors import BRIDGE_FAILED, KernelError

    _author_bridge_and_resolver(
        initialized,
        run_op,
        bridge_id="ghost",
        implementation="no.such.module:cross",
    )
    _author_subject_intention(initialized, run_op)
    with pytest.raises(KernelError) as exc_info:
        run_op(
            "kernel.bridge.cross",
            {
                "bridge_id": "ghost",
                "resolver_id": "r-for-ghost",
                "for_ir_id": "subj-1",
            },
        )
    assert exc_info.value.code == BRIDGE_FAILED
