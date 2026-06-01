"""Tests for Block 4.1 — `domain` lifted to base frontmatter.

Closes OPEN-Q-019. Per 8OS-BLOCK-1-SPEC v1.1 §4.3, `domain` becomes optional
base frontmatter. Inheritance follows the `stakes` pattern: record-level
overrides scope `domain_default`; absent at both levels means null.

The nine test cases enumerated in the Block 4.1 prompt:

1. Authoring with `domain` — accepted, preserved on disk.
2. Authoring without `domain` — accepted, resolves null when no scope default.
3. Scope-default inheritance — record without domain inherits scope's default.
4. Record-level overrides scope default — explicit record domain wins.
5. `reindex --check` accepts records without `domain` — optional field.
6. `reindex --check` rejects empty-string `domain` — schema invariant.
7. Calibration policy `applies_to_domain` matches resolved domain.
8. Backward compat — pre-Block-4.1 records (no `domain`) keep working.
9. Upgrade-mode body refresh adds `domain_default` to `_kernel.scope`.

Note: per discipline, this file lives in `tests/kernel/` alongside other
schema-amendment tests (mirrors `test_v1_0_1_partial.py`'s home), even though
the Block 4.1 prompt nominally specified `tests/`. Logged in block report.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eightos import __version__ as KERNEL_VERSION
from eightos._frontmatter import IRRecord, parse_file, serialize
from eightos._yaml import dump_yaml, load_yaml_file
from eightos.calibration import find_active_policy, resolve_domain
from eightos.errors import SCHEMA_INVALID, KernelError


# ---------------------------------------------------------------------------
# §4.3 — domain on records
# ---------------------------------------------------------------------------


def test_authoring_with_domain_accepts_and_preserves(initialized: Path, run_op):
    """A record authored with `domain` is accepted; the field is written to
    frontmatter and survives a round-trip through parse."""
    repo = initialized
    env = run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "with-domain",
        "tier": 1,
        "intention_text": "Has a domain.",
        "authority_level": "convention",
        "authored_by": "test-author",
        "domain": "billing/invoices",
    })
    rec = parse_file(repo / env["data"]["path"])
    assert rec.frontmatter["domain"] == "billing/invoices"


def test_authoring_without_domain_resolves_null(initialized: Path, run_op):
    """A record authored without `domain` (and no scope default) resolves to null."""
    repo = initialized
    env = run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "no-domain",
        "tier": 1,
        "intention_text": "No domain.",
        "authority_level": "convention",
        "authored_by": "test-author",
    })
    rec = parse_file(repo / env["data"]["path"])
    assert "domain" not in rec.frontmatter
    # The default scope record has no `domain_default`; resolve to null.
    scope_rec = parse_file(repo / "ir" / "_kernel" / "scope" / "test-scope.md")
    assert resolve_domain(rec.frontmatter, scope_rec.frontmatter) is None


def test_scope_default_inheritance(initialized: Path, run_op):
    """When a scope record carries `domain_default`, intentions in that scope
    without a record-level `domain` resolve to the scope default."""
    repo = initialized
    # Author a fresh hard-authority scope with a domain_default. The init
    # already wrote the `_kernel` and `test-scope` declarations; we add a
    # sibling scope with the default we want to test.
    run_op("kernel.ir.new", {
        "scope_id": "_kernel",
        "slug": "domain-scope",
        "tier": 1,
        "intention_text": "A scope with a domain default.",
        "projection_types": ["_kernel.scope"],
        "authority_level": "hard",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "frontmatter_extensions": {
            "parent_scope": "test-scope",
            "authority_defaults": {"hard": [], "convention": [], "uncalibrated": []},
            "visibility_defaults": ["domain-scope"],
            "domain_default": "kernel-development/test-result",
        },
    })
    # Author an intention in that scope without a record-level domain.
    run_op("kernel.ir.new", {
        "scope_id": "domain-scope",
        "slug": "inheriting",
        "tier": 1,
        "intention_text": "Inherits the scope default.",
        "authority_level": "convention",
        "authored_by": "test-author",
    })
    intention = parse_file(repo / "ir" / "domain-scope" / "inheriting.md")
    scope_rec = parse_file(repo / "ir" / "_kernel" / "scope" / "domain-scope.md")
    assert resolve_domain(intention.frontmatter, scope_rec.frontmatter) == "kernel-development/test-result"


def test_record_domain_overrides_scope_default(initialized: Path, run_op):
    """A record's own `domain` ignores the scope's `domain_default`."""
    repo = initialized
    run_op("kernel.ir.new", {
        "scope_id": "_kernel",
        "slug": "override-scope",
        "tier": 1,
        "intention_text": "A scope with one default.",
        "projection_types": ["_kernel.scope"],
        "authority_level": "hard",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "frontmatter_extensions": {
            "parent_scope": "test-scope",
            "authority_defaults": {"hard": [], "convention": [], "uncalibrated": []},
            "visibility_defaults": ["override-scope"],
            "domain_default": "scope-default-domain",
        },
    })
    run_op("kernel.ir.new", {
        "scope_id": "override-scope",
        "slug": "overriding",
        "tier": 1,
        "intention_text": "Has its own domain.",
        "authority_level": "convention",
        "authored_by": "test-author",
        "domain": "record-domain",
    })
    intention = parse_file(repo / "ir" / "override-scope" / "overriding.md")
    scope_rec = parse_file(repo / "ir" / "_kernel" / "scope" / "override-scope.md")
    assert resolve_domain(intention.frontmatter, scope_rec.frontmatter) == "record-domain"


# ---------------------------------------------------------------------------
# §4.3 — reindex --check shape validation
# ---------------------------------------------------------------------------


def test_reindex_check_accepts_record_without_domain(initialized: Path, run_op):
    """Records lacking `domain` pass reindex --check."""
    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "no-domain-record",
        "tier": 1,
        "intention_text": "No domain field.",
        "authority_level": "convention",
        "authored_by": "test-author",
    })
    # Should not raise.
    env = run_op("kernel.reindex", {"mode": "check"})
    assert env["data"]["drift_detected"] is False


def test_reindex_check_rejects_empty_string_domain(initialized: Path, run_op):
    """A record with `domain: ""` rejects as SCHEMA_INVALID."""
    repo = initialized
    bad_path = repo / "ir" / "test-scope" / "empty-domain.md"
    rec = IRRecord(
        frontmatter={
            "id": "empty-domain",
            "kind": "ir-node",
            "tier": 1,
            "projection_types": [],
            "collapsed_summary": "Empty-string domain.",
            "expanded_into": None,
            "parent": None,
            "scope": "test-scope",
            "depends_on": [],
            "visible_to": ["test-scope"],
            "resolved_at": None,
            "valid_through": None,
            "revalidate_trigger": None,
            "status": "open",
            "resolver": None,
            "resolution_event": None,
            "authored_by": "test-author",
            "authored_on": "2026-04-28T00:00:00Z",
            "authority_level": "convention",
            "authored_via": "outside",
            "supersedes": None,
            "superseded_by": None,
            "surrogate_of": None,
            "domain": "",
        },
        intention_text="Hand-authored with empty-string domain.",
        resolution_text=None,
    )
    bad_path.write_text(serialize(rec), encoding="utf-8")
    run_op("kernel.reindex", {"mode": "rebuild"})
    with pytest.raises(KernelError) as exc:
        run_op("kernel.reindex", {"mode": "check"})
    assert exc.value.code == SCHEMA_INVALID
    assert "ir/test-scope/empty-domain.md" in str(
        exc.value.extra_context.get("records_with_invalid_domain")
    )


# ---------------------------------------------------------------------------
# §4.3 — calibration policy matching by domain
# ---------------------------------------------------------------------------


def _register_resolver(run_op, resolver_id: str, domain: str = "general") -> None:
    run_op("kernel.ir.new", {
        "scope_id": "_kernel",
        "slug": resolver_id,
        "tier": 1,
        "intention_text": f"Resolver {resolver_id}.",
        "projection_types": ["_kernel.resolver"],
        "authority_level": "hard",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "frontmatter_extensions": {
            "resolver_id": resolver_id,
            "display_name": resolver_id,
            "bridge": None,
            "cost": {"clock_ms": 1, "coin_usd": 0.001, "carbon_g": 0.001, "currency": "USD"},
            "capability": {
                domain: {
                    "sigma": {"declared": 0.9, "measured": None},
                    "pi": {"declared": 0.9, "measured": None},
                    "alpha": {"declared": 0.9, "measured": None},
                    "rho": {"declared": 0.9, "measured": None},
                }
            },
        },
    })


def _author_calibration_policy_for_domain(run_op, slug: str, domain: str) -> None:
    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": slug,
        "tier": 1,
        "intention_text": f"Calibration policy for domain {domain!r}.",
        "projection_types": ["_kernel.calibration-policy"],
        "authority_level": "hard",
        "authored_by": "test-author",
        "frontmatter_extensions": {
            "policy_id": slug,
            "applies_to_scope": "test-scope",
            "applies_to_domain": domain,
            "predictor": "predictor-llm",
            "calibration_signal": "proxy",
            "proxy_specification": {"kind": "peer-agreement", "params": {}},
            "holdout_rate": 0.0,
            "recalibration_trigger": {"kind": "count", "params": {"n": 50}},
        },
    })


def test_calibration_policy_matches_by_resolved_domain(initialized: Path, run_op):
    """A policy with `applies_to_domain: X` matches a record whose resolved
    domain (declared or inherited) is X; mismatched-domain and null-domain
    records do not match."""
    repo = initialized
    _register_resolver(run_op, "predictor-llm")
    _author_calibration_policy_for_domain(run_op, "billing-policy", "billing/invoices")

    # Match: record-level domain equal to applies_to_domain.
    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "matching-record",
        "tier": 1,
        "intention_text": "Matches the policy.",
        "authority_level": "convention",
        "authored_by": "test-author",
        "domain": "billing/invoices",
    })
    matching = parse_file(repo / "ir" / "test-scope" / "matching-record.md").frontmatter
    policy_fm = find_active_policy(repo, matching)
    assert policy_fm is not None
    assert policy_fm.get("policy_id") == "billing-policy"

    # No match: record-level domain different.
    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "wrong-domain-record",
        "tier": 1,
        "intention_text": "Wrong domain.",
        "authority_level": "convention",
        "authored_by": "test-author",
        "domain": "shipping/labels",
    })
    wrong = parse_file(repo / "ir" / "test-scope" / "wrong-domain-record.md").frontmatter
    assert find_active_policy(repo, wrong) is None

    # No match: record-level domain absent and scope has no default.
    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "null-domain-record",
        "tier": 1,
        "intention_text": "Null domain.",
        "authority_level": "convention",
        "authored_by": "test-author",
    })
    null_dom = parse_file(repo / "ir" / "test-scope" / "null-domain-record.md").frontmatter
    assert find_active_policy(repo, null_dom) is None


# ---------------------------------------------------------------------------
# §4.3 — backward compat
# ---------------------------------------------------------------------------


def test_backward_compat_pre_block_4_1_record(initialized: Path, run_op):
    """A record authored under the v1.0.1-partial schema (no `domain` field)
    loads correctly, indexes correctly, and the resolver-selection path keeps
    working — i.e., the absence of `domain` is the explicit "null domain"
    signal, not a schema violation."""
    repo = initialized

    # Hand-author a v1.0.1-partial-shaped intention (no `domain`).
    legacy_path = repo / "ir" / "test-scope" / "legacy-record.md"
    legacy_rec = IRRecord(
        frontmatter={
            "id": "legacy-record",
            "kind": "ir-node",
            "tier": 1,
            "projection_types": [],
            "collapsed_summary": "Legacy v1.0.1-partial record.",
            "expanded_into": None,
            "parent": None,
            "scope": "test-scope",
            "depends_on": [],
            "visible_to": ["test-scope"],
            "resolved_at": None,
            "valid_through": None,
            "revalidate_trigger": None,
            "status": "open",
            "resolver": None,
            "resolution_event": None,
            "authored_by": "test-author",
            "authored_on": "2026-04-27T00:00:00Z",
            "authority_level": "convention",
            "authored_via": "outside",
            "supersedes": None,
            "superseded_by": None,
            "surrogate_of": None,
        },
        intention_text="Legacy intention with no domain field.",
        resolution_text=None,
    )
    legacy_path.write_text(serialize(legacy_rec), encoding="utf-8")
    # Reindex picks it up cleanly.
    run_op("kernel.reindex", {"mode": "rebuild"})
    # Reindex --check passes (no domain field is fine).
    env = run_op("kernel.reindex", {"mode": "check"})
    assert env["data"]["drift_detected"] is False
    # Selector dispatch works on a domain-free record.
    _register_resolver(run_op, "general-resolver", domain="general")
    sel_env = run_op("kernel.selector.select", {
        "for_ir_id": "legacy-record",
        "domain": "general",
        "demands": {"min_sigma": 0.5, "min_pi": 0.5, "min_alpha": 0.5, "min_rho": 0.5},
    })
    assert sel_env["data"]["selected_resolver_id"] == "general-resolver"


# ---------------------------------------------------------------------------
# §4.8 — upgrade-mode body refresh (per Amendment 3 discipline)
# ---------------------------------------------------------------------------


def test_v101partial_to_v110dev1_upgrade_refreshes_domain_default_field(
    initialized: Path, run_op
):
    """Simulate a v1.0.1-partial repo: rewrite the `_kernel.scope` body
    without `domain_default` and bump .8os/version to 1.0.1-partial. Init
    upgrade-mode must refresh the body, folding `domain_default` back in.
    Idempotent: a second init at v1.1.0-dev.1 is a noop."""
    repo = initialized
    body_path = repo / ".8os" / "projections" / "_kernel" / "_kernel.scope.yml"
    body = load_yaml_file(body_path) or {}
    optional = body.get("optional_frontmatter") or []
    body["optional_frontmatter"] = [
        f for f in optional if f.get("name") != "domain_default"
    ]
    body_path.write_text(dump_yaml(body), encoding="utf-8")
    (repo / ".8os" / "version").write_text("1.0.1-partial\n", encoding="utf-8")
    run_op("kernel.reindex", {"mode": "rebuild"})

    env = run_op("kernel.init", {
        "project_name": "test-project",
        "primary_scope_id": "test-scope",
        "primary_operator_id": "test-author",
        "kernel_version": KERNEL_VERSION,
    })
    assert env["data"]["mode"] == "upgrade"
    assert env["data"]["previous_version"] == "1.0.1-partial"
    refreshed = env["data"]["refreshed"]["vendored_projection_bodies"]
    assert "_kernel.scope" in refreshed

    # Body now carries domain_default in optional_frontmatter.
    refreshed_body = load_yaml_file(body_path)
    optional_names = {
        f["name"] for f in (refreshed_body.get("optional_frontmatter") or [])
    }
    assert "domain_default" in optional_names

    # Idempotent: second init at the same version is a noop.
    env2 = run_op("kernel.init", {
        "project_name": "test-project",
        "primary_scope_id": "test-scope",
        "primary_operator_id": "test-author",
        "kernel_version": KERNEL_VERSION,
    })
    assert env2["data"]["mode"] == "noop"
