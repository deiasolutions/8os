---
authored_by: kernel.self
authored_on: '2026-04-27T18:59:09.583Z'
authored_via: kernel.self
authority_level: hard
bridge: null
capability:
  kernel-development/test-result:
    alpha:
      declared: 1.0
      measured: null
    pi:
      declared: 1.0
      measured: null
    rho:
      declared: 1.0
      measured: null
    sigma:
      declared: 1.0
      measured: null
collapsed_summary: Pytest ground-truth runner for the kernel's test-suite predictions (Block 2.9).
cost:
  carbon_g: 0.5
  clock_ms: 30000
  coin_usd: 0
  currency: USD
cost_model: fixed
depends_on: []
display_name: Pytest ground-truth runner
expanded_into: null
id: kernel.pytest-runner
implementation: eightos.resolvers.pytest_runner:resolve
kind: ir-node
model_name: null
parent: null
projection_types:
- _kernel.resolver
resolution_event: null
resolved_at: null
resolver: null
resolver_id: kernel.pytest-runner
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

Pytest ground-truth runner for the kernel's test-suite predictions (Block 2.9).

This is the ground-truth resolver paired with `kernel.test-pass-predictor`
under the `test-result-policy` calibration policy. Per v1.0 §3.6,
ground-truth resolvers exist to give the calibrator a sovereign signal
to reason about predictions against. For the Block 2.9 dogfood, pytest
is that sovereign — it is the kernel's authoritative answer to "do the
tests currently pass?"

Implementation: `src/eightos/resolvers/pytest_runner.py`, declared in
frontmatter as `implementation: eightos.resolvers.pytest_runner:resolve`.
The factory's registry (Block 3 Piece 1) reads that field directly from
this (I, R)'s frontmatter to import and dispatch the function. The
function `resolve(intention_id)` runs `uv run pytest --tb=no -q` in a
subprocess, captures the exit code, and returns the resolution. The
module also defines `adapt` (adapter convention: same module as
`implementation`, function name `adapt`) which normalizes the runner's
structured output into the factory's `{resolution_text, cost_actual}`
shape.

Bridge: null

The runner lives entirely inside the kernel project. It runs pytest on
the kernel's own source — self-observation, not outside-call. Axiom 0's
inside/outside boundary doesn't apply here: pytest's source is in some
Python package somewhere, but the test SUITE being run is in `tests/`,
which is kernel-internal. The subprocess is a process boundary, not an
inside/outside boundary. A future test-runner shape that dispatched to a
CI service would warrant a bridge; this local runner does not.

Cost vector rationale:
- clock_ms 30000 — pytest currently runs in ~25s; 30s is a comfortable
  declaration. The calibrator will refine empirically per v1.0 §3.5.
- coin_usd 0 — local compute, no external API.
- carbon_g 0.5 — order-of-magnitude estimate. Mostly symbolic; the
  kernel does not use this for VOI in v1.0.

Capability vector (σ=π=α=ρ=1.0):

Pytest IS ground truth in this domain by definition. If pytest exits 0,
the predicate "tests pass" is true; if pytest exits non-zero, the
predicate is false. There is no source of truth more authoritative for
this question. The capability vector is fully saturated. The calibrator
will not refine pytest's σ downward because pytest's outputs are
self-defining — calibration is what predictors are measured against, not
what pytest is measured against.

Cost-model: fixed (could be linear-in-test-count later; defer for now)

Pytest's runtime varies with test count, but for Block 2.9 the test
count is small enough (~90 tests) that the variance is dominated by
fixed setup costs. A future block could declare cost_model:
linear-in-depth with depth_budget = test count for finer-grained
selector budget tracking. Not warranted yet.

Block 2.9 invokes `resolve()` by hand when the selector's effective
strategy is `escalate-directly` or `run-both-with-comparison`; the
output drives `kernel.ir.resolve` on the subject intention, which in
turn populates the calibration-corpus index's `actual_value` field at
the next reindex.

References:
- 8OS-BLOCK-1-SPEC-v1.0.md §3.2 (`_kernel.calibration-policy` —
  ground_truth_resolver field)
- 8OS-BLOCK-1-SPEC-v1.0.md §3.6 (puddle-or-galaxy framing, why proxy
  signals exist; not needed here since pytest always terminates)
- docs/internal/prompts/block-2.9-prompt.md Piece 3
