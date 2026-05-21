"""Tests for Block 4.6 — Path A implementation: `kernel.ir.new` accepts
`supersedes:` for supersede-with-replacement of cancelled records, plus
`kernel.ir.list` `include_cancelled` filter.

Per 8OS-BLOCK-1-SPEC v1.1 §3.2 (as amended by BLOCK-4.5-SPEC-AMENDMENTS
Amendment 4) and v1.1 §3.10 (as clarified by Appendix A item 7).

Architecture: cancellation is terminal (v1.1 §5.2). Reversal is achieved
via authoring a NEW (I, R) carrying `supersedes: <cancelled-id>` in its
frontmatter through `kernel.ir.new`. The cancelled target is unchanged
(no `superseded_by` written, no transition event). Lineage is
unidirectional from new record to cancelled target. Discovery of "what
replaced this cancelled record" is via index lookup on the new records'
`supersedes:` field.

`kernel.ir.list` filters cancelled records by default (`include_cancelled:
false`); explicit `status: ["cancelled"]` overrides the gate (caller
intent wins per Block 4.6 Q2).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eightos import __version__ as KERNEL_VERSION
from eightos._frontmatter import parse_file, serialize
from eightos.errors import (
    IR_SUPERSEDES_TARGET_NOT_CANCELLED,
    NOT_FOUND,
    SCHEMA_INVALID,
    KernelError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _author_open(run_op, slug: str, *, scope: str = "test-scope") -> str:
    run_op("kernel.ir.new", {
        "scope_id": scope,
        "slug": slug,
        "tier": 1,
        "intention_text": f"Test intention {slug!r}.",
        "authority_level": "convention",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
    })
    return slug


def _author_cancelled(run_op, slug: str, *, scope: str = "test-scope") -> str:
    _author_open(run_op, slug, scope=scope)
    run_op("kernel.ir.cancel", {
        "ir_id": slug,
        "cancelled_by": "test-author",
        "authored_via": "kernel.self",
    })
    return slug


def _force_status(repo: Path, slug: str, status: str, *, scope: str = "test-scope") -> None:
    rec_path = repo / "ir" / scope / f"{slug}.md"
    rec = parse_file(rec_path)
    rec.frontmatter["status"] = status
    rec_path.write_text(serialize(rec))


# ---------------------------------------------------------------------------
# Tests 1-3 — basic Path A behavior + null/omission
# ---------------------------------------------------------------------------


def test_kernel_ir_new_without_supersedes_unchanged(initialized: Path, run_op):
    """Regression guard: omitting `supersedes` (or supplying null) preserves
    the pre-Block-4.6 behavior — record authored at status open with
    supersedes: None."""
    repo = initialized
    _author_open(run_op, "vanilla")
    rec = parse_file(repo / "ir" / "test-scope" / "vanilla.md")
    assert rec.frontmatter["status"] == "open"
    assert rec.frontmatter["supersedes"] is None


def test_kernel_ir_new_with_explicit_null_supersedes(initialized: Path, run_op):
    """Explicit `supersedes: null` is equivalent to omission."""
    repo = initialized
    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "explicitly-null",
        "tier": 1,
        "intention_text": "Testing explicit null supersedes.",
        "authority_level": "convention",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "supersedes": None,
    })
    rec = parse_file(repo / "ir" / "test-scope" / "explicitly-null.md")
    assert rec.frontmatter["supersedes"] is None


def test_kernel_ir_new_with_valid_cancelled_target_authors_lineage(initialized: Path, run_op):
    """The headline Path A flow: cancel A, then ir.new with supersedes:A
    authors B carrying the lineage backward. A is unchanged."""
    repo = initialized
    _author_cancelled(run_op, "old-and-cancelled")
    pre = parse_file(repo / "ir" / "test-scope" / "old-and-cancelled.md")
    pre_cancelled_at = pre.frontmatter["cancelled_at"]

    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "the-replacement",
        "tier": 1,
        "intention_text": "Successor to the cancelled record.",
        "authority_level": "convention",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "supersedes": "old-and-cancelled",
    })

    new = parse_file(repo / "ir" / "test-scope" / "the-replacement.md")
    assert new.frontmatter["supersedes"] == "old-and-cancelled"
    assert new.frontmatter["status"] == "open"
    assert new.frontmatter["superseded_by"] is None  # the new record is the live one

    # Cancelled target MUST be unchanged.
    post = parse_file(repo / "ir" / "test-scope" / "old-and-cancelled.md")
    assert post.frontmatter["status"] == "cancelled"
    assert post.frontmatter.get("superseded_by") is None
    assert post.frontmatter["cancelled_at"] == pre_cancelled_at


# ---------------------------------------------------------------------------
# Tests 4-8 — error cases per the prompt's inventory
# ---------------------------------------------------------------------------


def test_supersedes_nonexistent_target_raises_not_found(initialized: Path, run_op):
    """Per Block 4.6 Q1: missing-target case reuses generic NOT_FOUND
    (not IR_NOT_FOUND), matching the kernel's existing pattern across
    cancel/supersede/resolve/get."""
    with pytest.raises(KernelError) as exc:
        run_op("kernel.ir.new", {
            "scope_id": "test-scope",
            "slug": "orphan",
            "tier": 1,
            "intention_text": "References a nonexistent target.",
            "authority_level": "convention",
            "authored_by": "test-author",
            "authored_via": "kernel.self",
            "supersedes": "does-not-exist",
        })
    assert exc.value.code == NOT_FOUND
    assert exc.value.input_field == "supersedes"


def test_supersedes_open_record_raises_target_not_cancelled(initialized: Path, run_op):
    _author_open(run_op, "still-living")
    with pytest.raises(KernelError) as exc:
        run_op("kernel.ir.new", {
            "scope_id": "test-scope",
            "slug": "wrong-call",
            "tier": 1,
            "intention_text": "Trying to use Path A on a living record.",
            "authority_level": "convention",
            "authored_by": "test-author",
            "authored_via": "kernel.self",
            "supersedes": "still-living",
        })
    assert exc.value.code == IR_SUPERSEDES_TARGET_NOT_CANCELLED
    assert "open" in exc.value.message


def test_supersedes_resolved_record_raises_target_not_cancelled(initialized: Path, run_op):
    repo = initialized
    _author_open(run_op, "completed")
    _force_status(repo, "completed", "resolved")
    with pytest.raises(KernelError) as exc:
        run_op("kernel.ir.new", {
            "scope_id": "test-scope",
            "slug": "wrong-resolved",
            "tier": 1,
            "intention_text": "Resolved is not cancelled.",
            "authority_level": "convention",
            "authored_by": "test-author",
            "authored_via": "kernel.self",
            "supersedes": "completed",
        })
    assert exc.value.code == IR_SUPERSEDES_TARGET_NOT_CANCELLED


def test_supersedes_stale_record_raises_target_not_cancelled(initialized: Path, run_op):
    """Stale is permitted to BE cancelled per BLOCK-4.5-SPEC-AMENDMENTS
    Amendment 3, but not to BE the target of supersede-with-replacement
    (that path is for cancelled records only). Two semantics, both pinned."""
    repo = initialized
    _author_open(run_op, "stale-target")
    _force_status(repo, "stale-target", "stale")
    with pytest.raises(KernelError) as exc:
        run_op("kernel.ir.new", {
            "scope_id": "test-scope",
            "slug": "wrong-stale",
            "tier": 1,
            "intention_text": "Stale is not cancelled.",
            "authority_level": "convention",
            "authored_by": "test-author",
            "authored_via": "kernel.self",
            "supersedes": "stale-target",
        })
    assert exc.value.code == IR_SUPERSEDES_TARGET_NOT_CANCELLED


def test_supersedes_superseded_record_raises_target_not_cancelled(initialized: Path, run_op):
    _author_open(run_op, "older")
    run_op("kernel.ir.supersede", {
        "old_ir_id": "older",
        "new_intention_text": "Newer version.",
        "authored_by": "test-author",
        "reason": "improvement",
    })
    with pytest.raises(KernelError) as exc:
        run_op("kernel.ir.new", {
            "scope_id": "test-scope",
            "slug": "wrong-superseded",
            "tier": 1,
            "intention_text": "Superseded is not cancelled.",
            "authority_level": "convention",
            "authored_by": "test-author",
            "authored_via": "kernel.self",
            "supersedes": "older",
        })
    assert exc.value.code == IR_SUPERSEDES_TARGET_NOT_CANCELLED


# ---------------------------------------------------------------------------
# Test 9 — cross-scope reversal (locks Block 4.5 Q5 decision)
# ---------------------------------------------------------------------------


def test_supersedes_cross_scope_reversal_succeeds(initialized: Path, run_op):
    """Block 4.5 Q5 locked no same-scope constraint at v1.1. A cancelled
    record in scope A may be 'reversed' by a new record in scope B."""
    repo = initialized
    # Set up a sibling scope.
    run_op("kernel.ir.new", {
        "scope_id": "_kernel",
        "slug": "scope-b",
        "tier": 1,
        "intention_text": "A sibling scope for cross-scope reversal testing.",
        "projection_types": ["_kernel.scope"],
        "authority_level": "hard",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "frontmatter_extensions": {
            "parent_scope": "test-scope",
            "authority_defaults": {"hard": [], "convention": [], "uncalibrated": []},
            "visibility_defaults": ["scope-b", "test-scope"],
        },
    })
    _author_cancelled(run_op, "in-test-scope")

    run_op("kernel.ir.new", {
        "scope_id": "scope-b",
        "slug": "in-scope-b",
        "tier": 1,
        "intention_text": "Cross-scope replacement.",
        "authority_level": "convention",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "supersedes": "in-test-scope",
    })

    new = parse_file(repo / "ir" / "scope-b" / "in-scope-b.md")
    assert new.frontmatter["supersedes"] == "in-test-scope"
    assert new.frontmatter["scope"] == "scope-b"


# ---------------------------------------------------------------------------
# Test 10 — readback semantics
# ---------------------------------------------------------------------------


def test_get_on_replacement_shows_lineage_pointer(initialized: Path, run_op):
    _author_cancelled(run_op, "anchor")
    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "reads-back",
        "tier": 1,
        "intention_text": "Verify get returns lineage.",
        "authority_level": "convention",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "supersedes": "anchor",
    })
    env = run_op("kernel.ir.get", {"ir_id": "reads-back"})
    assert env["data"]["frontmatter"]["supersedes"] == "anchor"

    # The cancelled target's get is unchanged (still cancelled, no
    # superseded_by).
    target_env = run_op("kernel.ir.get", {"ir_id": "anchor"})
    assert target_env["data"]["frontmatter"]["status"] == "cancelled"
    assert target_env["data"]["frontmatter"].get("superseded_by") is None


# ---------------------------------------------------------------------------
# Test 11 — chain of cancellation-reversals
# ---------------------------------------------------------------------------


def test_chain_of_cancellation_reversals(initialized: Path, run_op):
    """Cancel A → author B with supersedes:A → cancel B → author C with
    supersedes:B. Verify the lineage chain reads cleanly; A and B remain
    terminally cancelled forever; C is the live record."""
    repo = initialized
    _author_cancelled(run_op, "rev-a")
    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "rev-b",
        "tier": 1,
        "intention_text": "B replaces cancelled A.",
        "authority_level": "convention",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "supersedes": "rev-a",
    })
    run_op("kernel.ir.cancel", {
        "ir_id": "rev-b",
        "cancelled_by": "test-author",
        "authored_via": "kernel.self",
    })
    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "rev-c",
        "tier": 1,
        "intention_text": "C replaces cancelled B.",
        "authority_level": "convention",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "supersedes": "rev-b",
    })

    a = parse_file(repo / "ir" / "test-scope" / "rev-a.md")
    b = parse_file(repo / "ir" / "test-scope" / "rev-b.md")
    c = parse_file(repo / "ir" / "test-scope" / "rev-c.md")
    assert a.frontmatter["status"] == "cancelled"
    assert a.frontmatter.get("superseded_by") is None
    assert b.frontmatter["status"] == "cancelled"
    assert b.frontmatter["supersedes"] == "rev-a"
    assert b.frontmatter.get("superseded_by") is None
    assert c.frontmatter["status"] == "open"
    assert c.frontmatter["supersedes"] == "rev-b"


# ---------------------------------------------------------------------------
# Tests 12-13 — schema-level rejection at the SDK boundary
# ---------------------------------------------------------------------------


def test_supersedes_wrong_type_rejects_schema_invalid(initialized: Path, run_op):
    with pytest.raises(KernelError) as exc:
        run_op("kernel.ir.new", {
            "scope_id": "test-scope",
            "slug": "bad-type",
            "tier": 1,
            "intention_text": "supersedes is not a string.",
            "authority_level": "convention",
            "authored_by": "test-author",
            "authored_via": "kernel.self",
            "supersedes": 42,
        })
    assert exc.value.code == SCHEMA_INVALID


def test_supersedes_empty_string_rejects_schema_invalid(initialized: Path, run_op):
    """Per BLOCK-4.5-SPEC-AMENDMENTS Amendment 1: empty string for an
    optional string base/input field is a schema violation; null is the
    canonical absence signal."""
    with pytest.raises(KernelError) as exc:
        run_op("kernel.ir.new", {
            "scope_id": "test-scope",
            "slug": "bad-empty",
            "tier": 1,
            "intention_text": "supersedes is empty string.",
            "authority_level": "convention",
            "authored_by": "test-author",
            "authored_via": "kernel.self",
            "supersedes": "",
        })
    assert exc.value.code == SCHEMA_INVALID


# ---------------------------------------------------------------------------
# Tests 14-17 — kernel.ir.list include_cancelled (queue item 7)
# ---------------------------------------------------------------------------


def test_list_excludes_cancelled_by_default(initialized: Path, run_op):
    """Default behavior: cancelled records do not appear in list output."""
    _author_open(run_op, "alive")
    _author_cancelled(run_op, "dead")

    env = run_op("kernel.ir.list", {"scope_id": "test-scope"})
    ids = {r["ir_id"] for r in env["data"]["results"]}
    assert "alive" in ids
    assert "dead" not in ids


def test_list_with_include_cancelled_true_shows_cancelled(initialized: Path, run_op):
    _author_open(run_op, "alive2")
    _author_cancelled(run_op, "dead2")

    env = run_op("kernel.ir.list", {
        "scope_id": "test-scope",
        "include_cancelled": True,
    })
    ids = {r["ir_id"] for r in env["data"]["results"]}
    assert "alive2" in ids
    assert "dead2" in ids


def test_list_with_explicit_status_filter_overrides_gate(initialized: Path, run_op):
    """Block 4.6 Q2: explicit `status: ['cancelled']` honors caller intent
    and bypasses the include_cancelled gate. 'If you asked, you get.'"""
    _author_open(run_op, "alive3")
    _author_cancelled(run_op, "dead3")

    env = run_op("kernel.ir.list", {
        "scope_id": "test-scope",
        "status": ["cancelled"],
        "include_cancelled": False,  # explicitly false; overridden by status filter
    })
    ids = {r["ir_id"] for r in env["data"]["results"]}
    assert "alive3" not in ids
    assert "dead3" in ids


def test_list_with_explicit_status_open_does_not_show_cancelled(initialized: Path, run_op):
    """Mirror test: status: ['open'] never returns cancelled records,
    regardless of include_cancelled. Status filter is independent of the
    gate when cancelled is NOT in the requested filter."""
    _author_open(run_op, "alive4")
    _author_cancelled(run_op, "dead4")

    env = run_op("kernel.ir.list", {
        "scope_id": "test-scope",
        "status": ["open"],
        "include_cancelled": True,
    })
    ids = {r["ir_id"] for r in env["data"]["results"]}
    assert "alive4" in ids
    assert "dead4" not in ids


# ---------------------------------------------------------------------------
# Test 18 — backward compat
# ---------------------------------------------------------------------------


def test_pre_block_4_6_record_loads_and_dispatches(initialized: Path, run_op):
    """A v1.1.0-dev.4-shaped record (no `supersedes` set, or `supersedes:
    None`) loads, indexes, and dispatches cleanly through list/get."""
    repo = initialized
    _author_open(run_op, "legacy-shape")
    rec_path = repo / "ir" / "test-scope" / "legacy-shape.md"
    rec = parse_file(rec_path)
    # Pre-Block-4.6 records carry supersedes: None (from kernel.ir.new's
    # vanilla path). Confirm this is treated as "no lineage."
    assert rec.frontmatter["supersedes"] is None

    env = run_op("kernel.ir.get", {"ir_id": "legacy-shape"})
    assert env["data"]["frontmatter"]["supersedes"] is None


# ---------------------------------------------------------------------------
# Test 19 — upgrade-from-dev.4-to-current is clean
# ---------------------------------------------------------------------------


def test_upgrade_from_dev4_to_current_is_clean(repo: Path, run_op):
    """A repo at v1.1.0-dev.4 upgrades to KERNEL_VERSION cleanly with no
    body refresh (the supersedes input field is op-input-side, not in any
    `_kernel.*` projection body). Pinned against KERNEL_VERSION per the
    discipline note in BLOCK-4.5-SPEC-AMENDMENTS Appendix A item 8."""
    # Bootstrap at current version so .8os/ is current shape.
    run_op("kernel.init", {
        "project_name": "upgrade-test",
        "primary_scope_id": "test-scope",
        "primary_operator_id": "test-author",
        "kernel_version": KERNEL_VERSION,
    })
    # Rewind only the version file to simulate a v1.1.0-dev.4 starting state.
    (repo / ".8os" / "version").write_text("1.1.0-dev.4\n")

    env = run_op("kernel.init", {
        "project_name": "upgrade-test",
        "primary_scope_id": "test-scope",
        "primary_operator_id": "test-author",
        "kernel_version": KERNEL_VERSION,
    })
    data = env["data"]
    assert data["mode"] == "upgrade"
    assert data["previous_version"] == "1.1.0-dev.4"
    assert data["kernel_version"] == KERNEL_VERSION
    # No vendored body refreshes — supersedes is op-input-side, not in any
    # vendored projection body.
    assert data["refreshed"]["vendored_projection_bodies"] == []
