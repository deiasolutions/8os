"""kernel.voi — value-of-information computation (v1.0 §4).

VOI is a vendored kernel-internal resolver: pure inside computation, near-zero
cost, deterministic given inputs. The resolver definition (I, R) is authored
by `kernel.self` at bootstrap (`ir/_kernel/resolver/kernel.voi.md`); this
module is the implementation the kernel calls when the selector consults VOI.

## Inputs

VOI is invoked with four pieces of context (v1.0 §4.1):

- The prediction (I, R), via its frontmatter — fields `predicted_resolution`,
  `probability` (or null for uncalibrated predictors), `predictor`, and
  optional `predictor_calibration`.
- The candidate ground-truth resolver, via its `_kernel.resolver` (I, R)
  frontmatter — fields `cost` (current, calibrator-maintained) and
  `capability` (per-domain σπαρ).
- The intention being predicted about, via its frontmatter — `stakes` if
  declared, otherwise scope `stakes_defaults` if declared, otherwise
  stakes-unknown per §3.7.
- The active calibration policy, via its frontmatter — `holdout_rate` (used
  by the selector, not VOI itself, per §4.3).

## Output

A structured value `{recommended_strategy, expected_value_predict_only,
expected_value_escalate, expected_value_run_both, rationale}` where
`recommended_strategy ∈ {predict-only, predict-then-conditional-escalate,
escalate-directly, run-both-with-comparison}`.

VOI does not implement holdout sampling. The selector consults VOI for the
recommendation and separately consults the policy for whether the current
decision is a sampled holdout per the policy's `holdout_rate`. If holdout,
the selector overrides VOI's recommendation with `run-both-with-comparison`.

## Reference math (v1.0 baseline; future versions may supersede)

The math below is documented as the *baseline* for v1.0 and is intentionally
simple — it produces sane recommendations on plausible inputs without
claiming optimality. Future versions can supersede the kernel.voi resolver
(I, R) with a refined implementation; the calibrator can also empirically
refine `kernel.voi`'s `rho` (reliability) capability vector if its
recommendations are observed to diverge from sovereign judgment.

### Stakes asymmetry

Decisions almost always have asymmetric loss between false positives and
false negatives. v1.0 captures both via `stakes.false_positive_cost` and
`stakes.false_negative_cost` — same shape, three-currency cost vectors
`{clock_ms, coin_usd, carbon_g}`. v1.0's reference math defaults to
`coin_usd` only when no policy weights are declared; this is a v1.0
simplification, not a permanent commitment. Future calibration policies may
declare per-currency weights, at which point the cost-aggregation step
becomes a weighted sum across currencies. (Reversibility and consequence-
scope adjust the effective stakes by multiplicative factors below.)

### Probability and calibration-error widening

The predictor reports a probability `p ∈ [0, 1]` with the prediction. Naively
treating `p` as the true posterior overcounts predictor confidence — the
predictor itself has a calibration error `E ∈ [0, 1]` (1 - σ from its
σπαρ on this domain). Calibration error of `E` widens the predictive
distribution: a reported `p = 0.85` with `E = 0.10` is treated as
`p ∈ [0.75, 0.95]`. v1.0 uses the conservative bound — when computing
expected loss for predict-only, use `p_low = max(0, p - E)` for the lower
side of the prediction's claim and `p_high = min(1, p + E)` for the upper
side. Specifically:

- Probability-of-false-positive (the prediction says "yes" but truth is
  "no") under predict-only is bounded above by `1 - p_low` (i.e., the worst
  the predictor's "yes" could be).
- Probability-of-false-negative is bounded above by `p_high` similarly.

This widening is the v1.0 reference; future versions may use richer
calibration models (per-decile reliability, per-domain calibration curves,
etc.) supplied through `predictor_calibration` references.

### Strategy expected values

Let `S_fp = stakes.false_positive_cost.coin_usd`, `S_fn =
stakes.false_negative_cost.coin_usd` (per v1.0 default), `C_pred =
predictor.cost.coin_usd`, and `C_gt = ground_truth_resolver.cost.coin_usd`.
Let `R_factor` be the reversibility multiplier (1.0 for `irreversible`,
0.5 for `reversible_within_<duration>`, 0.25 for `reversible`); let
`D_factor` be the consequence-scope multiplier (1.0 for `project`, 2.0
for `downstream`).

Expected losses (negative of expected values; lower is better):

```
EL_predict_only      = R_factor × D_factor × (
                         (1 - p_low) × S_fp +
                         p_high × S_fn
                       ) + C_pred
EL_escalate          = R_factor × D_factor × 0 + C_gt    (ground-truth assumed accurate)
EL_run_both          = R_factor × D_factor × 0 + C_pred + C_gt
EL_predict_then_cond = R_factor × D_factor × (
                         (1 - p_low) × S_fp × confidence_factor
                       ) + C_pred + C_gt × escalation_probability
```

where `confidence_factor` and `escalation_probability` are derived from the
predictor's confidence relative to a threshold (default 0.5 for v1.0). The
v1.0 reference uses a coarse heuristic: `escalation_probability = 1 - p`
for the conditional strategy, on the intuition that lower-confidence
predictions trigger more conditional escalations.

Expected values are the negatives of expected losses:
`EV_strategy = -EL_strategy`.

`recommended_strategy = argmax(EV)` (i.e., argmin(EL)).

### Stakes-unknown (§3.7)

If stakes are unknown — no `stakes` field on the intention, no
`stakes_defaults` on the scope — VOI returns
`recommended_strategy = escalate-directly` with
`rationale = "stakes-unknown-default"` and the four expected_value fields
populated with sentinels (`None`). This behavior is hard-coded in v1.0
and changes only via supersession of the `kernel.voi` resolver definition.

The principle: in the absence of information that justifies economizing on
authority, defer to the more authoritative source. See v1.0 §0.2 (bridge
sovereignties) and §3.7 (stakes-unknown defaults to escalate).

### Probability-null (uncalibrated predictors)

If `prediction.probability` is None, the predictor is uncalibrated — its
output is taken at face value. v1.0 treats this as `p = 1.0` (predictor's
output IS the resolution if predict-only is chosen) with `E = 0` (no
widening), which makes `EL_predict_only = C_pred` regardless of stakes.
This collapses VOI to a cost comparison: predict-only when predictor is
cheaper, escalate when ground-truth is cheaper. The recommendation is
honest about treating an uncalibrated probability as a deterministic claim.

## Cost-vector aggregation

v1.0's reference math aggregates the three-currency cost vector by reading
`coin_usd` only. This is a v1.0 default, NOT a permanent commitment.

Future versions may introduce CCC weighting policies — e.g., a calibration
policy that declares carbon costs ten times more salient than coin costs
for environmental-impact decisions, or one that prioritizes clock latency
for real-time decisions. The cost-aggregation step becomes a weighted sum:
`C_aggregated = w_clock × C.clock_ms + w_coin × C.coin_usd + w_carbon ×
C.carbon_g`. v1.0 ships with default weights `(0, 1, 0)` (coin only); the
weights become a configurable property of the active calibration policy
in a future block.
"""

from __future__ import annotations

from typing import Any


# Reversibility multiplier on effective stakes (v1.0 reference).
# Block 2.9 dogfood cycle 2 marker: this comment line is the subject
# change for cycle 2; tiny diff, neither test nor SDK paths touched.
_REVERSIBILITY_FACTOR: dict[str, float] = {
    "irreversible": 1.0,
    "reversible": 0.25,
}

# Consequence-scope multiplier on effective stakes (v1.0 reference).
_CONSEQUENCE_FACTOR: dict[str, float] = {
    "project": 1.0,
    "downstream": 2.0,
}


def consult(
    *,
    prediction_fm: dict[str, Any],
    predictor_resolver_fm: dict[str, Any],
    ground_truth_resolver_fm: dict[str, Any],
    intention_fm: dict[str, Any],
    scope_fm: dict[str, Any] | None = None,
    policy_fm: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute VOI recommendation given a prediction, resolvers, intention.

    Returns a dict with keys:
      - recommended_strategy: one of predict-only, predict-then-conditional-
        escalate, escalate-directly, run-both-with-comparison
      - expected_value_predict_only, expected_value_escalate,
        expected_value_run_both: numeric (or None for stakes-unknown)
      - rationale: short string describing why this strategy was picked

    The selector applies holdout sampling separately per the active policy's
    `holdout_rate`; VOI does not implement holdouts itself (v1.0 §4.3).

    Determinism: VOI's output is a pure function of its inputs. Two calls
    with the same frontmatters produce the same output.
    """
    stakes = _resolve_stakes(intention_fm, scope_fm)
    if stakes is None:
        return {
            "recommended_strategy": "escalate-directly",
            "expected_value_predict_only": None,
            "expected_value_escalate": None,
            "expected_value_run_both": None,
            "rationale": "stakes-unknown-default",
        }

    fp_cost = _coin(stakes.get("false_positive_cost"))
    fn_cost = _coin(stakes.get("false_negative_cost"))
    rev_factor = _reversibility_factor(stakes.get("reversibility"))
    scope_factor = _CONSEQUENCE_FACTOR.get(stakes.get("consequence_scope") or "project", 1.0)
    risk_factor = rev_factor * scope_factor

    predictor_cost = _coin(predictor_resolver_fm.get("cost"))
    gt_cost = _coin(ground_truth_resolver_fm.get("cost"))

    probability = prediction_fm.get("probability")
    calibration_error = _calibration_error(predictor_resolver_fm)

    # Stakes-known, probability-null: treat as deterministic claim.
    if probability is None:
        ev_predict_only = -predictor_cost
        ev_escalate = -gt_cost
        ev_run_both = -(predictor_cost + gt_cost)
        ev_conditional = ev_predict_only  # conditional collapses to predict-only
        rationale = "probability-null-deterministic"
    else:
        p = float(probability)
        p_low = max(0.0, p - calibration_error)
        p_high = min(1.0, p + calibration_error)
        # Conservative bound: prediction "yes" could be wrong with prob (1-p_low).
        expected_loss_predict_only = risk_factor * (
            (1.0 - p_low) * fp_cost + p_high * fn_cost
        ) + predictor_cost
        ev_predict_only = -expected_loss_predict_only
        ev_escalate = -gt_cost
        ev_run_both = -(predictor_cost + gt_cost)
        # Conditional: predictor_cost always paid; ground-truth paid with
        # probability proportional to predictor's uncertainty.
        escalation_probability = 1.0 - p
        ev_conditional = -(
            risk_factor * (1.0 - p_low) * fp_cost * (1.0 - escalation_probability)
            + predictor_cost
            + gt_cost * escalation_probability
        )
        rationale = "stakes-known"

    strategies = {
        "predict-only": ev_predict_only,
        "escalate-directly": ev_escalate,
        "run-both-with-comparison": ev_run_both,
        "predict-then-conditional-escalate": ev_conditional,
    }
    # Pick max EV; ties broken by deterministic strategy ordering.
    ranking = sorted(
        strategies.items(),
        key=lambda kv: (-kv[1], kv[0]),
    )
    recommended = ranking[0][0]

    return {
        "recommended_strategy": recommended,
        "expected_value_predict_only": ev_predict_only,
        "expected_value_escalate": ev_escalate,
        "expected_value_run_both": ev_run_both,
        "rationale": rationale,
    }


def _resolve_stakes(
    intention_fm: dict[str, Any],
    scope_fm: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Resolve effective stakes via per-intention then scope-defaults inheritance.

    Returns None when neither intention nor scope declares stakes (or when
    declared stakes are entirely empty), signaling stakes-unknown to VOI.
    Per-intention `stakes` overrides scope `stakes_defaults` field-by-field.
    """
    intention_stakes = intention_fm.get("stakes")
    scope_defaults = (scope_fm or {}).get("stakes_defaults")
    if not intention_stakes and not scope_defaults:
        return None
    merged: dict[str, Any] = {}
    if scope_defaults:
        for k, v in scope_defaults.items():
            if v is not None:
                merged[k] = v
    if intention_stakes:
        for k, v in intention_stakes.items():
            if v is not None:
                merged[k] = v
    return merged or None


def _coin(cost: dict[str, Any] | None) -> float:
    """Aggregate a cost vector to a scalar.

    v1.0 reference: coin_usd only. Future versions may apply policy-declared
    CCC weighting (clock × w_c + coin × w_$ + carbon × w_g).
    """
    if not cost:
        return 0.0
    val = cost.get("coin_usd")
    try:
        return float(val) if val is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _reversibility_factor(value: Any) -> float:
    """Map reversibility enum to the multiplicative factor on stakes.

    v1.0: irreversible=1.0, reversible=0.25, reversible_within_*=0.5.
    """
    if value is None:
        return 1.0
    s = str(value)
    if s in _REVERSIBILITY_FACTOR:
        return _REVERSIBILITY_FACTOR[s]
    if s.startswith("reversible_within_"):
        return 0.5
    return 1.0


def _calibration_error(predictor_resolver_fm: dict[str, Any]) -> float:
    """Read the predictor's calibration error from its capability vector.

    v1.0 reference: error = 1 - σ.measured (or 1 - σ.declared if no measurement
    yet). When the predictor has multiple domains, the lowest σ wins as the
    conservative bound. Returns 0.0 if no capability data is available.
    """
    capability = predictor_resolver_fm.get("capability") or {}
    if not isinstance(capability, dict):
        return 0.0
    sigmas: list[float] = []
    for domain_caps in capability.values():
        if not isinstance(domain_caps, dict):
            continue
        sigma_block = domain_caps.get("sigma")
        if isinstance(sigma_block, dict):
            measured = sigma_block.get("measured")
            if measured is not None:
                try:
                    sigmas.append(float(measured))
                    continue
                except (TypeError, ValueError):
                    pass
            declared = sigma_block.get("declared")
            if declared is not None:
                try:
                    sigmas.append(float(declared))
                except (TypeError, ValueError):
                    pass
        elif isinstance(sigma_block, (int, float)):
            sigmas.append(float(sigma_block))
    if not sigmas:
        return 0.0
    return max(0.0, 1.0 - min(sigmas))
