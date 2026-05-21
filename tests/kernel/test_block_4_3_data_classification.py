"""Tests for Block 4.3 — `data_classification` lifted to base frontmatter.

Per 8OS-BLOCK-1-SPEC v1.1 §4.2, `data_classification` becomes optional base
frontmatter. Inheritance follows the `domain` pattern from Block 4.1:
record-level overrides scope `data_classification_default`; absent at both
levels means null. The kernel stores the value as an opaque string;
classification-based policy gating is downstream work that plugs into the
already-marked placeholder in `kernel.ir.new` / `kernel.ir.resolve`.

The 12 test cases enumerated in the Block 4.3 prompt:

1. Authoring with `data_classification` — accepted, preserved on disk.
2. Authoring without `data_classification` — accepted, resolves to null
   when no scope default.
3. Scope-default inheritance via `data_classification_default`.
4. Record-level overrides scope default.
5. Reindex --check accepts records lacking the field.
6. Reindex --check accepts records with `data_classification: null`.
7. Reindex --check rejects empty-string `data_classification`.
8. Reindex --check rejects non-string `data_classification`.
9. Backward compat — pre-Block-4.3 records (no field) keep working.
10. `data_classification` preserved on `kernel.ir.resolve`.
11. `data_classification` preserved through `kernel.ir.cancel`.
12. Upgrade-mode body refresh adds `data_classification_default` to
    `_kernel.scope` optional_frontmatter.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eightos import __version__ as KERNEL_VERSION
from eightos._frontmatter import parse_file, serialize
from eightos._yaml import load_yaml_file
from eightos.calibration import resolve_data_classification
from eightos.errors import SCHEMA_INVALID, KernelError


# ---------------------------------------------------------------------------
# §4.2 — data_classification on records
# ---------------------------------------------------------------------------


def test_authoring_with_data_classification_accepts_and_preserves(initialized: Path, run_op):
    repo = initialized
    env = run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "with-classification",
        "tier": 1,
        "intention_text": "Carries classified data.",
        "authority_level": "convention",
        "authored_by": "test-author",
        "data_classification": "pii-tokenized-fbb-v1",
    })
    rec = parse_file(repo / env["data"]["path"])
    assert rec.frontmatter["data_classification"] == "pii-tokenized-fbb-v1"


def test_authoring_without_data_classification_resolves_null(initialized: Path, run_op):
    repo = initialized
    env = run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "no-classification",
        "tier": 1,
        "intention_text": "No classification.",
        "authority_level": "convention",
        "authored_by": "test-author",
    })
    rec = parse_file(repo / env["data"]["path"])
    assert "data_classification" not in rec.frontmatter
    scope_rec = parse_file(repo / "ir" / "_kernel" / "scope" / "test-scope.md")
    assert resolve_data_classification(rec.frontmatter, scope_rec.frontmatter) is None


def test_scope_default_inheritance(initialized: Path, run_op):
    repo = initialized
    run_op("kernel.ir.new", {
        "scope_id": "_kernel",
        "slug": "classified-scope",
        "tier": 1,
        "intention_text": "A scope with a classification default.",
        "projection_types": ["_kernel.scope"],
        "authority_level": "hard",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "frontmatter_extensions": {
            "parent_scope": "test-scope",
            "authority_defaults": {"hard": [], "convention": [], "uncalibrated": []},
            "visibility_defaults": ["classified-scope"],
            "data_classification_default": "pii-free",
        },
    })
    run_op("kernel.ir.new", {
        "scope_id": "classified-scope",
        "slug": "inheriting",
        "tier": 1,
        "intention_text": "Inherits the scope's classification default.",
        "authority_level": "convention",
        "authored_by": "test-author",
    })
    intention = parse_file(repo / "ir" / "classified-scope" / "inheriting.md")
    scope_rec = parse_file(repo / "ir" / "_kernel" / "scope" / "classified-scope.md")
    assert resolve_data_classification(
        intention.frontmatter, scope_rec.frontmatter
    ) == "pii-free"


def test_record_classification_overrides_scope_default(initialized: Path, run_op):
    repo = initialized
    run_op("kernel.ir.new", {
        "scope_id": "_kernel",
        "slug": "override-classification-scope",
        "tier": 1,
        "intention_text": "A scope with one default.",
        "projection_types": ["_kernel.scope"],
        "authority_level": "hard",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "frontmatter_extensions": {
            "parent_scope": "test-scope",
            "authority_defaults": {"hard": [], "convention": [], "uncalibrated": []},
            "visibility_defaults": ["override-classification-scope"],
            "data_classification_default": "pii-free",
        },
    })
    run_op("kernel.ir.new", {
        "scope_id": "override-classification-scope",
        "slug": "overriding",
        "tier": 1,
        "intention_text": "Has its own classification.",
        "authority_level": "convention",
        "authored_by": "test-author",
        "data_classification": "confidential-internal",
    })
    intention = parse_file(
        repo / "ir" / "override-classification-scope" / "overriding.md"
    )
    scope_rec = parse_file(
        repo / "ir" / "_kernel" / "scope" / "override-classification-scope.md"
    )
    assert resolve_data_classification(
        intention.frontmatter, scope_rec.frontmatter
    ) == "confidential-internal"


# ---------------------------------------------------------------------------
# §4.2 — reindex --check shape validation
# ---------------------------------------------------------------------------


def test_reindex_check_accepts_records_without_data_classification(initialized: Path, run_op):
    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "no-classification-check",
        "tier": 1,
        "intention_text": "No classification.",
        "authority_level": "convention",
        "authored_by": "test-author",
    })
    run_op("kernel.reindex", {"mode": "check"})  # should not raise


def test_reindex_check_accepts_records_with_null_data_classification(initialized: Path, run_op):
    repo = initialized
    rec_path = repo / "ir" / "test-scope" / "explicit-null.md"
    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "explicit-null",
        "tier": 1,
        "intention_text": "Explicit null classification.",
        "authority_level": "convention",
        "authored_by": "test-author",
    })
    rec = parse_file(rec_path)
    rec.frontmatter["data_classification"] = None
    rec_path.write_text(serialize(rec))
    run_op("kernel.reindex", {"mode": "rebuild"})
    run_op("kernel.reindex", {"mode": "check"})  # should not raise


def test_reindex_check_rejects_empty_string_data_classification(initialized: Path, run_op):
    repo = initialized
    rec_path = repo / "ir" / "test-scope" / "empty-classification.md"
    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "empty-classification",
        "tier": 1,
        "intention_text": "Will be corrupted with empty string.",
        "authority_level": "convention",
        "authored_by": "test-author",
    })
    rec = parse_file(rec_path)
    rec.frontmatter["data_classification"] = ""
    rec_path.write_text(serialize(rec))
    run_op("kernel.reindex", {"mode": "rebuild"})
    with pytest.raises(KernelError) as exc:
        run_op("kernel.reindex", {"mode": "check"})
    assert exc.value.code == SCHEMA_INVALID
    assert "ir/test-scope/empty-classification.md" in str(
        exc.value.extra_context.get("records_with_invalid_data_classification")
    )


def test_reindex_check_rejects_non_string_data_classification(initialized: Path, run_op):
    repo = initialized
    rec_path = repo / "ir" / "test-scope" / "non-string-classification.md"
    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "non-string-classification",
        "tier": 1,
        "intention_text": "Will be corrupted with non-string.",
        "authority_level": "convention",
        "authored_by": "test-author",
    })
    rec = parse_file(rec_path)
    rec.frontmatter["data_classification"] = ["pii-free"]  # list, not string
    rec_path.write_text(serialize(rec))
    run_op("kernel.reindex", {"mode": "rebuild"})
    with pytest.raises(KernelError) as exc:
        run_op("kernel.reindex", {"mode": "check"})
    assert exc.value.code == SCHEMA_INVALID


# ---------------------------------------------------------------------------
# Backward compat + preservation across ops
# ---------------------------------------------------------------------------


def test_backward_compat_with_pre_block_4_3_record(initialized: Path, run_op):
    """A record authored under v1.1.0-dev.2 (no `data_classification` field)
    loads, indexes, and dispatches cleanly."""
    repo = initialized
    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "legacy-shape",
        "tier": 1,
        "intention_text": "Pre-Block-4.3 shape.",
        "authority_level": "convention",
        "authored_by": "test-author",
    })
    rec = parse_file(repo / "ir" / "test-scope" / "legacy-shape.md")
    assert "data_classification" not in rec.frontmatter

    env = run_op("kernel.ir.list", {
        "scope_id": "test-scope",
        "status": ["open"],
    })
    ids = {r["ir_id"] for r in env["data"]["results"]}
    assert "legacy-shape" in ids


def test_data_classification_preserved_on_resolve(initialized: Path, run_op):
    repo = initialized
    run_op("kernel.ir.new", {
        "scope_id": "_kernel",
        "slug": "test-resolver",
        "tier": 1,
        "intention_text": "A test resolver.",
        "projection_types": ["_kernel.resolver"],
        "authority_level": "hard",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "frontmatter_extensions": {
            "resolver_id": "test-resolver",
            "display_name": "test-resolver",
            "bridge": None,
            "cost": {"clock_ms": 1, "coin_usd": 0, "carbon_g": 0},
            "capability": {
                "general": {
                    "sigma": {"declared": 0.9, "measured": None},
                    "pi": {"declared": 0.9, "measured": None},
                    "alpha": {"declared": 0.9, "measured": None},
                    "rho": {"declared": 0.9, "measured": None},
                }
            },
        },
    })
    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "to-resolve",
        "tier": 1,
        "intention_text": "Has classification; will be resolved.",
        "authority_level": "convention",
        "authored_by": "test-author",
        "data_classification": "pii-tokenized-fbb-v1",
    })
    run_op("kernel.ir.resolve", {
        "ir_id": "to-resolve",
        "resolver_id": "test-resolver",
        "resolution_text": "Done.",
        "cost_actual": {"clock_ms": 1, "coin_usd": 0, "carbon_g": 0},
    })
    rec = parse_file(repo / "ir" / "test-scope" / "to-resolve.md")
    assert rec.frontmatter["status"] == "resolved"
    assert rec.frontmatter["data_classification"] == "pii-tokenized-fbb-v1"


def test_data_classification_preserved_through_cancel(initialized: Path, run_op):
    repo = initialized
    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "to-cancel-classified",
        "tier": 1,
        "intention_text": "Has classification; will be cancelled.",
        "authority_level": "convention",
        "authored_by": "test-author",
        "data_classification": "confidential-internal",
    })
    run_op("kernel.ir.cancel", {
        "ir_id": "to-cancel-classified",
        "cancelled_by": "test-author",
        "authored_via": "kernel.self",
    })
    rec = parse_file(repo / "ir" / "test-scope" / "to-cancel-classified.md")
    assert rec.frontmatter["status"] == "cancelled"
    # The cancel op's frontmatter mutation must not strip pre-existing fields.
    assert rec.frontmatter["data_classification"] == "confidential-internal"


# ---------------------------------------------------------------------------
# Upgrade-mode body refresh
# ---------------------------------------------------------------------------


def test_upgrade_from_dev2_refreshes_scope_body(repo: Path, run_op):
    """Block 4.3 added `data_classification_default` to `_kernel.scope`'s
    vendored body. Simulating a v1.1.0-dev.2 pre-upgrade state (body
    without the field) and re-running init at current binary version
    refreshes the body. (Test name + assertions made KERNEL_VERSION-
    agnostic per Block 4.3 F1 / Block 4.4 finding.)"""
    run_op("kernel.init", {
        "project_name": "test-project",
        "primary_scope_id": "test-scope",
        "primary_operator_id": "test-author",
        "kernel_version": KERNEL_VERSION,
    })
    # Rewind .8os/version and strip data_classification_default from the
    # on-disk scope body to simulate the v1.1.0-dev.2 pre-upgrade state.
    (repo / ".8os" / "version").write_text("1.1.0-dev.2\n")
    body_path = repo / ".8os" / "projections" / "_kernel" / "_kernel.scope.yml"
    body_doc = load_yaml_file(body_path)
    body_doc["optional_frontmatter"] = [
        f for f in body_doc["optional_frontmatter"]
        if f.get("name") != "data_classification_default"
    ]
    import yaml
    body_path.write_text(yaml.safe_dump(body_doc, sort_keys=True))

    env = run_op("kernel.init", {
        "project_name": "test-project",
        "primary_scope_id": "test-scope",
        "primary_operator_id": "test-author",
        "kernel_version": KERNEL_VERSION,
    })
    assert env["data"]["mode"] == "upgrade"
    assert env["data"]["previous_version"] == "1.1.0-dev.2"
    assert env["data"]["kernel_version"] == KERNEL_VERSION
    assert "_kernel.scope" in env["data"]["refreshed"]["vendored_projection_bodies"]

    # Verify the refreshed body now contains the field.
    refreshed = load_yaml_file(body_path)
    optional_names = {f["name"] for f in refreshed["optional_frontmatter"]}
    assert "data_classification_default" in optional_names

    # Idempotent: running init again at the matched version is a noop.
    env_again = run_op("kernel.init", {
        "project_name": "test-project",
        "primary_scope_id": "test-scope",
        "primary_operator_id": "test-author",
        "kernel_version": KERNEL_VERSION,
    })
    assert env_again["data"]["mode"] == "noop"
