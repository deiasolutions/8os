"""Tests for the public engine-port facade (``eightos.api``) — Slice 1.

These exercise the curated public surface only (no reaching into internals),
which is the consume path the DES / sd-ortrta will use.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import eightos.api as api
from eightos._frontmatter import IRRecord
from eightos._paths import events_dir
from eightos.errors import KernelError

_FEEDABLE_FM = {
    "id": "x",
    "kind": "ir-node",
    "tier": 1,
    "projection_types": [],
    "scope": "s",
    "status": "open",
    "authored_by": "a",
    "authored_on": "2026-06-01T00:00:00.000Z",
    "authority_level": "convention",
    "authored_via": "outside",
}


def _author_open(slug: str) -> None:
    api.run(
        "kernel.ir.new",
        {
            "scope_id": "test-scope",
            "slug": slug,
            "tier": 1,
            "intention_text": "A feedable work intention.",
            "authority_level": "convention",
            "authored_by": "test-author",
            "authored_via": "outside",
        },
    )


def test_run_dispatches(initialized: Path):
    env = api.run("kernel.reindex", {"mode": "check"})
    assert env["status"] == "ok"


def test_run_unknown_op_raises(repo: Path):
    with pytest.raises(KernelError):
        api.run("kernel.nonsense", {})


def test_leaves_finds_open_intention(initialized: Path):
    _author_open("feed-me")
    ids = [r.frontmatter.get("id") for r in api.leaves(initialized, "test-scope")]
    assert "feed-me" in ids


def test_is_feedable_true_for_authored_leaf(initialized: Path):
    _author_open("ok-rec")
    leaf = next(
        r for r in api.leaves(initialized, "test-scope") if r.frontmatter["id"] == "ok-rec"
    )
    verdict = api.is_feedable(leaf)
    assert verdict["feedable"] is True
    assert verdict["missing"] == []


def test_is_feedable_false_when_missing_fields():
    rec = IRRecord(frontmatter={"id": "x"}, intention_text="hi", resolution_text=None)
    verdict = api.is_feedable(rec)
    assert verdict["feedable"] is False
    assert "authored_via" in verdict["missing"]


def test_is_feedable_false_when_no_intention():
    rec = IRRecord(frontmatter=dict(_FEEDABLE_FM), intention_text="   ", resolution_text=None)
    verdict = api.is_feedable(rec)
    assert verdict["feedable"] is False
    assert "intention_text" in verdict["missing"]


def test_cost_of_reads_and_defaults():
    assert api.cost_of({"cost_actual": {"coin_usd": 0.5}})["coin_usd"] == 0.5
    assert api.cost_of({"data": {"cost_actual": {"clock_ms": 12}}})["clock_ms"] == 12.0
    zero = api.cost_of({})
    assert zero["clock_ms"] == 0.0
    assert zero["coin_usd"] == 0.0
    assert zero["carbon_g"] == 0.0


def test_emit_marker_writes_event(initialized: Path):
    eid = api.emit_marker(initialized, kind="test.marker", payload={"n": 1})
    assert eid
    found = False
    for jsonl in events_dir(initialized).rglob("events.jsonl"):
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            if json.loads(line).get("event_id") == eid:
                found = True
    assert found, "emit_marker event not found in any events.jsonl"
