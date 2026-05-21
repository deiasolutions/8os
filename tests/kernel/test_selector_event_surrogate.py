"""Tests for kernel.selector.select and kernel.event.get."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eightos.errors import NOT_FOUND, KernelError


def _bridge_and_two_resolvers(run_op):
    """Author a synthetic bridge and two resolvers with different sigma/coin
    profiles as v0.2 kernel-configuration (I, R)s. Used by selector tests to
    exercise fitness ranking.
    """
    run_op(
        "kernel.ir.new",
        {
            "scope_id": "_kernel",
            "slug": "synth",
            "tier": 1,
            "intention_text": "Synthetic test bridge.",
            "projection_types": ["_kernel.bridge"],
            "authority_level": "hard",
            "authored_by": "test-author",
            "frontmatter_extensions": {
                "bridge_id": "synth",
                "display_name": "Synthetic Bridge",
                "bridge_type": "other",
                "requires_authorization": False,
                "scope_of_authority": "session",
                "cost_envelope": {
                    "clock_ms_max": 1000,
                    "coin_usd_max": 1.0,
                    "carbon_g_max": 1,
                },
                "endpoint": {"protocol": "local"},
            },
        },
    )
    for rid, sigma, coin in (("cheap", 0.6, 0.001), ("good", 0.95, 0.05)):
        run_op(
            "kernel.ir.new",
            {
                "scope_id": "_kernel",
                "slug": rid,
                "tier": 1,
                "intention_text": f"Resolver {rid!r}.",
                "projection_types": ["_kernel.resolver"],
                "authority_level": "hard",
                "authored_by": "test-author",
                "frontmatter_extensions": {
                    "resolver_id": rid,
                    "display_name": f"Resolver {rid}",
                    "bridge": "synth",
                    "cost": {
                        "clock_ms": 100,
                        "coin_usd": coin,
                        "carbon_g": 0.0,
                        "currency": "USD",
                    },
                    "capability": {
                        "code-gen": {
                            "sigma": {"declared": sigma, "measured": None},
                            "pi": {"declared": 0.5, "measured": None},
                            "alpha": {"declared": 0.5, "measured": None},
                            "rho": {"declared": 0.5, "measured": None},
                        }
                    },
                },
            },
        )


def test_selector_picks_best_resolver(initialized: Path, run_op):
    _bridge_and_two_resolvers(run_op)
    envelope = run_op(
        "kernel.selector.select",
        {"for_ir_id": "_kernel", "domain": "code-gen", "demands": {}},
    )
    # `good` has higher sigma; the trivial fitness function should pick it.
    assert envelope["data"]["selected_resolver_id"] == "good"
    assert (initialized / envelope["data"]["selection_path"]).exists()


def test_selector_filters_by_min_sigma(initialized: Path, run_op):
    _bridge_and_two_resolvers(run_op)
    envelope = run_op(
        "kernel.selector.select",
        {
            "for_ir_id": "_kernel",
            "domain": "code-gen",
            "demands": {"min_sigma": 0.9},
        },
    )
    assert envelope["data"]["selected_resolver_id"] == "good"


def test_selector_returns_null_when_no_candidate(initialized: Path, run_op):
    _bridge_and_two_resolvers(run_op)
    envelope = run_op(
        "kernel.selector.select",
        {
            "for_ir_id": "_kernel",
            "domain": "non-existent-domain",
            "demands": {},
        },
    )
    assert envelope["data"]["selected_resolver_id"] is None


def test_event_get_returns_record_and_projection(initialized: Path, run_op):
    # Use the bootstrap event that already exists.
    line = (
        next((initialized / ".8os" / "events").rglob("*.jsonl"))
        .read_text()
        .strip()
        .splitlines()[0]
    )
    event_id = json.loads(line)["event_id"]
    envelope = run_op("kernel.event.get", {"event_id": event_id})
    data = envelope["data"]
    assert data["event_id"] == event_id
    assert data["event_record"]["event_type"] == "operation"
    assert data["ir_projection"]["tier"] == 3


def test_event_get_404(initialized: Path, run_op):
    with pytest.raises(KernelError) as e:
        run_op("kernel.event.get", {"event_id": "01XXXNOTFOUND00000000000000"})
    assert e.value.code == NOT_FOUND
