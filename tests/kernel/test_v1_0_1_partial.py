"""Tests for v1.0.1-partial amendments.

Covers:
- Amendment 1: subdirectory discipline (`target_subdirectory:` honored,
  conflict rejection on conflicting projection-declared values).
- Amendment 2: mandatory `authored_via` on `kernel.ir.new`, SDK default
  (`outside`) for non-internal callers, `kernel.reindex --check`
  enforcement, internal ops authoring through `kernel.self`.
- Amendment 3: per-version body seal — v1.0.0 → v1.0.1-partial upgrade
  refreshes vendored bodies.
- Migration: idempotency, relocation correctness, authored_via backfill.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from eightos import __version__ as KERNEL_VERSION
from eightos._frontmatter import IRRecord, parse_file, serialize
from eightos._yaml import dump_yaml, load_yaml_file
from eightos.errors import (
    CONFLICTING_PROJECTION_TARGETS,
    SCHEMA_INVALID,
    KernelError,
)


# ---------------------------------------------------------------------------
# Amendment 1 — subdirectory discipline
# ---------------------------------------------------------------------------


def _register_predictor(run_op) -> None:
    run_op("kernel.ir.new", {
        "scope_id": "_kernel",
        "slug": "predictor-llm",
        "tier": 1,
        "intention_text": "An LLM predictor.",
        "projection_types": ["_kernel.resolver"],
        "authority_level": "hard",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "frontmatter_extensions": {
            "resolver_id": "predictor-llm",
            "display_name": "Predictor LLM",
            "bridge": None,
            "cost": {"clock_ms": 100, "coin_usd": 0.001, "carbon_g": 0.001, "currency": "USD"},
            "capability": {
                "lending": {
                    "sigma": {"declared": 0.85, "measured": None},
                    "pi": {"declared": 0.9, "measured": None},
                    "alpha": {"declared": 0.95, "measured": None},
                    "rho": {"declared": 0.9, "measured": None},
                }
            },
        },
    })


def _author_subject_intention(run_op, slug: str) -> None:
    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": slug,
        "tier": 1,
        "intention_text": f"Subject intention {slug!r}.",
        "depends_on": [],
        "authority_level": "convention",
        "authored_by": "test-author",
    })


def test_prediction_lands_in_predictions_subdirectory(initialized: Path, run_op):
    repo = initialized
    _register_predictor(run_op)
    _author_subject_intention(run_op, "subject-001")
    env = run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "pred-001",
        "tier": 1,
        "intention_text": "Predict subject-001.",
        "projection_types": ["_kernel.prediction"],
        "authority_level": "convention",
        "authored_by": "predictor-llm",
        "frontmatter_extensions": {
            "subject_intention": "subject-001",
            "predicted_resolution": True,
            "probability": 0.8,
            "predictor": "predictor-llm",
        },
    })
    assert env["data"]["path"] == "ir/test-scope/_predictions/pred-001.prediction.md"
    assert (repo / env["data"]["path"]).exists()


def test_calibration_policy_lands_in_calibration_policies_subdirectory(
    initialized: Path, run_op
):
    repo = initialized
    _register_predictor(run_op)
    env = run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "policy-001",
        "tier": 1,
        "intention_text": "Calibration policy.",
        "projection_types": ["_kernel.calibration-policy"],
        "authority_level": "hard",
        "authored_by": "test-author",
        "frontmatter_extensions": {
            "policy_id": "policy-001",
            "applies_to_scope": "test-scope",
            "predictor": "predictor-llm",
            "calibration_signal": "proxy",
            "proxy_specification": {"kind": "peer-agreement", "params": {}},
            "holdout_rate": 0.1,
            "recalibration_trigger": {"kind": "count", "params": {"n": 50}},
        },
    })
    assert env["data"]["path"] == "ir/test-scope/_calibration-policies/policy-001.policy.md"
    assert (repo / env["data"]["path"]).exists()


def test_calibration_policy_proposal_lands_in_proposals_subdirectory(
    initialized: Path, run_op
):
    repo = initialized
    _register_predictor(run_op)
    # author a target policy first
    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "policy-base",
        "tier": 1,
        "intention_text": "Base policy.",
        "projection_types": ["_kernel.calibration-policy"],
        "authority_level": "hard",
        "authored_by": "test-author",
        "frontmatter_extensions": {
            "policy_id": "policy-base",
            "applies_to_scope": "test-scope",
            "predictor": "predictor-llm",
            "calibration_signal": "proxy",
            "proxy_specification": {"kind": "peer-agreement", "params": {}},
            "holdout_rate": 0.2,
            "recalibration_trigger": {"kind": "count", "params": {"n": 100}},
        },
    })
    env = run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "proposal-001",
        "tier": 1,
        "intention_text": "Lower holdout_rate to 0.1.",
        "projection_types": ["_kernel.calibration-policy-proposal"],
        "authority_level": "convention",
        "authored_by": "kernel.calibrator",
        "frontmatter_extensions": {
            "proposal_id": "proposal-001",
            "target_policy": "policy-base",
            "proposed_changes": {"holdout_rate": 0.1},
            "evidence_summary": {"observation_count": 30},
            "proposed_by": "kernel.calibrator",
            "proposed_on": "2026-04-27T12:00:00Z",
            "proposal_status": "pending",
        },
    })
    assert env["data"]["path"] == (
        "ir/test-scope/_calibration-proposals/proposal-001.proposal.md"
    )
    assert (repo / env["data"]["path"]).exists()


def test_conflicting_target_subdirectories_rejected(initialized: Path, run_op):
    """A record carrying multiple projection_types with conflicting
    target_subdirectory: declarations is rejected with
    CONFLICTING_PROJECTION_TARGETS."""
    # Author a project-declared projection that conflicts with prediction.
    body = {
        "projection_id": "test-conflicting-proj",
        "filename_suffix": ".md",
        "target_subdirectory": "_some-other-dir",
        "body_shape": "free",
        "required_frontmatter": [],
        "optional_frontmatter": [],
    }
    fenced = "```yaml\n" + dump_yaml(body).rstrip() + "\n```\n"
    run_op("kernel.ir.new", {
        "scope_id": "_kernel",
        "slug": "test-conflicting-proj",
        "tier": 1,
        "intention_text": "Test conflicting projection.\n\n" + fenced,
        "projection_types": ["_kernel.projection"],
        "authority_level": "hard",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "frontmatter_extensions": {
            "projection_id": "test-conflicting-proj",
            "display_name": "Test Conflicting Projection",
        },
    })
    _register_predictor(run_op)
    _author_subject_intention(run_op, "subject-002")
    with pytest.raises(KernelError) as exc:
        run_op("kernel.ir.new", {
            "scope_id": "test-scope",
            "slug": "pred-conflicting",
            "tier": 1,
            "intention_text": "Conflicting predict.",
            "projection_types": ["_kernel.prediction", "test-conflicting-proj"],
            "authority_level": "convention",
            "authored_by": "predictor-llm",
            "frontmatter_extensions": {
                "subject_intention": "subject-002",
                "predicted_resolution": True,
                "probability": 0.5,
                "predictor": "predictor-llm",
            },
        })
    assert exc.value.code == CONFLICTING_PROJECTION_TARGETS


def test_record_without_target_subdirectory_stays_flat(initialized: Path, run_op):
    """Tier 1 records with projection_types that don't declare
    target_subdirectory remain at ir/<scope>/<slug>.md."""
    env = run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "plain-decision",
        "tier": 1,
        "intention_text": "A plain decision with no projection-declared subdir.",
        "depends_on": [],
        "authority_level": "convention",
        "authored_by": "test-author",
    })
    assert env["data"]["path"] == "ir/test-scope/plain-decision.md"


# ---------------------------------------------------------------------------
# Amendment 2 — mandatory authored_via
# ---------------------------------------------------------------------------


def test_authored_via_default_outside_when_omitted(initialized: Path, run_op):
    """SDK boundary defaults authored_via to 'outside' for callers who
    don't supply it. The handler sees a non-empty value."""
    env = run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "no-bridge-supplied",
        "tier": 1,
        "intention_text": "Author through the SDK without naming a bridge.",
        "depends_on": [],
        "authority_level": "convention",
        "authored_by": "test-author",
    })
    rec = parse_file(initialized / env["data"]["path"])
    assert rec.frontmatter["authored_via"] == "outside"


def test_authored_via_explicit_supplied_value_honored(initialized: Path, run_op):
    """Explicit non-default authored_via is written through unchanged."""
    env = run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "explicit-bridge",
        "tier": 1,
        "intention_text": "Author through a named bridge.",
        "authority_level": "convention",
        "authored_by": "test-author",
        "authored_via": "human-test-author",
    })
    rec = parse_file(initialized / env["data"]["path"])
    assert rec.frontmatter["authored_via"] == "human-test-author"


def test_authored_via_empty_string_rejected(initialized: Path, run_op):
    """Schema requires authored_via with minLength: 1."""
    with pytest.raises(KernelError) as exc:
        run_op("kernel.ir.new", {
            "scope_id": "test-scope",
            "slug": "empty-via",
            "tier": 1,
            "intention_text": "Empty bridge id.",
            "authority_level": "convention",
            "authored_by": "test-author",
            "authored_via": "",
        })
    assert exc.value.code == SCHEMA_INVALID


def test_init_authored_records_use_kernel_self(initialized: Path):
    """Init-authored records (foundational kernel content + bootstrap)
    carry authored_via: kernel.self per the cogito pattern."""
    repo = initialized
    # Bootstrap (I, R)
    bootstrap = parse_file(repo / "ir" / "test-scope" / "000-bootstrap.md")
    assert bootstrap.frontmatter["authored_via"] == "kernel.self"
    # _kernel scope, projection definitions, internal resolvers
    for path in (
        repo / "ir" / "_kernel" / "scope" / "_kernel.md",
        repo / "ir" / "_kernel" / "projection" / "_kernel.prediction.md",
        repo / "ir" / "_kernel" / "resolver" / "kernel.voi.md",
        repo / "ir" / "_kernel" / "bridge" / "kernel.self.md",
    ):
        assert path.exists()
        rec = parse_file(path)
        assert rec.frontmatter["authored_via"] == "kernel.self", (
            f"{path} has authored_via={rec.frontmatter.get('authored_via')!r}"
        )


def test_selector_records_use_kernel_self(initialized: Path, run_op):
    """Selector-authored tier 2 (I, R)s carry authored_via: kernel.self."""
    # Set up a candidate resolver and an intention to select for.
    run_op("kernel.ir.new", {
        "scope_id": "_kernel",
        "slug": "candidate-resolver",
        "tier": 1,
        "intention_text": "A candidate resolver.",
        "projection_types": ["_kernel.resolver"],
        "authority_level": "hard",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "frontmatter_extensions": {
            "resolver_id": "candidate-resolver",
            "display_name": "Candidate Resolver",
            "bridge": None,
            "cost": {"clock_ms": 10, "coin_usd": 0.0, "carbon_g": 0.0, "currency": "USD"},
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
        "slug": "decision-001",
        "tier": 1,
        "intention_text": "Decide something.",
        "depends_on": [],
        "authority_level": "convention",
        "authored_by": "test-author",
    })
    env = run_op("kernel.selector.select", {
        "for_ir_id": "decision-001",
        "domain": "general",
        "demands": {"min_sigma": 0.5, "min_pi": 0.5, "min_alpha": 0.5, "min_rho": 0.5},
    })
    sel_path = initialized / env["data"]["selection_path"]
    rec = parse_file(sel_path)
    assert rec.frontmatter["authored_via"] == "kernel.self"


def test_reindex_check_rejects_record_missing_authored_via(initialized: Path, run_op):
    """If a record lacks authored_via on disk, reindex --check raises
    SCHEMA_INVALID with the path in extra_context."""
    repo = initialized
    # Hand-author a record with authored_via missing.
    bad_path = repo / "ir" / "test-scope" / "missing-via.md"
    rec = IRRecord(
        frontmatter={
            "id": "missing-via",
            "kind": "ir-node",
            "tier": 1,
            "projection_types": [],
            "collapsed_summary": "Missing authored_via.",
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
            # no authored_via
            "supersedes": None,
            "superseded_by": None,
            "surrogate_of": None,
        },
        intention_text="Hand-authored without authored_via.",
        resolution_text=None,
    )
    bad_path.write_text(serialize(rec), encoding="utf-8")
    run_op("kernel.reindex", {"mode": "rebuild"})
    with pytest.raises(KernelError) as exc:
        run_op("kernel.reindex", {"mode": "check"})
    assert exc.value.code == SCHEMA_INVALID
    assert "ir/test-scope/missing-via.md" in str(
        exc.value.extra_context.get("records_missing_authored_via")
    )


# ---------------------------------------------------------------------------
# Amendment 3 — per-version body seal (v1.0.0 → v1.0.1-partial upgrade refresh)
# ---------------------------------------------------------------------------


def test_v100_to_v101partial_upgrade_refreshes_target_subdirectory_fields(
    initialized: Path, run_op
):
    """Simulate a v1.0.0 repo: rewrite the three vendored bodies without
    target_subdirectory and bump .8os/version to 1.0.0. Init upgrade-mode
    must refresh the bodies, folding target_subdirectory back in.
    """
    repo = initialized
    body_dir = repo / ".8os" / "projections" / "_kernel"
    # Strip target_subdirectory from the three bodies + stamp version.
    for ptype in (
        "_kernel.prediction",
        "_kernel.calibration-policy",
        "_kernel.calibration-policy-proposal",
    ):
        path = body_dir / f"{ptype}.yml"
        body = load_yaml_file(path) or {}
        body.pop("target_subdirectory", None)
        path.write_text(dump_yaml(body), encoding="utf-8")
    (repo / ".8os" / "version").write_text("1.0.0\n", encoding="utf-8")
    run_op("kernel.reindex", {"mode": "rebuild"})

    env = run_op("kernel.init", {
        "project_name": "test-project",
        "primary_scope_id": "test-scope",
        "primary_operator_id": "test-author",
        "kernel_version": KERNEL_VERSION,
    })
    assert env["data"]["mode"] == "upgrade"
    assert env["data"]["previous_version"] == "1.0.0"
    refreshed = env["data"]["refreshed"]["vendored_projection_bodies"]
    assert "_kernel.prediction" in refreshed
    assert "_kernel.calibration-policy" in refreshed
    assert "_kernel.calibration-policy-proposal" in refreshed
    # Bodies now carry target_subdirectory.
    pred_body = load_yaml_file(body_dir / "_kernel.prediction.yml")
    assert pred_body["target_subdirectory"] == "_predictions"


# ---------------------------------------------------------------------------
# Migration script — idempotency, relocation, backfill
# ---------------------------------------------------------------------------


def _run_migration(repo: Path) -> dict:
    """Invoke the migration script as a subprocess; return parsed stdout."""
    result = subprocess.run(
        [sys.executable, "scripts/migrate-v1.0-to-v1.0.1-partial.py", "--repo", str(repo)],
        capture_output=True,
        cwd=str(Path(__file__).resolve().parent.parent.parent),
        timeout=30,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.decode(),
        "stderr": result.stderr.decode(),
    }


def _reset_to_v100(repo: Path, run_op) -> None:
    """Take a fresh v1.0.1-partial repo and reverse-engineer it to look
    like a v1.0.0 repo: strip target_subdirectory from vendored bodies,
    null out authored_via on every ir/**/*.md record, write 1.0.0 to
    .8os/version, run reindex --rebuild."""
    body_dir = repo / ".8os" / "projections" / "_kernel"
    for ptype in (
        "_kernel.prediction",
        "_kernel.calibration-policy",
        "_kernel.calibration-policy-proposal",
    ):
        path = body_dir / f"{ptype}.yml"
        body = load_yaml_file(path) or {}
        body.pop("target_subdirectory", None)
        path.write_text(dump_yaml(body), encoding="utf-8")
    for md in (repo / "ir").rglob("*.md"):
        rec = parse_file(md)
        rec.frontmatter["authored_via"] = None
        md.write_text(serialize(rec), encoding="utf-8")
    (repo / ".8os" / "version").write_text("1.0.0\n", encoding="utf-8")
    # Don't run reindex --check (would fail on null authored_via);
    # write_all from `--rebuild` mode is fine.
    from eightos._indexes import write_all as _write_all
    _write_all(repo)


def test_migration_relocates_v1_records_to_subdirectories(initialized: Path, run_op):
    """A v1.0.0-shaped repo with prediction/policy records in flat
    ir/<scope>/ layout gets relocated into the projection-declared
    subdirectories."""
    repo = initialized
    _register_predictor(run_op)
    _author_subject_intention(run_op, "subject-100")
    # Author a prediction (it lands in subdirs because we've already migrated;
    # simulate v1.0.0 by relocating the file back to flat layout afterward).
    env = run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "pred-100",
        "tier": 1,
        "intention_text": "Predict subject-100.",
        "projection_types": ["_kernel.prediction"],
        "authority_level": "convention",
        "authored_by": "predictor-llm",
        "frontmatter_extensions": {
            "subject_intention": "subject-100",
            "predicted_resolution": True,
            "probability": 0.7,
            "predictor": "predictor-llm",
        },
    })
    pred_path = repo / env["data"]["path"]
    assert pred_path.parent.name == "_predictions"

    _reset_to_v100(repo, run_op)
    # Move pred-100 from subdir back to flat.
    flat = repo / "ir" / "test-scope" / pred_path.name
    pred_path.rename(flat)
    if not any(pred_path.parent.iterdir()):
        pred_path.parent.rmdir()

    result = _run_migration(repo)
    assert result["returncode"] == 0, result["stderr"]
    relocated = repo / "ir" / "test-scope" / "_predictions" / "pred-100.prediction.md"
    assert relocated.exists()
    assert not flat.exists()
    assert (repo / ".8os" / "version").read_text(encoding="utf-8").strip() == KERNEL_VERSION


def test_migration_backfills_authored_via(initialized: Path, run_op):
    """Records lacking authored_via get backfilled. Records authored by
    kernel.self get kernel.self; everything else gets outside."""
    repo = initialized
    _reset_to_v100(repo, run_op)
    result = _run_migration(repo)
    assert result["returncode"] == 0, result["stderr"]
    # Bootstrap was authored_by: human-test-author → outside.
    bootstrap = parse_file(repo / "ir" / "test-scope" / "000-bootstrap.md")
    assert bootstrap.frontmatter["authored_via"] == "outside"
    # Foundational kernel records authored_by: kernel.self → kernel.self.
    kernel_scope = parse_file(repo / "ir" / "_kernel" / "scope" / "_kernel.md")
    assert kernel_scope.frontmatter["authored_via"] == "kernel.self"


def test_migration_is_idempotent(initialized: Path, run_op):
    """Re-running the migration on already-migrated state is a noop."""
    repo = initialized
    _reset_to_v100(repo, run_op)
    first = _run_migration(repo)
    assert first["returncode"] == 0, first["stderr"]
    second = _run_migration(repo)
    assert second["returncode"] == 0, second["stderr"]
    assert "no-op" in second["stdout"] or "already at" in second["stdout"]


def test_migration_reindex_check_passes_after_run(initialized: Path, run_op):
    """After migration, reindex --check passes — every record has authored_via,
    no index drift."""
    repo = initialized
    _reset_to_v100(repo, run_op)
    result = _run_migration(repo)
    assert result["returncode"] == 0, result["stderr"]
    env = run_op("kernel.reindex", {"mode": "check"})
    assert env["data"]["drift_detected"] is False
