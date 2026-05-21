"""Tests for kernel.reindex — rebuild regen and drift detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from eightos.errors import INDEX_DRIFT, KernelError


def test_reindex_check_passes_on_clean_repo(initialized: Path, run_op):
    envelope = run_op("kernel.reindex", {"mode": "check"})
    assert envelope["status"] == "ok"
    assert envelope["data"]["drift_detected"] is False


def test_reindex_rebuild_is_convergent(initialized: Path, run_op):
    """Repeated rebuilds always leave the indexes consistent: any number
    of consecutive rebuilds is followed by a clean check.

    v1.2 (Block 5.0): each rebuild emits a tier-3 event and runs the
    two-phase commit (write_all → append event → write_all) so the
    event-derived indexes (id-to-path, resolver-to-events, _checksum, etc.)
    grow by exactly one entry per rebuild while remaining consistent with
    the records-plus-events on disk. Strict byte-determinism does not hold
    across rebuilds (the event ledger grows), but consistency does.
    """
    for _ in range(3):
        run_op("kernel.reindex", {"mode": "rebuild"})
    envelope = run_op("kernel.reindex", {"mode": "check"})
    assert envelope["status"] == "ok"
    assert envelope["data"]["drift_detected"] is False


def test_reindex_detects_drift(initialized: Path, run_op):
    """Tampering with an index file triggers INDEX_DRIFT on check."""
    idx = initialized / ".8os" / "index" / "id-to-path.yml"
    idx.write_text("{phantom: ir/foo.md}\n")
    with pytest.raises(KernelError) as excinfo:
        run_op("kernel.reindex", {"mode": "check"})
    assert excinfo.value.code == INDEX_DRIFT
    assert "drift_diff" in excinfo.value.extra_context


def test_reindex_rebuild_emits_tier3_event(initialized: Path, run_op):
    """v1.2 (Block 5.0): rebuild mode emits a tier-3 event per axiom 8.

    The event records the rebuild's outcome with `resolver_id: "kernel"`,
    `bridge_id: "kernel.self"`, and `authored_via: kernel.self` (in the
    event-emission discipline). The event_id is non-null in the response.
    Check mode remains silent — it makes no claim, emits no event.
    """
    pre_lines = sum(
        len(p.read_text().splitlines())
        for p in (initialized / ".8os" / "events").rglob("*.jsonl")
    )
    envelope = run_op("kernel.reindex", {"mode": "rebuild"})
    post_lines = sum(
        len(p.read_text().splitlines())
        for p in (initialized / ".8os" / "events").rglob("*.jsonl")
    )
    assert envelope["event_id"] is not None, (
        "rebuild mode must emit a tier-3 event per axiom 8"
    )
    assert post_lines == pre_lines + 1, (
        "exactly one tier-3 event line should be appended by rebuild"
    )


def test_reindex_check_emits_no_event(initialized: Path, run_op):
    """Check mode is read-only: it verifies, it does not assert. No event."""
    pre_lines = sum(
        len(p.read_text().splitlines())
        for p in (initialized / ".8os" / "events").rglob("*.jsonl")
    )
    envelope = run_op("kernel.reindex", {"mode": "check"})
    post_lines = sum(
        len(p.read_text().splitlines())
        for p in (initialized / ".8os" / "events").rglob("*.jsonl")
    )
    assert envelope["event_id"] is None
    assert post_lines == pre_lines


def test_reindex_rebuild_indexes_consistent_with_emitted_event(
    initialized: Path, run_op
):
    """v1.2 two-phase commit: after rebuild, mode:"check" must find no drift.

    The rebuild appends an event to the ledger; the second-phase write_all
    inside the rebuild op picks up that event so the events-related indexes
    reflect it. A subsequent check-mode run must therefore find the indexes
    consistent with the records-plus-events on disk.
    """
    run_op("kernel.reindex", {"mode": "rebuild"})
    envelope = run_op("kernel.reindex", {"mode": "check"})
    assert envelope["status"] == "ok"
    assert envelope["data"]["drift_detected"] is False
