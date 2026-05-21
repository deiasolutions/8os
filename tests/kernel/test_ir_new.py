"""Tests for kernel.ir.new — tier 1 happy path and key error paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from eightos.errors import ALREADY_EXISTS, DEPENDENCY_BROKEN, KernelError
from eightos._frontmatter import parse_file


def _new_payload(**over):
    base = {
        "scope_id": "test-scope",
        "slug": "first-decision",
        "tier": 1,
        "intention_text": "Decide on the first ADR for the test project.",
        "depends_on": ["000-bootstrap"],
        "authority_level": "convention",
        "authored_by": "test-author",
    }
    base.update(over)
    return base


def test_ir_new_writes_tier1_record(initialized: Path, run_op):
    envelope = run_op("kernel.ir.new", _new_payload())
    assert envelope["status"] == "ok"
    assert envelope["data"]["ir_id"] == "first-decision"
    path = initialized / "ir" / "test-scope" / "first-decision.md"
    assert path.exists()

    rec = parse_file(path)
    assert rec.frontmatter["status"] == "open"
    assert rec.frontmatter["tier"] == 1
    assert rec.frontmatter["depends_on"] == ["000-bootstrap"]
    assert rec.intention_text.startswith("Decide on")
    assert rec.resolution_text is None  # not resolved yet


def test_ir_new_appends_operation_event(initialized: Path, run_op):
    envelope = run_op("kernel.ir.new", _new_payload())
    event_id = envelope["event_id"]
    jsonl_lines = []
    for jsonl in (initialized / ".8os" / "events").rglob("*.jsonl"):
        jsonl_lines.extend(jsonl.read_text().splitlines())
    assert any(event_id in ln for ln in jsonl_lines)


def test_ir_new_reindex_stays_clean(initialized: Path, run_op):
    """After ir.new, reindex --check must pass."""
    run_op("kernel.ir.new", _new_payload())
    envelope = run_op("kernel.reindex", {"mode": "check"})
    assert envelope["data"]["drift_detected"] is False


def test_ir_new_rejects_duplicate_slug(initialized: Path, run_op):
    run_op("kernel.ir.new", _new_payload())
    with pytest.raises(KernelError) as excinfo:
        run_op("kernel.ir.new", _new_payload())
    assert excinfo.value.code == ALREADY_EXISTS


def test_ir_new_rejects_unknown_dependency(initialized: Path, run_op):
    payload = _new_payload(depends_on=["does-not-exist"])
    with pytest.raises(KernelError) as excinfo:
        run_op("kernel.ir.new", payload)
    assert excinfo.value.code == DEPENDENCY_BROKEN


def test_ir_new_validates_slug_pattern(initialized: Path, run_op):
    """Schema rejects slugs starting with non-alphanumeric or containing spaces."""
    payload = _new_payload(slug="Bad Slug")
    with pytest.raises(KernelError) as excinfo:
        run_op("kernel.ir.new", payload)
    assert excinfo.value.code == "SCHEMA_INVALID"


def test_ir_new_indexes_record_dependency(initialized: Path, run_op):
    run_op("kernel.ir.new", _new_payload())
    from eightos._yaml import load_yaml_file

    fwd = load_yaml_file(initialized / ".8os" / "index" / "deps-forward.yml") or {}
    rev = load_yaml_file(initialized / ".8os" / "index" / "deps-reverse.yml") or {}
    assert fwd.get("first-decision") == ["000-bootstrap"]
    assert "first-decision" in (rev.get("000-bootstrap") or [])
