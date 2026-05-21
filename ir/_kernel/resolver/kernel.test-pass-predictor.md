---
authored_by: kernel.self
authored_on: '2026-04-27T18:53:00.342Z'
authored_via: kernel.self
authority_level: hard
bridge: null
capability:
  kernel-development/test-result:
    alpha:
      declared: 1.0
      measured: null
    pi:
      declared: 0.5
      measured: null
    rho:
      declared: 0.65
      measured: null
    sigma:
      declared: 0.7
      measured: null
collapsed_summary: Heuristic test-pass predictor for the kernel's own test suite (Block 2.9).
cost:
  carbon_g: 0.001
  clock_ms: 5
  coin_usd: 0
  currency: USD
cost_model: fixed
depends_on: []
display_name: Test-pass heuristic predictor
expanded_into: null
id: kernel.test-pass-predictor
implementation: eightos.resolvers.test_pass_predictor:predict_from_intention
kind: ir-node
model_name: null
parent: null
projection_types:
- _kernel.resolver
resolution_event: null
resolved_at: null
resolver: null
resolver_id: kernel.test-pass-predictor
revalidate_trigger: null
scope: _kernel
status: open
superseded_by: null
supersedes: null
surrogate_of: null
tier: 1
valid_through: null
visible_to:
- _kernel
---

# Intention

Heuristic test-pass predictor for the kernel's own test suite (Block 2.9).

This is the predictor in v1.0's first prediction-economics dogfood. It
takes git-diff metadata for the current working tree and returns a
prediction about whether `uv run pytest` would exit 0 if run. Pure
deterministic computation; no bridge, near-zero cost, no LLM.

Implementation: `src/eightos/resolvers/test_pass_predictor.py`,
declared in frontmatter as
`implementation: eightos.resolvers.test_pass_predictor:predict_from_intention`.
The factory's registry (Block 3 Piece 1) reads that field directly
from this (I, R)'s frontmatter to import and dispatch the function.
The dispatch entry point is `predict_from_intention(intention_id)`
(Block 3 Piece 2 shim) — it conforms to the factory's `impl(intention_id)`
contract, gets the repo from `eightos.factory.context.get_repo()`, and
delegates to `predict(diff_metadata)` underneath.

The function `predict(diff_metadata)` is the predictor. The function
`diff_metadata_from_git(repo)` is a helper that produces the input from
the current `git diff HEAD` state. The module also defines `adapt`
(adapter convention: same module as `implementation`, function name
`adapt`) which normalizes the prediction's structured output into the
factory's `{resolution_text, cost_actual}` shape.

Heuristic logic (deliberately crude):
- If any test file is changed → predict pass at 0.75 (developer just
  wrote a test; tests they author usually pass at first run, but not
  always — confidence is moderate).
- If any SDK or index file is changed → predict fail at 0.65 (kernel-
  internals changes are the most common breakage source in this repo).
- If lines_changed < 10 and neither rule above fires → predict pass at
  0.90 (small changes rarely break things).
- Default (large changes that don't touch tests or SDK/index) → predict
  pass at 0.65 (weak prior).

Capability vector rationale (initial declarations only — calibrator
refines these empirically):
- σ (sigma) 0.7 — quality is moderate. The heuristic is crude but
  encodes real signal; we expect calibration to confirm σ in [0.5, 0.85].
- π (pi) 0.5 — preference is neutral. The predictor has no opinion
  about whether being right is better than being wrong; it just predicts.
- α (alpha) 1.0 — autonomy is full. The predictor needs no human input.
- ρ (rho) 0.65 — reliability is moderate. The heuristic has obvious
  failure modes (e.g., a 5-line bug fix in src/ that breaks a test);
  expected calibration error is non-trivial.

Cost vector rationale:
- clock_ms 5 — pure Python, ~5ms to run including subprocess overhead
  for `git diff`. Negligible compared to pytest's ~25s.
- coin_usd 0 — no LLM, no API calls.
- carbon_g 0.001 — a token estimate of computational carbon for a
  tiny Python function call. Mostly symbolic; the kernel does not use
  this for VOI in v1.0.

Block 2.9 invokes `predict()` by hand for each dogfood intention; the
output becomes a `_kernel.prediction` (I, R) authored through
kernel.ir.new with subject_intention pointing at the relevant intention.
Block 3's factory will dispatch this predictor automatically.

References:
- 8OS-BLOCK-1-SPEC-v1.0.md §3.1 (`_kernel.prediction`)
- 8OS-BLOCK-1-SPEC-v1.0.md §0.1 (predictors need not be LLMs)
- docs/internal/prompts/block-2.9-prompt.md Piece 2
