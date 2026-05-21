"""Tests for kernel.ir.{resolve, expand, collapse, supersede, deps, promote}."""

from __future__ import annotations

from pathlib import Path

import pytest

from eightos.errors import INVALID_STATE, NOT_FOUND, KernelError
from eightos._frontmatter import parse_file


def _new(**over):
    base = {
        "scope_id": "test-scope",
        "slug": "decision-1",
        "tier": 1,
        "intention_text": "Pick one.",
        "authority_level": "convention",
        "authored_by": "test-author",
    }
    base.update(over)
    return base


def _bridge_and_resolver(run_op):
    """Author a synthetic bridge and resolver as v0.2 kernel-configuration (I, R)s.

    v0.1's `kernel.bridge.add` and `kernel.resolver.add` were removed; both are
    now (I, R) records under `ir/_kernel/<category>/` authored through
    `kernel.ir.new` with the matching `_kernel.*` projection type.
    """
    run_op(
        "kernel.ir.new",
        {
            "scope_id": "_kernel",
            "slug": "synthetic",
            "tier": 1,
            "intention_text": "Synthetic test bridge.",
            "projection_types": ["_kernel.bridge"],
            "authority_level": "hard",
            "authored_by": "test-author",
            "frontmatter_extensions": {
                "bridge_id": "synthetic",
                "display_name": "Synthetic Bridge",
                "bridge_type": "other",
                "requires_authorization": False,
                "scope_of_authority": "session",
                "cost_envelope": {
                    "clock_ms_max": 1000,
                    "coin_usd_max": 0.01,
                    "carbon_g_max": 1,
                },
                "endpoint": {"protocol": "local"},
            },
        },
    )
    run_op(
        "kernel.ir.new",
        {
            "scope_id": "_kernel",
            "slug": "synth-resolver",
            "tier": 1,
            "intention_text": "Synthetic test resolver.",
            "projection_types": ["_kernel.resolver"],
            "authority_level": "hard",
            "authored_by": "test-author",
            "frontmatter_extensions": {
                "resolver_id": "synth-resolver",
                "display_name": "Synthetic Resolver",
                "bridge": "synthetic",
                "cost": {
                    "clock_ms": 250,
                    "coin_usd": 0.001,
                    "carbon_g": 0.05,
                    "currency": "USD",
                },
                "capability": {
                    "synth": {
                        "sigma": {"declared": 0.9, "measured": None},
                        "pi": {"declared": 0.9, "measured": None},
                        "alpha": {"declared": 1.0, "measured": None},
                        "rho": {"declared": 0.95, "measured": None},
                    }
                },
            },
        },
    )


def test_ir_resolve_marks_record_resolved(initialized: Path, run_op):
    _bridge_and_resolver(run_op)
    run_op("kernel.ir.new", _new())
    envelope = run_op(
        "kernel.ir.resolve",
        {
            "ir_id": "decision-1",
            "resolver_id": "synth-resolver",
            "resolution_text": "We chose option A.",
            "cost_actual": {
                "clock_ms": 250,
                "coin_usd": 0.001,
                "carbon_g": 0.05,
                "model_name": "synth",
                "tokens_in": 100,
                "tokens_out": 200,
            },
        },
    )
    assert envelope["data"]["ir_status"] == "resolved"
    rec = parse_file(initialized / "ir" / "test-scope" / "decision-1.md")
    assert rec.frontmatter["status"] == "resolved"
    assert rec.frontmatter["resolver"] == "synth-resolver"
    assert rec.resolution_text == "We chose option A."


def test_ir_resolve_rejects_already_resolved(initialized: Path, run_op):
    _bridge_and_resolver(run_op)
    run_op("kernel.ir.new", _new())
    payload = {
        "ir_id": "decision-1",
        "resolver_id": "synth-resolver",
        "resolution_text": "x",
        "cost_actual": {"clock_ms": 0, "coin_usd": 0, "carbon_g": 0},
    }
    run_op("kernel.ir.resolve", payload)
    with pytest.raises(KernelError) as e:
        run_op("kernel.ir.resolve", payload)
    assert e.value.code == INVALID_STATE


def test_ir_expand_then_collapse_round_trip(initialized: Path, run_op):
    run_op("kernel.ir.new", _new())
    expanded = run_op("kernel.ir.expand", {"ir_id": "decision-1"})
    assert expanded["data"]["new_path"].endswith("/decision-1/_node.md")
    assert (initialized / expanded["data"]["new_path"]).exists()
    collapsed = run_op("kernel.ir.collapse", {"ir_id": "decision-1"})
    assert collapsed["data"]["new_path"].endswith("/decision-1.md")
    assert (initialized / collapsed["data"]["new_path"]).exists()
    # reindex check should pass.
    assert run_op("kernel.reindex", {"mode": "check"})["data"]["drift_detected"] is False


def test_ir_collapse_refuses_non_empty(initialized: Path, run_op):
    run_op("kernel.ir.new", _new())
    run_op("kernel.ir.expand", {"ir_id": "decision-1"})
    run_op(
        "kernel.ir.new",
        _new(slug="child-1", parent_id="decision-1", intention_text="A child."),
    )
    with pytest.raises(KernelError) as e:
        run_op("kernel.ir.collapse", {"ir_id": "decision-1"})
    assert e.value.code == INVALID_STATE


def test_ir_supersede_creates_new_record(initialized: Path, run_op):
    run_op("kernel.ir.new", _new())
    envelope = run_op(
        "kernel.ir.supersede",
        {
            "old_ir_id": "decision-1",
            "new_intention_text": "Revisit option A.",
            "authored_by": "test-author",
            "reason": "Constraints changed.",
        },
    )
    new_id = envelope["data"]["new_ir_id"]
    assert new_id.startswith("decision-1.s")
    old = parse_file(initialized / "ir" / "test-scope" / "decision-1.md")
    assert old.frontmatter["status"] == "superseded"
    assert old.frontmatter["superseded_by"] == new_id


def test_ir_deps_walks_forward(initialized: Path, run_op):
    run_op("kernel.ir.new", _new(slug="a"))
    run_op("kernel.ir.new", _new(slug="b", depends_on=["a"]))
    run_op("kernel.ir.new", _new(slug="c", depends_on=["b"]))
    envelope = run_op("kernel.ir.deps", {"ir_id": "c", "direction": "forward", "max_depth": 5})
    ids = [n["ir_id"] for n in envelope["data"]["graph"]]
    assert "c" in ids and "b" in ids and "a" in ids


def test_ir_deps_404(initialized: Path, run_op):
    with pytest.raises(KernelError) as e:
        run_op("kernel.ir.deps", {"ir_id": "ghost"})
    assert e.value.code == NOT_FOUND


def test_ir_promote_tier3_event_to_tier1(initialized: Path, run_op):
    """Promote the bootstrap operation event into a tier 1 (I, R)."""
    # The bootstrap operation event already exists.
    init_event = next(
        (initialized / ".8os" / "events").rglob("*.jsonl")
    ).read_text().strip().splitlines()[0]
    import json as _json

    event_id = _json.loads(init_event)["event_id"]
    envelope = run_op(
        "kernel.ir.promote",
        {
            "event_id": event_id,
            "to_tier": 1,
            "target_scope": "test-scope",
            "target_slug": "promoted-event",
            "authored_by": "test-author",
            "authority_level": "convention",
        },
    )
    assert envelope["data"]["new_ir_id"] == "promoted-event"
    assert (initialized / envelope["data"]["new_path"]).exists()
