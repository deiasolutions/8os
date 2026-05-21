"""Tests for Block 4.2 — `kernel.ir.cancel` op + `cancelled` status enum.

Implements 8OS-BLOCK-1-SPEC v1.1 §3.8 (the `kernel.ir.cancel` SDK op) and §5
(status enum extension). The cancel op is terminal: a cancelled (I, R)
remains cancelled permanently; reversal is supersede-with-replacement.
Cancellation cascades one hop through the `deps-reverse` index, marking
direct dependents `stale`. Already-stale or already-cancelled dependents
are skipped silently per §3.8 (OPEN-Q-032 defers the audit-completeness
emit-on-skip alternative). Transitive cascade is **not** in v1.1
(OPEN-Q-031); test 10 locks that boundary.

The 17 tests enumerated in the Block 4.2 prompt:

1. Cancel an `open` (I, R) — basic flow.
2. Cancel a `resolved` (I, R).
3. Cancel a `stale` (I, R) — confirms §5.2 transition table wins over the
   §18.1 `IR_NOT_CANCELLABLE` description (which conflates `superseded`
   and `stale`).
4. Cancel an already-cancelled (I, R) → `IR_ALREADY_CANCELLED`.
5. Cancel a `superseded` (I, R) → `IR_NOT_CANCELLABLE`.
6. Cascade marks one-hop dependents `stale`.
7. Cascade respects scope visibility (axiom 3) — cross-scope dependents
   whose `visible_to` excludes the cancelled scope are skipped.
8. Cascade skips already-stale dependents silently.
9. Cascade skips already-cancelled dependents silently.
10. Transitive cascade does NOT propagate beyond one hop (OPEN-Q-031
    boundary lock).
11. Authority enforcement → `CANCELLATION_AUTHORITY_INSUFFICIENT`.
12. Supersede-with-replacement after cancellation — SKIPPED, see
    block-4.2 report (§3.8 reversibility path requires either a
    `kernel.ir.new`-with-`supersedes:` field or a `kernel.ir.supersede`
    extension to accept cancelled targets; neither was in Block 4.2's
    explicit pieces).
13. `cascade: false` flag suppresses the cascade entirely.
14. `kernel.reindex --check` accepts a correctly-formed cancelled record.
15. `kernel.reindex --check` rejects a cancelled record without
    `cancelled_at` / `cancelled_by`.
16. Backward compat — pre-Block-4.2-shaped records load + dispatch.
17. Upgrade-mode body refresh — v1.1.0-dev.1 → v1.1.0-dev.2 is a no-op
    on vendored bodies (no body schemas changed).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eightos import __version__ as KERNEL_VERSION
from eightos._frontmatter import parse_file, serialize
from eightos.errors import (
    CANCELLATION_AUTHORITY_INSUFFICIENT,
    IR_ALREADY_CANCELLED,
    IR_NOT_CANCELLABLE,
    SCHEMA_INVALID,
    KernelError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _author_open(run_op, slug: str, *, depends_on: list[str] | None = None,
                 scope: str = "test-scope", domain: str | None = None) -> str:
    """Author a fresh open intention; return its slug."""
    payload = {
        "scope_id": scope,
        "slug": slug,
        "tier": 1,
        "intention_text": f"Test intention {slug!r}.",
        "authority_level": "convention",
        "authored_by": "test-author",
    }
    if depends_on:
        payload["depends_on"] = depends_on
    if domain is not None:
        payload["domain"] = domain
    run_op("kernel.ir.new", payload)
    return slug


def _force_status(repo: Path, slug: str, status: str) -> None:
    """Bypass the SDK to set a record's status directly. Used to set up
    pre-cascade fixtures (`stale`, etc.) without invoking the cancel op
    itself."""
    rec_path = repo / "ir" / "test-scope" / f"{slug}.md"
    rec = parse_file(rec_path)
    rec.frontmatter["status"] = status
    rec_path.write_text(serialize(rec))


# ---------------------------------------------------------------------------
# Tests 1-3 — cancel from each starting status
# ---------------------------------------------------------------------------


def test_cancel_an_open_ir(initialized: Path, run_op):
    repo = initialized
    _author_open(run_op, "to-cancel")

    env = run_op("kernel.ir.cancel", {
        "ir_id": "to-cancel",
        "cancelled_by": "test-author",
        "reason": "no longer needed",
        "authored_via": "kernel.self",
    })
    data = env["data"]
    assert data["ir_status_after"] == "cancelled"
    assert data["affected_dependents"] == 0
    assert data["dropped_pending_ops"] == 0
    assert data["cancellation_event_id"] == env["event_id"]

    rec = parse_file(repo / "ir" / "test-scope" / "to-cancel.md")
    assert rec.frontmatter["status"] == "cancelled"
    assert isinstance(rec.frontmatter["cancelled_at"], str)
    assert rec.frontmatter["cancelled_by"] == "test-author"
    assert rec.frontmatter["cancelled_reason"] == "no longer needed"


def test_cancel_a_resolved_ir(initialized: Path, run_op):
    repo = initialized
    _author_open(run_op, "to-resolve")
    _force_status(repo, "to-resolve", "resolved")

    env = run_op("kernel.ir.cancel", {
        "ir_id": "to-resolve",
        "cancelled_by": "test-author",
        "authored_via": "kernel.self",
    })
    assert env["data"]["ir_status_after"] == "cancelled"
    assert parse_file(
        repo / "ir" / "test-scope" / "to-resolve.md"
    ).frontmatter["status"] == "cancelled"


def test_cancel_a_stale_ir_per_section_5_2(initialized: Path, run_op):
    """v1.1 §5.2's transition table permits stale → cancelled. v1.1 §18.1's
    error description for `IR_NOT_CANCELLABLE` says it rejects `superseded`
    OR `stale`, which contradicts §5.2. The implementation follows §5.2."""
    repo = initialized
    _author_open(run_op, "to-stale")
    _force_status(repo, "to-stale", "stale")

    env = run_op("kernel.ir.cancel", {
        "ir_id": "to-stale",
        "cancelled_by": "test-author",
        "authored_via": "kernel.self",
    })
    assert env["data"]["ir_status_after"] == "cancelled"


# ---------------------------------------------------------------------------
# Tests 4-5 — terminal-state rejections
# ---------------------------------------------------------------------------


def test_cancel_already_cancelled_rejects(initialized: Path, run_op):
    _author_open(run_op, "twice")
    run_op("kernel.ir.cancel", {
        "ir_id": "twice", "cancelled_by": "test-author", "authored_via": "kernel.self",
    })
    with pytest.raises(KernelError) as exc:
        run_op("kernel.ir.cancel", {
            "ir_id": "twice", "cancelled_by": "test-author", "authored_via": "kernel.self",
        })
    assert exc.value.code == IR_ALREADY_CANCELLED


def test_cancel_superseded_rejects(initialized: Path, run_op):
    """Superseded is terminal per §5.2. Cancellation is forbidden — the
    correct path is to supersede again or accept the chain."""
    _author_open(run_op, "old-record")
    run_op("kernel.ir.supersede", {
        "old_ir_id": "old-record",
        "new_intention_text": "Replacement intention.",
        "authored_by": "test-author",
        "reason": "needed an update",
    })
    with pytest.raises(KernelError) as exc:
        run_op("kernel.ir.cancel", {
            "ir_id": "old-record",
            "cancelled_by": "test-author",
            "authored_via": "kernel.self",
        })
    assert exc.value.code == IR_NOT_CANCELLABLE


# ---------------------------------------------------------------------------
# Tests 6-10 — cascade behaviour
# ---------------------------------------------------------------------------


def test_cascade_marks_one_hop_dependent_stale(initialized: Path, run_op):
    repo = initialized
    _author_open(run_op, "parent")
    _author_open(run_op, "dependent", depends_on=["parent"])

    env = run_op("kernel.ir.cancel", {
        "ir_id": "parent",
        "cancelled_by": "test-author",
        "authored_via": "kernel.self",
    })
    assert env["data"]["affected_dependents"] == 1

    dep = parse_file(repo / "ir" / "test-scope" / "dependent.md")
    assert dep.frontmatter["status"] == "stale"
    assert dep.frontmatter["staled_reason"].startswith("cascade from cancellation of")


def test_cascade_respects_scope_visibility(initialized: Path, run_op):
    """A dependent in a scope whose `visible_to` excludes the cancelled
    record's scope is not cascaded (axiom 3)."""
    repo = initialized
    # Author a sibling scope whose visibility_defaults don't include
    # `test-scope`. Records authored in it inherit `visible_to: [scope-b]`,
    # which omits `test-scope` — the cascade from a test-scope cancel
    # cannot reach them.
    run_op("kernel.ir.new", {
        "scope_id": "_kernel",
        "slug": "scope-b",
        "tier": 1,
        "intention_text": "An isolated scope.",
        "projection_types": ["_kernel.scope"],
        "authority_level": "hard",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "frontmatter_extensions": {
            "parent_scope": "test-scope",
            "authority_defaults": {"hard": [], "convention": [], "uncalibrated": []},
            "visibility_defaults": ["scope-b"],
        },
    })
    _author_open(run_op, "parent")
    _author_open(run_op, "isolated-dep", depends_on=["parent"], scope="scope-b")

    env = run_op("kernel.ir.cancel", {
        "ir_id": "parent",
        "cancelled_by": "test-author",
        "authored_via": "kernel.self",
    })
    assert env["data"]["affected_dependents"] == 0

    dep = parse_file(repo / "ir" / "scope-b" / "isolated-dep.md")
    assert dep.frontmatter["status"] == "open"


def test_cascade_skips_already_stale_silently(initialized: Path, run_op):
    """Two dependents share a parent. One is pre-staled. Cancelling the
    parent should affect only the still-open one; the stale dep is skipped
    with no status mutation and no cascade event for it."""
    repo = initialized
    _author_open(run_op, "parent")
    _author_open(run_op, "open-dep", depends_on=["parent"])
    _author_open(run_op, "stale-dep", depends_on=["parent"])
    _force_status(repo, "stale-dep", "stale")

    env = run_op("kernel.ir.cancel", {
        "ir_id": "parent",
        "cancelled_by": "test-author",
        "authored_via": "kernel.self",
    })
    assert env["data"]["affected_dependents"] == 1

    open_dep = parse_file(repo / "ir" / "test-scope" / "open-dep.md")
    stale_dep = parse_file(repo / "ir" / "test-scope" / "stale-dep.md")
    assert open_dep.frontmatter["status"] == "stale"
    assert stale_dep.frontmatter["status"] == "stale"
    # The skip was silent — no `staled_reason` was written to the
    # already-stale dependent because the cascade did not touch it.
    assert "staled_reason" not in stale_dep.frontmatter


def test_cascade_skips_already_cancelled_silently(initialized: Path, run_op):
    repo = initialized
    _author_open(run_op, "parent")
    _author_open(run_op, "open-dep", depends_on=["parent"])
    _author_open(run_op, "cancelled-dep", depends_on=["parent"])
    # Cancel cancelled-dep first via the op (not _force_status) so it
    # carries cancelled_at / cancelled_by and the reindex --check stays
    # clean.
    run_op("kernel.ir.cancel", {
        "ir_id": "cancelled-dep",
        "cancelled_by": "test-author",
        "authored_via": "kernel.self",
    })

    env = run_op("kernel.ir.cancel", {
        "ir_id": "parent",
        "cancelled_by": "test-author",
        "authored_via": "kernel.self",
    })
    assert env["data"]["affected_dependents"] == 1

    cancelled_dep = parse_file(repo / "ir" / "test-scope" / "cancelled-dep.md")
    # Status remains cancelled; the cascade did not flip it to stale.
    assert cancelled_dep.frontmatter["status"] == "cancelled"


def test_transitive_cascade_does_not_propagate(initialized: Path, run_op):
    """v1.1 §3.8 specifies one-hop cascade only; transitive propagation
    is OPEN-Q-031 (deferred). This test locks the boundary."""
    repo = initialized
    _author_open(run_op, "root")
    _author_open(run_op, "level-1", depends_on=["root"])
    _author_open(run_op, "level-2", depends_on=["level-1"])

    env = run_op("kernel.ir.cancel", {
        "ir_id": "root",
        "cancelled_by": "test-author",
        "authored_via": "kernel.self",
    })
    assert env["data"]["affected_dependents"] == 1  # only level-1

    level_1 = parse_file(repo / "ir" / "test-scope" / "level-1.md")
    level_2 = parse_file(repo / "ir" / "test-scope" / "level-2.md")
    assert level_1.frontmatter["status"] == "stale"
    assert level_2.frontmatter["status"] == "open"  # NOT propagated


# ---------------------------------------------------------------------------
# Test 11 — authority enforcement
# ---------------------------------------------------------------------------


def test_cancellation_authority_insufficient(initialized: Path, run_op):
    """A caller whose bridge has lower authority than the target's
    `authority_level` is rejected with `CANCELLATION_AUTHORITY_INSUFFICIENT`.

    Setup: target authored at `convention`. Caller authored_via=`outside`,
    which the kernel maps to `uncalibrated` per axiom 0 / v1.0.1-partial
    Amendment 2. uncalibrated < convention → reject.
    """
    _author_open(run_op, "high-target")  # authority_level: convention
    with pytest.raises(KernelError) as exc:
        run_op("kernel.ir.cancel", {
            "ir_id": "high-target",
            "cancelled_by": "test-author",
            "authored_via": "outside",
        })
    assert exc.value.code == CANCELLATION_AUTHORITY_INSUFFICIENT


# ---------------------------------------------------------------------------
# Test 12 — UNSKIPPED in Block 4.6: supersede-with-replacement after cancellation
# ---------------------------------------------------------------------------


def test_supersede_with_replacement_after_cancellation(initialized: Path, run_op):
    """v1.1 §3.8 reversibility: cancellation is reversible only via
    authoring a new (I, R) carrying `supersedes: <cancelled-id>` through
    `kernel.ir.new`'s Path A input field (BLOCK-4.5-SPEC-AMENDMENTS
    Amendment 4 / Block 4.6). The cancelled target is unchanged; the new
    record carries lineage backward only.

    Skipped at Block 4.2 close pending v1.1 housekeeping path-selection;
    unskipped at Block 4.6 once Path A's implementation landed."""
    repo = initialized
    _author_open(run_op, "to-cancel-then-replace")
    run_op("kernel.ir.cancel", {
        "ir_id": "to-cancel-then-replace",
        "cancelled_by": "test-author",
        "reason": "needs to be re-authored from scratch",
        "authored_via": "kernel.self",
    })

    # Cancelled target snapshot: status, no superseded_by, no forward pointer.
    pre = parse_file(repo / "ir" / "test-scope" / "to-cancel-then-replace.md")
    assert pre.frontmatter["status"] == "cancelled"
    assert pre.frontmatter.get("superseded_by") is None

    # Path A: author a NEW record with supersedes pointing at the cancelled one.
    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "fresh-replacement",
        "tier": 1,
        "intention_text": "Replacement for the cancelled record.",
        "authority_level": "convention",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "supersedes": "to-cancel-then-replace",
    })

    new_rec = parse_file(repo / "ir" / "test-scope" / "fresh-replacement.md")
    assert new_rec.frontmatter["status"] == "open"
    assert new_rec.frontmatter["supersedes"] == "to-cancel-then-replace"

    # Cancelled target MUST be unchanged: still cancelled, no superseded_by
    # written, no transition event on it (Path A's unidirectional-pointer
    # discipline per BLOCK-4.5-SPEC-AMENDMENTS Amendment 4).
    post = parse_file(repo / "ir" / "test-scope" / "to-cancel-then-replace.md")
    assert post.frontmatter["status"] == "cancelled"
    assert post.frontmatter.get("superseded_by") is None
    assert post.frontmatter["cancelled_at"] == pre.frontmatter["cancelled_at"]
    assert post.frontmatter["cancelled_by"] == pre.frontmatter["cancelled_by"]


# ---------------------------------------------------------------------------
# Test 13 — cascade: false
# ---------------------------------------------------------------------------


def test_cascade_false_suppresses_cascade(initialized: Path, run_op):
    repo = initialized
    _author_open(run_op, "parent")
    _author_open(run_op, "dependent", depends_on=["parent"])

    env = run_op("kernel.ir.cancel", {
        "ir_id": "parent",
        "cancelled_by": "test-author",
        "cascade": False,
        "authored_via": "kernel.self",
    })
    assert env["data"]["affected_dependents"] == 0

    dep = parse_file(repo / "ir" / "test-scope" / "dependent.md")
    assert dep.frontmatter["status"] == "open"  # untouched


# ---------------------------------------------------------------------------
# Tests 14-15 — reindex --check on cancelled state
# ---------------------------------------------------------------------------


def test_reindex_check_accepts_well_formed_cancelled_record(initialized: Path, run_op):
    _author_open(run_op, "to-cancel")
    run_op("kernel.ir.cancel", {
        "ir_id": "to-cancel",
        "cancelled_by": "test-author",
        "authored_via": "kernel.self",
    })
    # Should not raise.
    run_op("kernel.reindex", {"mode": "check"})


def test_reindex_check_rejects_cancelled_without_cancelled_at(initialized: Path, run_op):
    repo = initialized
    _author_open(run_op, "to-corrupt")
    # Cancel cleanly first so cancelled_by is present, then strip cancelled_at
    # to simulate direct-edit drift.
    run_op("kernel.ir.cancel", {
        "ir_id": "to-corrupt",
        "cancelled_by": "test-author",
        "authored_via": "kernel.self",
    })
    rec_path = repo / "ir" / "test-scope" / "to-corrupt.md"
    rec = parse_file(rec_path)
    rec.frontmatter.pop("cancelled_at")
    rec_path.write_text(serialize(rec))
    run_op("kernel.reindex", {"mode": "rebuild"})  # reset indexes after manual edit

    with pytest.raises(KernelError) as exc:
        run_op("kernel.reindex", {"mode": "check"})
    assert exc.value.code == SCHEMA_INVALID
    flagged = exc.value.extra_context["records_with_invalid_cancelled_state"]
    assert any("to-corrupt" in entry["path"] for entry in flagged)


# ---------------------------------------------------------------------------
# Test 16 — backward compat
# ---------------------------------------------------------------------------


def test_pre_block_4_2_record_loads_and_dispatches(initialized: Path, run_op):
    """A v1.1.0-dev.1-shaped record (status one of the four prior values)
    loads, indexes, and lists cleanly. No record carries `cancelled` until
    Block 4.2 lands."""
    _author_open(run_op, "legacy-shape")  # status: open
    env = run_op("kernel.ir.list", {
        "scope_id": "test-scope",
        "status": ["open"],
    })
    ids = {r["ir_id"] for r in env["data"]["results"]}
    assert "legacy-shape" in ids


# ---------------------------------------------------------------------------
# Test 17 — upgrade-mode body refresh
# ---------------------------------------------------------------------------


def test_upgrade_from_dev1_to_current_is_clean(repo: Path, run_op):
    """Block 4.2 added no vendored projection body schemas (the only schema
    touched was `kernel.ir.list.v1.input.json`'s status enum, which is op
    schema, not vendored body). When the live repo is bootstrapped at the
    current binary version then rewound to dev.1, an upgrade back to current
    refreshes only the bodies that the test setup actually rewound. Since
    the test setup bootstrapped at current (so vendored bodies on disk are
    already current-shape), the upgrade observes no body diff. Idempotent
    on re-run at matched version. (Test made version-agnostic in Block 4.3
    per the F3 stale-baseline discipline.)
    """
    # Bootstrap a repo at the current binary version.
    run_op("kernel.init", {
        "project_name": "test-project",
        "primary_scope_id": "test-scope",
        "primary_operator_id": "test-author",
        "kernel_version": KERNEL_VERSION,
    })
    # Manually rewind .8os/version to dev.1 to simulate the pre-upgrade state.
    (repo / ".8os" / "version").write_text("1.1.0-dev.1\n")

    env = run_op("kernel.init", {
        "project_name": "test-project",
        "primary_scope_id": "test-scope",
        "primary_operator_id": "test-author",
        "kernel_version": KERNEL_VERSION,
    })
    assert env["data"]["mode"] == "upgrade"
    assert env["data"]["previous_version"] == "1.1.0-dev.1"
    assert env["data"]["kernel_version"] == KERNEL_VERSION
    # On-disk bodies were just bootstrapped at current; the upgrade observes
    # no diff, so no refresh fires.
    assert env["data"]["refreshed"]["vendored_projection_bodies"] == []
    assert env["data"]["added"]["vendored_projection_bodies"] == []

    # Idempotent on re-run at matched version.
    env_again = run_op("kernel.init", {
        "project_name": "test-project",
        "primary_scope_id": "test-scope",
        "primary_operator_id": "test-author",
        "kernel_version": KERNEL_VERSION,
    })
    assert env_again["data"]["mode"] == "noop"
