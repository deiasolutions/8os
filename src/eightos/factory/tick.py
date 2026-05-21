"""Factory tick — single entry point for one walk + one batch of dispatches.

Block 3 Piece 2 (rewritten from Piece 1). `tick(repo_root, scope, *,
domain=None)` walks leaves, dispatches predictors when an active
calibration policy applies (Shape 1), runs the selector to pick a
resolver per leaf, dispatches the selected resolver via the
two-case dispatcher (Shape 5 from Piece 1), and authors the
resolution via `kernel.ir.resolve`. Per-tick context (repo,
batch_id) is set in `factory.context` so inside resolvers can
access them without signature drift.

Shape 1 (predictor dispatch): when the leaf is in a scope/domain
with an active calibration policy, the policy's predictor is
dispatched as a pre-phase (before the selector consultation). Its
output is authored as a `_kernel.prediction` (I, R) via the SDK so
that the selector's `find_latest_prediction` can pick it up during
VOI consultation.

Shape 2 (per-batch holdout + batch_id markers): a `batch_id` is
generated per tick. At batch start, the factory writes a
`factory.batch.start` tier 3 event carrying batch_id, leaves list,
and pre-computed holdout decisions. Replay groups selector events
between consecutive markers into the batch. Sequential dispatch
within the batch keeps the existing selector's `count_prior_decisions`
walk consistent with the precomputed decisions; parallel dispatch
(future block) will use the precomputed map directly.

Strategy short-circuit: when the selector returns the predictor as
`selected_resolver_id` (predict-only / predict-then-conditional-
escalate strategies), the factory does NOT re-dispatch the predictor
— the prediction (I, R) was already authored in the pre-phase. The
factory calls `kernel.ir.resolve` with the prediction's text and the
predictor as `resolver_id`, using the prediction's cost vector.
Re-dispatch would author two prediction records for one logical
decision, corrupting the calibration corpus.

Per-leaf failures are caught into the summary's `dispatched` list
with `ok: False`. The tick does not raise on individual failure;
the caller decides whether to continue or abort the loop.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import KERNEL_BINARY_RESOLVER_ID, calibration
from .._atomic import append_jsonl_line
from .._events import make_event
from .._paths import event_jsonl_path
from .._time import now_iso
from .._ulid import new_ulid
from ..sdk._runner import run as run_op
from . import context
from .dispatcher import dispatch
from .materializer import extract_prism_resolver, materialize
from .registry import FactoryError, Registry
from .walker import find_dispatchable_leaves

_BATCH_MARKER_RESOLVER_ID = "factory.batch-marker"


def tick(
    repo_root: Path | str,
    scope: str,
    *,
    domain: str | None = None,
) -> dict[str, Any]:
    """One tick = one walk + one batch of dispatches.

    Args:
        repo_root: path to the 8os repo root.
        scope: scope name (e.g., "kernel", "test-scope").
        domain: optional override for the domain passed to
            `kernel.selector.select`. Defaults to the leaf's `domain`
            frontmatter field if present, else the empty string.

    Returns a summary dict:
        {
            "scope": <scope>,
            "batch_id": <ULID>,
            "leaves_found": <int>,
            "dispatched": [
                {
                    "intention_id": <id>,
                    "resolver_id": <id|None>,
                    "ok": <bool>,
                    "predicted": <bool>,  # True if a prediction was authored
                    "short_circuited": <bool>,  # True if used the prediction directly
                    "materialized_children": <int>?,  # graph-producing branch only
                    "error": <str>?,  # only present when ok is False
                },
                ...
            ],
            "holdout_decisions": {<intention_id>: <bool>, ...},
        }
    """
    repo = Path(repo_root)
    batch_id = new_ulid()
    context.set_repo(repo)
    context.set_batch_id(batch_id)
    try:
        leaves = find_dispatchable_leaves(repo, scope)
        # Deterministic ordering — required for replay determinism and for
        # the per-batch holdout assignment to be reproducible.
        leaves.sort(key=lambda r: r.frontmatter.get("id") or "")

        # Pre-compute per-batch holdout decisions before any dispatch
        # (Shape 2). Sequential dispatch happens to compute equivalent
        # decisions because count_prior_decisions walks events including
        # those just written in the batch — but we precompute and write
        # the marker so replay can reconstruct independently of dispatch
        # ordering, and so future parallel dispatch has the canonical
        # decision set already in hand.
        holdout_decisions = _compute_batch_holdouts(repo, leaves)

        _write_batch_start_marker(repo, batch_id, scope, leaves, holdout_decisions)

        registry = Registry(repo)
        dispatched: list[dict[str, Any]] = []

        for leaf in leaves:
            dispatched.append(_dispatch_one(leaf, registry, repo, domain))

        return {
            "scope": scope,
            "batch_id": batch_id,
            "leaves_found": len(leaves),
            "dispatched": dispatched,
            "holdout_decisions": holdout_decisions,
        }
    finally:
        context.clear()


def _dispatch_one(
    leaf,
    registry: Registry,
    repo: Path,
    domain_override: str | None,
) -> dict[str, Any]:
    """Predictor pre-phase + selector consult + strategy execution for one leaf."""
    intention_id = leaf.frontmatter["id"]
    leaf_domain = (
        domain_override
        if domain_override is not None
        else (
            leaf.frontmatter.get("domain")
            or extract_prism_resolver(leaf.intention_text)
            or ""
        )
    )

    result: dict[str, Any] = {
        "intention_id": intention_id,
        "resolver_id": None,
        "ok": False,
        "predicted": False,
        "short_circuited": False,
    }

    try:
        # Shape 1: predictor pre-phase. If an active calibration policy
        # applies for this leaf, dispatch the policy's predictor before
        # the selector consultation so VOI sees a fresh prediction.
        policy_fm = calibration.find_active_policy(repo, leaf.frontmatter)
        predictor_id = (policy_fm or {}).get("predictor") if policy_fm else None
        prediction_adapted: dict[str, Any] | None = None

        if predictor_id:
            predictor_entry = registry.get(predictor_id)
            prediction_adapted = dispatch(predictor_entry, leaf, repo)
            _author_prediction(repo, intention_id, predictor_id, prediction_adapted)
            result["predicted"] = True

        # Selector consultation — picks the resolver per the kernel's v1.0
        # selection rules (capability + demands + VOI when policy active).
        selector_env = run_op(
            "kernel.selector.select",
            {"for_ir_id": intention_id, "domain": leaf_domain},
        )
        selected = selector_env["data"]["selected_resolver_id"]
        result["resolver_id"] = selected

        if selected is None:
            raise FactoryError(
                f"selector returned null for {intention_id!r} "
                f"(no resolver in pool matched the demands)"
            )

        # Strategy short-circuit (the "use the prediction directly"
        # path). When selector picks the predictor, do not re-dispatch:
        # use the prediction we just authored as the resolution.
        if predictor_id and selected == predictor_id and prediction_adapted is not None:
            _resolve_with_prediction(
                intention_id, predictor_id, prediction_adapted
            )
            result["short_circuited"] = True
            result["ok"] = True
            return result

        # Standard ground-truth dispatch.
        selected_entry = registry.get(selected)
        adapted = dispatch(selected_entry, leaf, repo)

        if selected_entry.produces == "graph":
            # Block 3 Piece 5 — graph-producing branch (pattern β).
            # The selected resolver returned a graph spec instead of a
            # value; materialize it as children under this leaf via
            # `kernel.ir.expand` + per-child `kernel.ir.new`. The walker's
            # `expanded_into is None` filter ensures this leaf isn't
            # re-dispatched on the next tick. Parent stays open +
            # expanded; children dispatch in subsequent ticks. Piece 6's
            # recomposer will compose children's resolutions into the
            # parent's resolution as a follow-on supersession.
            graph_spec = adapted.get("resolution_value") or {"nodes": []}
            leaf_scope = leaf.frontmatter.get("scope") or ""
            authored_count = len(
                materialize(
                    graph_spec,
                    scope_id=leaf_scope,
                    authored_by=selected,
                    authored_via=selected_entry.bridge or "outside",
                    parent_id=intention_id,
                )
            )
            result["materialized_children"] = authored_count
            result["ok"] = True
            return result

        resolve_payload: dict[str, Any] = {
            "ir_id": intention_id,
            "resolver_id": selected,
            "resolution_text": adapted["resolution_text"],
            "cost_actual": adapted["cost_actual"],
        }
        if selected_entry.bridge is not None:
            resolve_payload["bridge_id"] = selected_entry.bridge
        if selected_entry.standing_authorization is not None:
            resolve_payload["authorization_id"] = selected_entry.standing_authorization
        run_op("kernel.ir.resolve", resolve_payload)
        result["ok"] = True
    except Exception as e:  # noqa: BLE001 - per-leaf isolation is intentional
        result["error"] = f"{type(e).__name__}: {e}"
    return result


def _author_prediction(
    repo: Path,
    subject_intention_id: str,
    predictor_id: str,
    prediction_adapted: dict[str, Any],
) -> str:
    """Author a `_kernel.prediction` (I, R) via the SDK from a predictor's adapted output.

    The adapter convention's optional `probability` field is honored
    when present (per-resolver adapter contract extension). Returns
    the prediction record's id.
    """
    pred_id = f"pred-{subject_intention_id}-{new_ulid()[-12:].lower()}"
    extensions: dict[str, Any] = {
        "subject_intention": subject_intention_id,
        "predicted_resolution": prediction_adapted.get("resolution_value"),
        "probability": prediction_adapted.get("probability"),
        "predictor": predictor_id,
    }
    intention_text = prediction_adapted.get("resolution_text") or (
        f"Prediction for {subject_intention_id} by {predictor_id}."
    )
    # The intention's scope is taken from the subject intention; the
    # SDK runner reads scope_id from the input.
    subject_scope = _read_intention_scope(repo, subject_intention_id) or "_kernel"
    run_op(
        "kernel.ir.new",
        {
            "scope_id": subject_scope,
            "slug": pred_id,
            "tier": 1,
            "intention_text": intention_text,
            "projection_types": ["_kernel.prediction"],
            "authority_level": "convention",
            "authored_by": predictor_id,
            "authored_via": "outside",
            "frontmatter_extensions": extensions,
        },
    )
    return pred_id


def _read_intention_scope(repo: Path, intention_id: str) -> str | None:
    """Look up the intention's scope via the id-to-path index."""
    from .._yaml import load_yaml_file

    idx = load_yaml_file(repo / ".8os" / "index" / "id-to-path.yml") or {}
    rel = idx.get(intention_id)
    if not rel:
        return None
    parts = Path(rel).parts
    # ir/<scope>/.../<file>.md — second part is scope.
    if len(parts) >= 2 and parts[0] == "ir":
        return parts[1]
    return None


def _resolve_with_prediction(
    intention_id: str,
    predictor_id: str,
    prediction_adapted: dict[str, Any],
) -> None:
    """Call kernel.ir.resolve using the prediction as the resolution.

    Avoids re-dispatching the predictor when the selector's strategy
    short-circuits to predict-only / predict-then-conditional-escalate.
    The cost vector is the prediction's own cost (captured when the
    predictor ran in the pre-phase); resolution_text comes from the
    predictor's adapter.
    """
    run_op(
        "kernel.ir.resolve",
        {
            "ir_id": intention_id,
            "resolver_id": predictor_id,
            "resolution_text": prediction_adapted["resolution_text"],
            "cost_actual": prediction_adapted["cost_actual"],
        },
    )


def _compute_batch_holdouts(
    repo: Path,
    leaves: list,
) -> dict[str, bool]:
    """Pre-compute per-batch holdout decisions (Shape 2).

    For each leaf in the deterministically-sorted batch, look up the
    leaf's active policy and compute `should_holdout(counter + i)`
    where `counter` is `count_prior_decisions(...)` at batch start
    and `i` is the leaf's position-within-policy in the batch
    (zero-indexed). For leaves with no active policy, the entry is
    False.

    The result is the canonical per-batch decision map. Sequential
    dispatch happens to compute equivalent decisions because the
    selector's own `count_prior_decisions` walks events including
    those just written in the batch. Parallel dispatch (future) will
    consult this map directly.
    """
    decisions: dict[str, bool] = {}
    counter_cache: dict[tuple, int] = {}
    policy_position: dict[tuple, int] = {}

    for leaf in leaves:
        intention_id = leaf.frontmatter.get("id") or ""
        policy_fm = calibration.find_active_policy(repo, leaf.frontmatter)
        if not policy_fm:
            decisions[intention_id] = False
            continue
        policy_id = (
            policy_fm.get("id") or policy_fm.get("policy_id") or ""
        )
        scope = leaf.frontmatter.get("scope") or ""
        p_domain = policy_fm.get("applies_to_domain")
        key = (policy_id, scope, p_domain)
        if key not in counter_cache:
            counter_cache[key] = calibration.count_prior_decisions(
                repo, policy_id, scope, p_domain
            )
        offset = policy_position.get(key, 0)
        is_holdout = calibration.should_holdout(
            policy_fm, scope, p_domain, counter_cache[key] + offset
        )
        decisions[intention_id] = is_holdout
        policy_position[key] = offset + 1
    return decisions


def _write_batch_start_marker(
    repo: Path,
    batch_id: str,
    scope: str,
    leaves: list,
    holdout_decisions: dict[str, bool],
) -> None:
    """Write a `factory.batch.start` tier 3 event.

    The marker is the replay anchor: any selector events authored
    between two consecutive markers belong to the bracketed batch.
    The intention dict carries batch_id, leaves, and holdout
    decisions so the batch is fully reconstructible from the event
    log alone. No joins required.

    The marker's resolver_id is `factory.batch-marker@<kernel-version>`
    — the factory is a kernel-binary-shipped layer and shares the
    binary's version string for now. If/when the factory ships
    independently of the kernel, this gets its own version namespace.
    """
    leaf_ids = [r.frontmatter.get("id") for r in leaves]
    ts = now_iso()
    intention = {
        "text": (
            f"Factory batch start: scope={scope!r}, batch_id={batch_id!r}, "
            f"leaves={len(leaf_ids)}, holdouts="
            f"{sum(1 for v in holdout_decisions.values() if v)}"
        ),
        "scope": "_ops",
        "depth": 0,
        "batch_id": batch_id,
        "factory_scope": scope,
        "leaves": leaf_ids,
        "holdout_decisions": holdout_decisions,
    }
    resolution = {
        "text": "Marker event; no work performed. Subsequent selector "
        "events through the next marker (or end-of-log) belong to this batch.",
        "authority_level": "convention",
    }
    kernel_ver = KERNEL_BINARY_RESOLVER_ID.split("@", 1)[-1]
    event = make_event(
        event_type="factory.batch.start",
        ir_node_id=batch_id,
        ir_node_path_at_event="<n/a — factory marker>",
        resolver_id=f"{_BATCH_MARKER_RESOLVER_ID}@{kernel_ver}",
        bridge_id=None,
        intention=intention,
        resolution=resolution,
        cost_actual={
            "clock_ms": 0,
            "coin_usd": 0,
            "carbon_g": 0,
            "model_name": None,
            "tokens_in": None,
            "tokens_out": None,
        },
        outcome="accepted",
        ts=ts,
    )
    append_jsonl_line(event_jsonl_path(repo, ts), event)


__all__ = ["FactoryError", "tick"]
