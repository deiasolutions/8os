"""Shared calibration / prediction-economics helpers (v1.0 §3, §5).

Used by:
- `kernel.selector.select` to find the active calibration policy for an
  intention, consult VOI, decide holdout, pick depth budget.
- `kernel.ir.new` to check standing authorizations against incoming
  calibration-policy-proposals and auto-dispatch the calibrator's
  approval supersession when conditions match.

This module is plumbing — no operations live here. Operations live in
`eightos.sdk.*_op.py` and call into this module.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ._frontmatter import parse_file
from ._paths import ir_dir, kernel_record_path
from ._yaml import load_yaml_file


def resolve_domain(
    intention_fm: dict[str, Any],
    scope_fm: dict[str, Any] | None,
) -> str | None:
    """Resolve the effective domain for an intention.

    v1.1 §4.3: record-level `domain` overrides scope's `domain_default`. When
    neither is declared, returns None. Parallel in shape to `_resolve_stakes`
    in voi.py.
    """
    record_domain = intention_fm.get("domain")
    if record_domain is not None:
        return record_domain
    return (scope_fm or {}).get("domain_default")


def resolve_data_classification(
    intention_fm: dict[str, Any],
    scope_fm: dict[str, Any] | None,
) -> str | None:
    """Resolve the effective data_classification for an intention.

    v1.1 §4.2 (Block 4.3): record-level `data_classification` overrides the
    scope's `data_classification_default`. When neither is declared, returns
    None — meaning no classification applies and classification-based
    policies do not match. Parallel in shape to `resolve_domain`.
    """
    record_classification = intention_fm.get("data_classification")
    if record_classification is not None:
        return record_classification
    return (scope_fm or {}).get("data_classification_default")


def find_active_policy(
    repo: Path,
    intention_fm: dict[str, Any],
) -> dict[str, Any] | None:
    """Return the calibration policy active for the intention's scope+domain.

    Scope match is exact. Domain match: a policy with `applies_to_domain: null`
    matches any domain; a policy with a specific domain matches only that
    domain. The intention's effective domain is its record-level `domain` if
    declared, else the scope's `domain_default`, else null (v1.1 §4.3).
    Latest non-superseded policy wins.

    Returns the policy's frontmatter dict, or None when no policy applies.
    """
    scope = intention_fm.get("scope")
    if not scope:
        return None
    scope_fm = load_scope_fm(repo, scope)
    domain = resolve_domain(intention_fm, scope_fm)
    candidates: list[dict[str, Any]] = []
    for fm in _all_policies(repo):
        if fm.get("status") == "superseded":
            continue
        if fm.get("applies_to_scope") != scope:
            continue
        p_domain = fm.get("applies_to_domain")
        if p_domain is not None and p_domain != domain:
            continue
        candidates.append(fm)
    if not candidates:
        return None
    candidates.sort(
        key=lambda p: (p.get("authored_on") or "", p.get("id") or ""),
        reverse=True,
    )
    return candidates[0]


def find_latest_prediction(
    repo: Path,
    subject_intention_id: str,
    predictor_id: str,
) -> dict[str, Any] | None:
    """Return the latest non-superseded prediction (I, R) for a subject by predictor.

    v1.0 §5.1: when consulting VOI, the selector uses the predictor's most-
    recent prediction or freshly authors one if none exists. v1.0's selector
    consultation only reads existing predictions; auto-authoring a fresh
    prediction is left to the caller (typically a Block 3 dispatch loop).
    """
    candidates: list[dict[str, Any]] = []
    for fm in _all_predictions(repo):
        if fm.get("status") == "superseded":
            continue
        if fm.get("subject_intention") != subject_intention_id:
            continue
        if fm.get("predictor") != predictor_id:
            continue
        candidates.append(fm)
    if not candidates:
        return None
    candidates.sort(
        key=lambda p: (p.get("authored_on") or "", p.get("id") or ""),
        reverse=True,
    )
    return candidates[0]


def load_resolver_fm(repo: Path, resolver_id: str) -> dict[str, Any] | None:
    """Load a `_kernel.resolver` (I, R)'s frontmatter, or None if absent."""
    path = kernel_record_path(repo, "resolver", resolver_id)
    if not path.exists():
        return None
    return parse_file(path).frontmatter


def load_scope_fm(repo: Path, scope_id: str) -> dict[str, Any] | None:
    """Load a `_kernel.scope` (I, R)'s frontmatter, or None if absent."""
    path = kernel_record_path(repo, "scope", scope_id)
    if not path.exists():
        return None
    return parse_file(path).frontmatter


def should_holdout(
    policy_fm: dict[str, Any],
    scope: str,
    domain: str | None,
    counter: int,
) -> bool:
    """Deterministic holdout decision per v1.0 §5.1.

    Holdout sampling is mechanical: maintain a counter per (policy, scope,
    domain) and fire a holdout when `counter modulo (1 / holdout_rate)`
    hits zero. With holdout_rate = 0.2, every fifth decision is a holdout.

    holdout_rate = 0 → never holdout. holdout_rate = 1 → always holdout.
    For non-trivial fractional rates (0 < r < 1), the cycle length is
    `round(1 / r)`. Reproducible given the counter.
    """
    rate = policy_fm.get("holdout_rate")
    if rate is None:
        return False
    try:
        r = float(rate)
    except (TypeError, ValueError):
        return False
    if r <= 0:
        return False
    if r >= 1:
        return True
    cycle = max(1, round(1.0 / r))
    return (counter % cycle) == 0


def count_prior_decisions(
    repo: Path,
    policy_id: str,
    scope: str,
    domain: str | None,
) -> int:
    """Count tier 3 selector events that contributed to this policy's decision stream.

    Counts events with `voi_consultation.policy_id` matching policy_id and
    `intention.scope` matching scope. Domain matches when the policy declared
    a domain. Used to feed `should_holdout`'s counter argument so the holdout
    cycle is reproducible across reruns.
    """
    from ._events import iter_events

    n = 0
    for _path, _line, ev in iter_events(repo):
        consult = ev.get("voi_consultation") or {}
        if consult.get("policy_id") != policy_id:
            continue
        ev_scope = (ev.get("intention") or {}).get("scope")
        if ev_scope != scope:
            continue
        if domain is not None:
            ev_domain = (ev.get("intention") or {}).get("domain")
            if ev_domain != domain:
                continue
        n += 1
    return n


def pick_depth_budget(
    resolver_fm: dict[str, Any],
    voi_recommendation: dict[str, Any] | None = None,
    escalation_budget: float | None = None,
) -> int | None:
    """Pick a coarse-grid depth budget for a `cost_model: linear-in-depth` resolver.

    v1.0 §5.1: shallow / medium / deep at resolver-declared values
    (resolver's `depth_grid` field). Default heuristic: smallest grid point
    whose expected cost stays within the active escalation budget. If VOI's
    expected-value computation suggests deeper would change the recommendation,
    step up. Falls back to `medium` when no escalation_budget is declared.

    Returns the integer depth value, or None when the resolver does not use
    `cost_model: linear-in-depth`.
    """
    if resolver_fm.get("cost_model") != "linear-in-depth":
        return None
    grid = resolver_fm.get("depth_grid") or {}
    if not grid:
        # No grid declared: default to 1 unit.
        return 1
    shallow = grid.get("shallow")
    medium = grid.get("medium")
    deep = grid.get("deep")
    cost_per_unit = resolver_fm.get("cost_per_depth_unit") or {}
    coin_per_unit = float(cost_per_unit.get("coin_usd") or 0)

    def cost_at(depth: int) -> float:
        base = float((resolver_fm.get("cost") or {}).get("coin_usd") or 0)
        return base + coin_per_unit * depth

    if escalation_budget is not None:
        for level in (shallow, medium, deep):
            if level is None:
                continue
            if cost_at(int(level)) <= escalation_budget:
                return int(level)
        # No grid point fits — refuse by returning None; caller decides what
        # to do. Convention in v1.0: caller picks shallow as fallback.
        return int(shallow) if shallow is not None else 1

    # No budget declared: medium is the v1.0 default.
    if medium is not None:
        return int(medium)
    if shallow is not None:
        return int(shallow)
    return 1


def find_matching_authorization(
    repo: Path,
    proposal_fm: dict[str, Any],
) -> dict[str, Any] | None:
    """Find a standing authorization that pre-grants approval for this proposal.

    A standing authorization matches when:
      - `authorized_action == "supersede-calibration-policy"`
      - `authorized_subject` includes the proposal's `target_policy`
      - All conditions in the authorization's `conditions` list pass against
        the proposal's `proposed_changes` and `evidence_summary`

    Conditions in v1.0 are simple predicates (per v1.0 §3.4 example):
      - `{field, change_within: <delta>}` — proposed change to <field> stays
        within <delta> of the current value.
      - `{field, requires_min_observations: <N>}` — evidence_summary's
        observation_count >= N.
      - `{field, requires_p_value: <p>}` — evidence_summary's observed
        p_value <= p (lower is more significant).

    v1.0 implements these three predicate kinds. Future versions may extend
    the predicate vocabulary.
    """
    target_policy = proposal_fm.get("target_policy")
    if not target_policy:
        return None
    proposed = proposal_fm.get("proposed_changes") or {}
    evidence = proposal_fm.get("evidence_summary") or {}
    candidates = _all_authorizations(repo)
    for auth in candidates:
        if auth.get("authorized_action") != "supersede-calibration-policy":
            continue
        subject = auth.get("authorized_subject")
        if subject is None:
            continue
        subjects = subject if isinstance(subject, list) else [subject]
        if target_policy not in subjects:
            continue
        if not _conditions_pass(auth.get("conditions") or [], proposed, evidence, repo, target_policy):
            continue
        return auth
    return None


def _conditions_pass(
    conditions: list[Any],
    proposed_changes: dict[str, Any],
    evidence_summary: dict[str, Any],
    repo: Path,
    target_policy_id: str,
) -> bool:
    """Evaluate a list of condition predicates against proposal evidence.

    All conditions must pass. Unknown predicate kinds fail closed (don't
    match) so authorizations with unknown predicates can't accidentally
    grant approval.
    """
    if not conditions:
        return True
    target_policy_fm = _load_policy_by_id(repo, target_policy_id)
    for cond in conditions:
        if not isinstance(cond, dict):
            return False
        field = cond.get("field")
        if "change_within" in cond:
            delta = float(cond.get("change_within", 0))
            current = (target_policy_fm or {}).get(field)
            new = proposed_changes.get(field)
            if current is None or new is None:
                return False
            try:
                if abs(float(new) - float(current)) > delta:
                    return False
            except (TypeError, ValueError):
                return False
        elif "requires_min_observations" in cond:
            min_obs = int(cond.get("requires_min_observations", 0))
            obs = evidence_summary.get("observation_count")
            if obs is None or int(obs) < min_obs:
                return False
        elif "requires_p_value" in cond:
            max_p = float(cond.get("requires_p_value", 1.0))
            p = evidence_summary.get("p_value")
            if p is None or float(p) > max_p:
                return False
        else:
            return False  # unknown predicate kind — fail closed
    return True


def deterministic_seed(*parts: str) -> int:
    """Stable integer seed from a tuple of strings.

    Used by `should_holdout` callers to derive a counter when no event-log
    history exists yet (e.g., first decision under a new policy).
    """
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(h[:8], 16)


# ---- internals -------------------------------------------------------------


def _all_predictions(repo: Path) -> list[dict[str, Any]]:
    return _all_records_with_projection(repo, "_kernel.prediction")


def _all_policies(repo: Path) -> list[dict[str, Any]]:
    return _all_records_with_projection(repo, "_kernel.calibration-policy")


def _all_authorizations(repo: Path) -> list[dict[str, Any]]:
    return _all_records_with_projection(repo, "_kernel.authorization")


def _all_records_with_projection(repo: Path, projection_type: str) -> list[dict[str, Any]]:
    base = ir_dir(repo)
    if not base.exists():
        return []
    out: list[dict[str, Any]] = []
    for md in sorted(base.rglob("*.md")):
        try:
            rec = parse_file(md)
        except Exception:
            continue
        ptypes = rec.frontmatter.get("projection_types") or []
        if projection_type in ptypes:
            out.append(rec.frontmatter)
    return out


def _load_policy_by_id(repo: Path, policy_id: str) -> dict[str, Any] | None:
    idx = load_yaml_file(repo / ".8os" / "index" / "id-to-path.yml") or {}
    rel = idx.get(policy_id)
    if not rel or "#L" in rel:
        return None
    try:
        return parse_file(repo / rel).frontmatter
    except Exception:
        return None
