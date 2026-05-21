"""Shape 1 tests — predictor pre-phase + prediction (I, R) authoring."""

from __future__ import annotations

import json

from eightos.factory import tick


def _author_two_resolvers(author_resolver):
    """Author a predictor + ground-truth resolver pair for tests."""
    author_resolver(
        "test-predictor",
        bridge=None,
        implementation="tests.factory._predictor_resolver:predict",
    )
    author_resolver(
        "test-ground-truth",
        bridge=None,
        implementation="tests.factory._fake_resolvers:simple_resolve_with_adapter",
    )


def test_predictor_pre_phase_authors_prediction(
    initialized,
    author_resolver,
    author_intention,
    author_calibration_policy,
):
    """When a calibration policy is active, the predictor runs in the
    pre-phase and a `_kernel.prediction` (I, R) is authored before the
    selector consultation."""
    _author_two_resolvers(author_resolver)
    author_calibration_policy(
        "test-policy",
        applies_to_scope="test-scope",
        applies_to_domain=None,  # null = match any domain in scope
        predictor="test-predictor",
        ground_truth_resolver="test-ground-truth",
    )
    author_intention("subj-1")

    summary = tick(initialized, "test-scope", domain="test/domain")

    assert summary["dispatched"][0]["predicted"] is True
    # A prediction record should now exist in the scope's _predictions
    # subdirectory (per v1.0.1-partial target_subdirectory discipline).
    pred_dir = initialized / "ir" / "test-scope" / "_predictions"
    assert pred_dir.exists()
    pred_files = list(pred_dir.glob("*.prediction.md"))
    assert len(pred_files) == 1
    text = pred_files[0].read_text()
    assert "subject_intention: subj-1" in text
    assert "predictor: test-predictor" in text


def test_no_policy_skips_predictor_phase(
    initialized,
    author_resolver,
    author_intention,
):
    """No active calibration policy → no predictor dispatch → no
    prediction (I, R) authored."""
    author_resolver(
        "lone",
        implementation="tests.factory._fake_resolvers:simple_resolve_with_adapter",
    )
    author_intention("alone")
    summary = tick(initialized, "test-scope", domain="test/domain")
    assert summary["dispatched"][0]["predicted"] is False
    pred_dir = initialized / "ir" / "test-scope" / "_predictions"
    assert not pred_dir.exists() or not list(pred_dir.glob("*.prediction.md"))


def test_predictor_dispatched_before_selector(
    initialized,
    author_resolver,
    author_intention,
    author_calibration_policy,
):
    """Selector's voi_consultation should reference the prediction we
    just authored — confirming temporal ordering (predictor → selector)."""
    _author_two_resolvers(author_resolver)
    author_calibration_policy(
        "test-policy",
        applies_to_scope="test-scope",
        applies_to_domain=None,
        predictor="test-predictor",
        ground_truth_resolver="test-ground-truth",
    )
    author_intention("subj-2")
    tick(initialized, "test-scope", domain="test/domain")

    # Find the selector tier 3 event for subj-2.
    jsonl_paths = list((initialized / ".8os" / "events").rglob("*.jsonl"))
    assert jsonl_paths
    events = []
    for p in jsonl_paths:
        for ln in p.read_text().splitlines():
            if ln.strip():
                events.append(json.loads(ln))
    # Selector events have event_type=operation and ir_node_id =
    # selection record's id (sel-...), not the subject intention.
    # Filter by intention.context_refs containing the subject id.
    sel_events = [
        e for e in events
        if e.get("event_type") == "operation"
        and e.get("intention", {}).get("text", "").startswith("Resolver selection")
        and "subj-2" in (e.get("intention", {}).get("context_refs") or [])
    ]
    assert sel_events, "selector tier 3 event for subj-2 not found"
    voi = sel_events[-1].get("voi_consultation")
    assert voi is not None, (
        "voi_consultation absent — predictor dispatch may have run AFTER "
        "selector, or the policy didn't apply"
    )
    assert voi.get("predictor_id") == "test-predictor"
    assert voi.get("prediction_id"), "selector found no prediction to consult"
