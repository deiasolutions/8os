"""kernel.selector.select — pick a resolver for an (I, R).

v0.2 §7.6.14 + v1.0 §5.1: the selector reads resolver cost and capability
vectors and picks per axiom 5. v1.0 extends the selector with prediction-
economics behavior:

- When an active calibration policy declares a predictor for the
  intention's scope+domain, consult `kernel.voi`. The VOI recommendation
  drives strategy choice: predict-only / predict-then-conditional-escalate /
  escalate-directly / run-both-with-comparison.
- When the policy's `holdout_rate` says the current decision is a sampled
  holdout, override VOI with `run-both-with-comparison`.
- When the chosen resolver has `cost_model: linear-in-depth`, pick a
  `depth_budget` from its declared coarse grid.
- The tier 3 selection event carries `voi_consultation` (when consulted)
  and `escalation_purpose` (per v1.0 §6.2/§6.3).
- Purpose-partitioned budgets are tracked via the `escalation_purpose`
  field on tier 3 events; standing authorizations may declare per-purpose
  budgets and the selector refuses dispatches that would exceed them
  (advisory in v1.0 absent runtime invocation; recorded for audit).
"""

from __future__ import annotations

from typing import Any

from .. import calibration, voi
from .._atomic import StagedFile, append_jsonl_line, commit_staged
from .._events import make_event
from .._frontmatter import IRRecord, parse_file, serialize
from .._indexes import write_all
from .._paths import event_jsonl_path, kernel_category_dir, ops_category_dir
from .._time import now_iso
from .._yaml import load_yaml_file
from ..errors import NOT_FOUND, KernelError
from ._common import repo_root_or_raise
from .ir_ops import _ensure_ops_scope


def run(payload: dict[str, Any]) -> dict[str, Any]:
    repo = repo_root_or_raise()
    for_ir = payload["for_ir_id"]
    domain = payload["domain"]
    demands = payload.get("demands") or {}
    candidates = payload.get("candidate_resolver_ids")

    base = kernel_category_dir(repo, "resolver")
    if not base.exists():
        raise KernelError(NOT_FOUND, "no resolvers registered (ir/_kernel/resolver/ missing)")

    pool: list[dict[str, Any]] = []
    for md in sorted(base.glob("*.md")):
        if md.name.startswith("_"):
            continue
        fm = parse_file(md).frontmatter
        if candidates and fm.get("id") not in candidates:
            continue
        pool.append(fm)

    scored: list[dict[str, Any]] = []
    for r in pool:
        score, breakdown = _fitness(r, domain, demands)
        scored.append({"resolver_id": r["id"], "score": score, "breakdown": breakdown})
    scored.sort(key=lambda s: s["score"], reverse=True)

    selected = scored[0]["resolver_id"] if scored and scored[0]["score"] > float("-inf") else None

    # ---- v1.0 §5.1: VOI consultation when an active calibration policy applies
    intention_fm = _load_intention_fm(repo, for_ir)
    voi_consultation: dict[str, Any] | None = None
    escalation_purpose = "none"
    depth_budget: int | None = None

    policy_fm = (
        calibration.find_active_policy(repo, intention_fm) if intention_fm else None
    )
    if policy_fm is not None:
        predictor_id = policy_fm.get("predictor")
        gt_resolver_id = policy_fm.get("ground_truth_resolver")
        predictor_fm = (
            calibration.load_resolver_fm(repo, predictor_id) if predictor_id else None
        )
        gt_resolver_fm = (
            calibration.load_resolver_fm(repo, gt_resolver_id) if gt_resolver_id else None
        )
        prediction_fm = (
            calibration.find_latest_prediction(repo, for_ir, predictor_id)
            if predictor_id
            else None
        )

        if prediction_fm and predictor_fm and gt_resolver_fm:
            scope_fm = calibration.load_scope_fm(repo, intention_fm.get("scope") or "")
            voi_result = voi.consult(
                prediction_fm=prediction_fm,
                predictor_resolver_fm=predictor_fm,
                ground_truth_resolver_fm=gt_resolver_fm,
                intention_fm=intention_fm,
                scope_fm=scope_fm,
                policy_fm=policy_fm,
            )
            recommended = voi_result["recommended_strategy"]

            # Holdout sampling overrides VOI per §5.1.
            counter = calibration.count_prior_decisions(
                repo,
                policy_fm.get("id") or policy_fm.get("policy_id") or "",
                intention_fm.get("scope") or "",
                policy_fm.get("applies_to_domain"),
            )
            is_holdout = calibration.should_holdout(
                policy_fm,
                intention_fm.get("scope") or "",
                policy_fm.get("applies_to_domain"),
                counter,
            )
            effective_strategy = (
                "run-both-with-comparison" if is_holdout else recommended
            )

            # Strategy → resolver choice.
            if effective_strategy == "predict-only":
                selected = predictor_id
                escalation_purpose = "none"
            elif effective_strategy == "escalate-directly":
                selected = gt_resolver_id
                escalation_purpose = "decision"
            elif effective_strategy == "run-both-with-comparison":
                selected = gt_resolver_id
                escalation_purpose = "holdout" if is_holdout else "decision"
            elif effective_strategy == "predict-then-conditional-escalate":
                # v1.0 records the predictor as the immediate selection;
                # conditional escalation is the caller's runtime decision.
                selected = predictor_id
                escalation_purpose = "none"

            voi_consultation = {
                "policy_id": policy_fm.get("id") or policy_fm.get("policy_id"),
                "prediction_id": prediction_fm.get("id"),
                "predictor_id": predictor_id,
                "ground_truth_resolver_id": gt_resolver_id,
                "voi_output": voi_result,
                "is_holdout": is_holdout,
                "effective_strategy": effective_strategy,
            }

            # Depth budget when the chosen resolver is linear-in-depth.
            chosen_fm = predictor_fm if selected == predictor_id else gt_resolver_fm
            if chosen_fm and chosen_fm.get("cost_model") == "linear-in-depth":
                depth_budget = calibration.pick_depth_budget(
                    chosen_fm,
                    voi_recommendation=voi_result,
                    escalation_budget=demands.get("max_coin_usd"),
                )

    ts = now_iso()
    _ensure_ops_scope(repo, "kernel", ts)
    sel_id = f"sel-{_compact_ts(ts)}"
    target = ops_category_dir(repo, "resolver-selection") / f"{sel_id}.md"
    selection_block: dict[str, Any] = {
        "for_ir": for_ir,
        "domain": domain,
        "demands": demands,
        "selected_resolver_id": selected,
        "fitness_scores": scored,
    }
    if voi_consultation is not None:
        selection_block["voi_consultation"] = voi_consultation
    if depth_budget is not None:
        selection_block["depth_budget"] = depth_budget
    if escalation_purpose != "none" or voi_consultation is not None:
        selection_block["escalation_purpose"] = escalation_purpose
    record = IRRecord(
        frontmatter={
            "id": sel_id,
            "kind": "ir-node",
            "tier": 2,
            "projection_types": ["_kernel.resolver-selection"],
            "collapsed_summary": f"Select resolver for {for_ir!r} in domain {domain!r}",
            "expanded_into": None,
            "parent": None,
            "scope": "_ops",
            "depends_on": [for_ir],
            "visible_to": ["_ops"],
            "resolved_at": ts,
            "valid_through": None,
            "revalidate_trigger": None,
            "status": "resolved",
            "resolver": "kernel",
            "resolution_event": None,
            "authored_by": "kernel",
            "authored_on": ts,
            "authority_level": "convention",
            # v1.0.1-partial Amendment 2: kernel-internal ops author through
            # the kernel.self cogito bridge.
            "authored_via": "kernel.self",
            "supersedes": None,
            "superseded_by": None,
            "surrogate_of": None,
            "selection": selection_block,
        },
        intention_text=f"Select a resolver for (I, R) {for_ir!r} in domain {domain!r}.",
        resolution_text=(
            f"Selected {selected!r}." if selected else "No candidate satisfies demands."
        ),
    )

    op_event = make_event(
        event_type="operation",
        ir_node_id=sel_id,
        ir_node_path_at_event=str(target.relative_to(repo)),
        resolver_id="kernel",
        bridge_id=None,
        intention={
            "text": f"Resolver selection for {for_ir!r}",
            "context_refs": [for_ir],
            "scope": (intention_fm or {}).get("scope") or "_ops",
            "domain": domain,
            "depth": 0,
        },
        resolution={
            "text": f"Selected {selected!r}" if selected else "No candidate selected",
            "structured": {
                "selected": selected,
                "fitness_scores": scored,
                "depth_budget": depth_budget,
            },
            "authority_level": "convention",
        },
        outcome="accepted",
        ts=ts,
        escalation_purpose=escalation_purpose if voi_consultation else None,
        voi_consultation=voi_consultation,
    )

    commit_staged([StagedFile(target, content_text=serialize(record))])
    append_jsonl_line(event_jsonl_path(repo, ts), op_event)
    write_all(repo)
    return {
        "data": {
            "selected_resolver_id": selected,
            "selection_ir_id": sel_id,
            "selection_path": str(target.relative_to(repo)),
            "fitness_scores": scored,
            "voi_consultation": voi_consultation,
            "depth_budget": depth_budget,
            "escalation_purpose": (
                escalation_purpose if voi_consultation is not None else None
            ),
        },
        "event_id": op_event["event_id"],
        "indexes_updated": [
            "id-to-path",
            "path-to-id",
            "scope-to-ids",
            "tier-to-ids",
            "projection-to-ids",
            "deps-forward",
            "deps-reverse",
            "_checksum",
        ],
    }


def _load_intention_fm(repo, ir_id: str) -> dict[str, Any] | None:
    """Load the subject (I, R)'s frontmatter so the selector can read its
    scope, stakes, and any domain hints. Returns None if the (I, R) is not
    found (the v0.2 selector accepts any string for `for_ir_id` and never
    de-references it; v1.0 looks it up best-effort)."""
    idx = load_yaml_file(repo / ".8os" / "index" / "id-to-path.yml") or {}
    rel = idx.get(ir_id)
    if not rel or "#L" in rel:
        return None
    try:
        return parse_file(repo / rel).frontmatter
    except Exception:
        return None


def _fitness(resolver_fm: dict[str, Any], domain: str, demands: dict[str, Any]) -> tuple[float, dict[str, float]]:
    """v0.2 fitness over a resolver's projection-extension frontmatter.

    Reads the `capability` and `cost` fields written by `_kernel.resolver`
    projection-declared frontmatter. A real selector lives in a future block;
    this is the registered seam.
    """
    capability = resolver_fm.get("capability") or {}
    domain_caps = capability.get(domain) if isinstance(capability, dict) else None
    if domain_caps is None:
        return float("-inf"), {"sigma_match": 0.0, "cost_pressure": 0.0, "availability": 0.0}

    sigma_block = domain_caps.get("sigma") or {}
    sigma = sigma_block.get("measured")
    if sigma is None:
        sigma = sigma_block.get("declared") or 0.5
    min_sigma = demands.get("min_sigma")
    if min_sigma is not None and sigma < min_sigma:
        return float("-inf"), {"sigma_match": sigma, "cost_pressure": 0.0, "availability": 0.0}

    cost = resolver_fm.get("cost") or {}
    coin = float(cost.get("coin_usd") or 0.0)
    max_coin = demands.get("max_coin_usd")
    if max_coin is not None and coin > max_coin:
        return float("-inf"), {"sigma_match": sigma, "cost_pressure": coin, "availability": 0.0}

    breakdown = {
        "sigma_match": float(sigma),
        "cost_pressure": float(coin),
        "availability": 1.0,
    }
    score = float(sigma) - 0.1 * float(coin)
    return score, breakdown


def _compact_ts(ts: str) -> str:
    """Trim ISO timestamp punctuation for use in slugs."""
    return ts.replace(":", "").replace("-", "").replace(".", "").rstrip("Z").lower()
