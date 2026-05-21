---
applies_to_domain: null
applies_to_scope: kernel
authored_by: human-q88n
authored_on: '2026-04-27T18:36:21.780Z'
authored_via: outside
authority_level: hard
calibration_signal: ground_truth
collapsed_summary: First prediction-economics dogfood policy (Block 2.9).
depends_on: []
expanded_into: null
ground_truth_resolver: kernel.pytest-runner
ground_truth_timeout: PT30M
holdout_rate: 0.5
id: test-result-policy
kind: ir-node
parent: null
policy_id: test-result-policy
predictor: kernel.test-pass-predictor
projection_types:
- _kernel.calibration-policy
recalibration_trigger:
  kind: count
  params:
    n: 10
resolution_event: null
resolved_at: null
resolver: null
revalidate_trigger: null
scope: kernel
status: open
superseded_by: null
supersedes: null
surrogate_of: null
tier: 1
valid_through: null
visible_to:
- kernel
---

# Intention

First prediction-economics dogfood policy (Block 2.9).

This is the first calibration policy authored against a real workload —
predicting whether `uv run pytest` will exit 0 given a working-tree
diff. The prompt specifies the workload's semantic domain as
`kernel-development/test-result`. Per OPEN-Q-019, intentions cannot
carry a `domain` field through `kernel.ir.new`'s strict-validation
input schema, so this policy uses `applies_to_domain: null` and
matches by scope only. The semantic domain is recorded here in the
body for documentation. Future v1.0.1 housekeeping will fold a
`domain` base-frontmatter field into 8OS, parallel to `stakes`, at
which point this policy can be superseded with `applies_to_domain:
kernel-development/test-result`.

Parameter rationale:

- `holdout_rate: 0.5` is intentionally high. First dogfood needs a
  fast-growing calibration corpus; running both predictor and
  ground-truth on every other call gets us paired (predicted, actual)
  evidence quickly. Once empirical calibration error stabilizes, a
  successor policy will drop the holdout rate (likely to 0.1–0.2)
  through `kernel.calibrator`-authored proposal and
  `supersede-calibration-policy` standing authorization (v1.0 §3.4).

- `recalibration_trigger: count, n: 10` is also a first-dogfood
  setting. Ten paired observations is small but sufficient to detect
  obvious miscalibration. The triggering count will rise as the
  corpus matures.

- `ground_truth_timeout: PT30M` bounds how long pytest may take
  before the calibrator falls back to a proxy signal (v1.0 §3.6).
  The kernel's own test suite currently runs in ~25s; PT30M is a
  comfortable ceiling that protects against unexpected slowdowns
  (CI on a cold runner, an inadvertent integration test, etc.).

- `calibration_signal: ground_truth` because pytest IS the ground
  truth for whether tests pass. There is no muddy-puddle case here:
  the candidate ground-truth resolver always terminates within a
  bounded budget. Future workloads on this kernel may use proxy
  signals; this one does not.

Stakes (low, project-scope, reversible):

The workload is deliberately low-stakes per the Block 2.9 prompt.
A false positive (predicted pass, actual fail) costs an unnecessary
local rerun. A false negative (predicted fail, actual pass) costs a
CI cycle that wasn't needed. No downstream consequence outside the
kernel project. Stakes are declared per-intention at authoring time.

Supersession triggers (what would cause this policy to be superseded):

1. After ~30 paired observations, the calibrator's
   `observed_calibration_error` will be stable enough to justify
   dropping `holdout_rate` to 0.2 or 0.1. Calibrator authors a
   `_kernel.calibration-policy-proposal`; sovereign approves via
   standing authorization or runtime countersignature.

2. If the `kernel.test-pass-predictor` heuristic gets refined (a
   future block trains a learned surrogate from this corpus), the
   policy's `predictor` field is updated through supersession.

3. Once OPEN-Q-019 is closed (domain joins base frontmatter at
   v1.0.1 housekeeping), this policy is superseded with the
   `applies_to_domain: kernel-development/test-result` value
   moving from documentation to enforcement.

4. If the kernel grows additional test-result-shaped workloads
   beyond pytest (e.g., type-check pass/fail, lint pass/fail), the
   policy's scope or domain shape may need to change to disambiguate.

References:
- 8OS-BLOCK-1-SPEC-v1.0.md §3.2 (`_kernel.calibration-policy`)
- 8OS-BLOCK-1-SPEC-v1.0.md §3.6 (puddle-or-galaxy framing)
- 8OS-BLOCK-1-SPEC-v1.0.md §3.7 (stakes-unknown defaults to escalate)
- docs/internal/prompts/block-2.9-prompt.md (the workload spec)
- docs/open-questions.md OPEN-Q-019 (the domain-on-intentions gap)
