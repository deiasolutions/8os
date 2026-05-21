"""Tests for kernel.ir.get and kernel.ir.list."""

from __future__ import annotations

from pathlib import Path

import pytest

from eightos.errors import NOT_FOUND, KernelError


def test_ir_get_returns_bootstrap(initialized: Path, run_op):
    envelope = run_op("kernel.ir.get", {"ir_id": "000-bootstrap"})
    data = envelope["data"]
    assert data["ir_id"] == "000-bootstrap"
    assert data["tier"] == 1
    assert data["frontmatter"]["status"] == "resolved"
    assert "Initialize" in data["intention_text"]


def test_ir_get_omits_body_when_requested(initialized: Path, run_op):
    envelope = run_op("kernel.ir.get", {"ir_id": "000-bootstrap", "include_body": False})
    assert envelope["data"]["intention_text"] is None
    assert envelope["data"]["resolution_text"] is None


def test_ir_get_404(initialized: Path, run_op):
    with pytest.raises(KernelError) as excinfo:
        run_op("kernel.ir.get", {"ir_id": "no-such-id"})
    assert excinfo.value.code == NOT_FOUND


def test_ir_list_default_returns_tier1(initialized: Path, run_op):
    envelope = run_op("kernel.ir.list", {})
    ids = [r["ir_id"] for r in envelope["data"]["results"]]
    assert ids == ["000-bootstrap"]
    assert envelope["data"]["total_matching"] == 1


def test_ir_list_filters_by_status(initialized: Path, run_op):
    """Bootstrap is resolved; an open ir.new record should be excluded by status filter."""
    run_op(
        "kernel.ir.new",
        {
            "scope_id": "test-scope",
            "slug": "open-decision",
            "tier": 1,
            "intention_text": "Open one.",
            "authority_level": "convention",
            "authored_by": "test-author",
        },
    )
    envelope = run_op("kernel.ir.list", {"status": ["resolved"]})
    ids = [r["ir_id"] for r in envelope["data"]["results"]]
    assert "000-bootstrap" in ids
    assert "open-decision" not in ids

    envelope2 = run_op("kernel.ir.list", {"status": ["open"]})
    ids2 = [r["ir_id"] for r in envelope2["data"]["results"]]
    assert ids2 == ["open-decision"]


def test_ir_list_pagination(initialized: Path, run_op):
    for i in range(5):
        run_op(
            "kernel.ir.new",
            {
                "scope_id": "test-scope",
                "slug": f"item-{i:02d}",
                "tier": 1,
                "intention_text": f"Item {i}.",
                "authority_level": "convention",
                "authored_by": "test-author",
            },
        )
    envelope = run_op("kernel.ir.list", {"limit": 2, "offset": 1})
    assert envelope["data"]["returned"] == 2
    assert envelope["data"]["total_matching"] == 6  # bootstrap + 5
