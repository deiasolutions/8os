"""Shape 2 tests — batch_id markers + per-batch holdout decisions."""

from __future__ import annotations

import json

from eightos import calibration
from eightos.factory import tick


def _read_events(initialized):
    paths = list((initialized / ".8os" / "events").rglob("*.jsonl"))
    out = []
    for p in paths:
        for ln in p.read_text().splitlines():
            if ln.strip():
                out.append(json.loads(ln))
    return out


def test_tick_writes_batch_start_marker(
    initialized,
    author_resolver,
    author_intention,
):
    """A factory.batch.start tier 3 event is authored at tick start
    carrying batch_id, leaves list, and holdout decisions."""
    author_resolver(
        "r1",
        implementation="tests.factory._fake_resolvers:simple_resolve_with_adapter",
    )
    author_intention("a")
    author_intention("b")

    summary = tick(initialized, "test-scope", domain="test/domain")
    events = _read_events(initialized)
    markers = [e for e in events if e.get("event_type") == "factory.batch.start"]
    assert len(markers) == 1
    m = markers[0]
    assert m["intention"]["batch_id"] == summary["batch_id"]
    assert m["intention"]["factory_scope"] == "test-scope"
    assert sorted(m["intention"]["leaves"]) == ["a", "b"]
    # Holdout decisions for both leaves are recorded (False since no
    # calibration policy applies).
    decisions = m["intention"]["holdout_decisions"]
    assert decisions == {"a": False, "b": False}


def test_marker_resolver_id_carries_factory_namespace(
    initialized,
    author_resolver,
    author_intention,
):
    """Per OPEN-Q-027 follow-up: the marker's resolver_id is in the
    factory.batch-marker namespace, distinct from kernel.binary."""
    author_resolver(
        "r1",
        implementation="tests.factory._fake_resolvers:simple_resolve_with_adapter",
    )
    author_intention("solo")
    tick(initialized, "test-scope", domain="test/domain")
    events = _read_events(initialized)
    markers = [e for e in events if e.get("event_type") == "factory.batch.start"]
    assert markers[0]["resolver_id"].startswith("factory.batch-marker@")


def test_holdout_precomputation_matches_sequential_per_leaf(
    initialized,
    author_resolver,
    author_intention,
    author_calibration_policy,
):
    """The per-batch holdout-decision set computed at batch start
    equals what `should_holdout(counter + i)` produces per leaf during
    sequential dispatch — proof that the per-batch semantic and the
    sequential implementation agree (per Piece 2 go-ahead note 4.3)."""
    author_resolver(
        "test-predictor",
        implementation="tests.factory._predictor_resolver:predict",
    )
    author_resolver(
        "test-ground-truth",
        implementation="tests.factory._fake_resolvers:simple_resolve_with_adapter",
    )
    # Holdout every other decision (rate=0.5 → cycle of 2 → counters
    # 0, 2, 4, ... are holdouts).
    author_calibration_policy(
        "rate-half",
        applies_to_scope="test-scope",
        applies_to_domain=None,
        predictor="test-predictor",
        ground_truth_resolver="test-ground-truth",
        holdout_rate=0.5,
    )
    # Author 4 leaves; deterministically sorted, positions are 0..3.
    for i in range(4):
        author_intention(f"leaf-{i}")

    summary = tick(initialized, "test-scope", domain="test/domain")

    # Read the batch.start marker — it carries the precomputed
    # holdout decisions.
    events = _read_events(initialized)
    marker = next(e for e in events if e.get("event_type") == "factory.batch.start")
    precomputed = marker["intention"]["holdout_decisions"]

    # Independently compute what should_holdout would say for each
    # position using a fresh count_prior_decisions=0 baseline (this
    # is the first batch in a fresh repo).
    policy_fm = calibration.find_active_policy(
        initialized,
        {"scope": "test-scope", "domain": "test/domain"},
    )
    expected = {}
    for i, leaf_id in enumerate(sorted(f"leaf-{j}" for j in range(4))):
        expected[leaf_id] = calibration.should_holdout(
            policy_fm, "test-scope", None, 0 + i
        )

    assert precomputed == expected
    # rate=0.5 → cycle 2, counters 0+0 and 0+2 are holdouts → leaf-0
    # and leaf-2 are holdouts.
    assert expected == {
        "leaf-0": True,
        "leaf-1": False,
        "leaf-2": True,
        "leaf-3": False,
    }
    # Tick's summary mirrors the marker's decisions.
    assert summary["holdout_decisions"] == precomputed


def test_batch_id_unique_per_tick(
    initialized,
    author_resolver,
    author_intention,
):
    """Each tick generates a fresh batch_id; markers don't collide."""
    author_resolver(
        "r1",
        implementation="tests.factory._fake_resolvers:simple_resolve_with_adapter",
    )
    author_intention("first")
    author_intention("second", depends_on=["first"])

    s1 = tick(initialized, "test-scope", domain="test/domain")
    s2 = tick(initialized, "test-scope", domain="test/domain")
    assert s1["batch_id"] != s2["batch_id"]
    events = _read_events(initialized)
    markers = [e for e in events if e.get("event_type") == "factory.batch.start"]
    batch_ids = {m["intention"]["batch_id"] for m in markers}
    assert {s1["batch_id"], s2["batch_id"]} <= batch_ids
