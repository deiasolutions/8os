"""Tests for v0.2 kernel-configuration (I, R)s and bridge crossing.

In v0.2, bridges and resolvers are (I, R) records under `ir/_kernel/<category>/`
authored through `kernel.ir.new` with `projection_types: [_kernel.bridge]` or
`[_kernel.resolver]`. The v0.1 ops `kernel.bridge.add` and `kernel.resolver.add`
were removed (spec §4.8). This file exercises bridge/resolver authoring via
`ir.new` and the surviving `cross`, `authorize`, and `gatekeeper.check` ops on
top of those records.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eightos.errors import (
    ALREADY_EXISTS,
    AUTHORIZATION_REQUIRED,
    BRIDGE_UNREACHABLE,
    NOT_FOUND,
    KernelError,
)


def _bridge_extensions(**over):
    base = {
        "bridge_id": "anthropic-api",
        "display_name": "Anthropic API",
        "bridge_type": "api",
        "requires_authorization": True,
        "scope_of_authority": "session",
        "cost_envelope": {
            "clock_ms_max": 30000,
            "coin_usd_max": 1.0,
            "carbon_g_max": 100,
        },
        "endpoint": "https://api.anthropic.com",
    }
    base.update(over)
    return base


def _new_bridge(run_op, **ext_overrides):
    ext = _bridge_extensions(**ext_overrides)
    bid = ext["bridge_id"]
    return run_op(
        "kernel.ir.new",
        {
            "scope_id": "_kernel",
            "slug": bid,
            "tier": 1,
            "intention_text": f"Bridge {bid!r} declaration",
            "projection_types": ["_kernel.bridge"],
            "authority_level": "hard",
            "authored_by": "test-author",
            "frontmatter_extensions": ext,
        },
    )


def _resolver_extensions(**over):
    base = {
        "resolver_id": "claude-sonnet-4-6",
        "display_name": "Claude Sonnet 4.6",
        "bridge": "anthropic-api",
        "cost": {
            "clock_ms": 800,
            "coin_usd": 0.003,
            "carbon_g": 0.5,
            "currency": "USD",
        },
        "capability": {
            "code-gen": {
                "sigma": {"declared": 0.85, "measured": None},
                "pi": {"declared": 0.7, "measured": None},
                "alpha": {"declared": 0.9, "measured": None},
                "rho": {"declared": 0.95, "measured": None},
            }
        },
    }
    base.update(over)
    return base


def _new_resolver(run_op, **ext_overrides):
    ext = _resolver_extensions(**ext_overrides)
    rid = ext["resolver_id"]
    return run_op(
        "kernel.ir.new",
        {
            "scope_id": "_kernel",
            "slug": rid,
            "tier": 1,
            "intention_text": f"Resolver {rid!r} declaration",
            "projection_types": ["_kernel.resolver"],
            "authority_level": "hard",
            "authored_by": "test-author",
            "frontmatter_extensions": ext,
        },
    )


def test_bridge_ir_new_writes_record_and_indexes(initialized: Path, run_op):
    envelope = _new_bridge(run_op)
    assert envelope["status"] == "ok"
    assert (initialized / "ir" / "_kernel" / "bridge" / "anthropic-api.md").exists()
    from eightos._yaml import load_yaml_file

    bidx = load_yaml_file(initialized / ".8os" / "index" / "bridge-to-resolvers.yml") or {}
    # Bridge appears in bridge-to-resolvers index even with no resolvers yet.
    assert "anthropic-api" in bidx


def test_bridge_ir_new_rejects_duplicate(initialized: Path, run_op):
    _new_bridge(run_op)
    with pytest.raises(KernelError) as e:
        _new_bridge(run_op)
    assert e.value.code == ALREADY_EXISTS


def test_resolver_ir_new_links_bridge(initialized: Path, run_op):
    _new_bridge(run_op)
    envelope = _new_resolver(run_op)
    assert envelope["status"] == "ok"
    from eightos._yaml import load_yaml_file

    bidx = load_yaml_file(initialized / ".8os" / "index" / "bridge-to-resolvers.yml") or {}
    assert "claude-sonnet-4-6" in bidx.get("anthropic-api", [])


def test_bridge_cross_404_on_unknown_bridge(initialized: Path, run_op):
    # v0.2: kernel.ir.new is generic and does not cross-validate references
    # between (I, R)s. A resolver may be authored against a non-existent
    # bridge; reference validation surfaces at use-time when bridge.cross is
    # invoked against the missing bridge.
    _new_resolver(run_op, bridge="ghost-bridge")
    with pytest.raises(KernelError) as e:
        run_op(
            "kernel.bridge.cross",
            {
                "bridge_id": "ghost-bridge",
                "resolver_id": "claude-sonnet-4-6",
                "for_ir_id": "_kernel",
                "payload": {"prompt": "hello"},
            },
        )
    assert e.value.code == NOT_FOUND


def test_bridge_cross_requires_authorization(initialized: Path, run_op):
    _new_bridge(run_op)
    _new_resolver(run_op)
    with pytest.raises(KernelError) as e:
        run_op(
            "kernel.bridge.cross",
            {
                "bridge_id": "anthropic-api",
                "resolver_id": "claude-sonnet-4-6",
                "for_ir_id": "_kernel",
                "payload": {"prompt": "hello"},
            },
        )
    assert e.value.code == AUTHORIZATION_REQUIRED


def test_bridge_cross_records_event(initialized: Path, run_op):
    _new_bridge(run_op, requires_authorization=False)
    _new_resolver(run_op)
    envelope = run_op(
        "kernel.bridge.cross",
        {
            "bridge_id": "anthropic-api",
            "resolver_id": "claude-sonnet-4-6",
            "for_ir_id": "_kernel",
            "payload": {"prompt": "hello"},
        },
    )
    assert envelope["data"]["raw_payload_ref"] is not None
    assert envelope["event_id"]


def test_bridge_cross_quarantined(initialized: Path, run_op):
    # Patch 4: bridge_status is declared on _kernel.bridge as optional frontmatter.
    # Namespaced to avoid collision with the base 8OS `status` field.
    _new_bridge(run_op, requires_authorization=False, bridge_status="quarantined")
    _new_resolver(run_op)
    with pytest.raises(KernelError) as e:
        run_op(
            "kernel.bridge.cross",
            {
                "bridge_id": "anthropic-api",
                "resolver_id": "claude-sonnet-4-6",
                "for_ir_id": "_kernel",
                "payload": None,
            },
        )
    assert e.value.code == BRIDGE_UNREACHABLE


def test_authorize_creates_tier2_record(initialized: Path, run_op):
    _new_bridge(run_op)
    envelope = run_op(
        "kernel.authorize",
        {
            "bridge_id": "anthropic-api",
            "for_ir_id": "_kernel",
            "scope_of_authority": "single",
            "valid_through": None,
            "cost_ceiling": {"coin_usd": 1.0, "carbon_g": None, "clock_ms": None},
            "authored_by": "test-author",
        },
    )
    assert envelope["status"] == "ok"
    p = initialized / envelope["data"]["path"]
    assert p.exists()
    assert "ir/_ops/authorization/" in p.as_posix()


def test_gatekeeper_check_with_valid_authorization(initialized: Path, run_op):
    _new_bridge(run_op)
    _new_resolver(run_op)
    auth = run_op(
        "kernel.authorize",
        {
            "bridge_id": "anthropic-api",
            "for_ir_id": "_kernel",
            "scope_of_authority": "session",
            "authored_by": "test-author",
        },
    )
    auth_id = auth["data"]["authorization_ir_id"]
    envelope = run_op(
        "kernel.gatekeeper.check",
        {
            "bridge_id": "anthropic-api",
            "resolver_id": "claude-sonnet-4-6",
            "for_ir_id": "_kernel",
            "authorization_id": auth_id,
        },
    )
    assert envelope["data"]["permitted"] is True


def test_gatekeeper_check_denies_without_authorization(initialized: Path, run_op):
    _new_bridge(run_op)
    _new_resolver(run_op)
    envelope = run_op(
        "kernel.gatekeeper.check",
        {
            "bridge_id": "anthropic-api",
            "resolver_id": "claude-sonnet-4-6",
            "for_ir_id": "_kernel",
        },
    )
    assert envelope["data"]["permitted"] is False
