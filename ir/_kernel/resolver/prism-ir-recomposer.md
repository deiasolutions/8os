---
authored_by: kernel.self
authored_on: '2026-04-28T02:00:00.000Z'
authored_via: kernel.self
authority_level: hard
bridge: anthropic
capability:
  prism-ir-recomposition:
    alpha:
      declared: 1.0
      measured: null
    pi:
      declared: 0.5
      measured: null
    rho:
      declared: 0.6
      measured: null
    sigma:
      declared: 0.75
      measured: null
collapsed_summary: PRISM-IR recomposer — reads a resolved (I, R) graph and reconstructs an English description of the workload's intent and outcome.
cost:
  carbon_g: 5.0
  clock_ms: 15000
  coin_usd: 0.05
  currency: USD
cost_model: fixed
depends_on:
- anthropic
- anthropic-standing
display_name: PRISM-IR recomposer
expanded_into: null
id: prism-ir-recomposer
implementation: null
intention_class: prism-ir-recomposition
kind: ir-node
model_name: claude-haiku-4-5
module: eightos.factory.recomposer
parent: null
projection_types:
- _kernel.resolver
resolution_event: null
resolved_at: null
resolver: null
resolver_id: prism-ir-recomposer
revalidate_trigger: null
scope: _kernel
standing_authorization: anthropic-standing
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

The PRISM-IR recomposer resolver. Block 3 Piece 6 — the round-trip
fidelity check. Takes a resolved (I, R) graph (a workload's children
under an expanded parent) and returns plain-English prose describing
what the workload was for and what happened.

This is the **inverse direction** of the decomposer:
- decomposer: PRISM-IR doc → JSON graph spec → kernel records
- recomposer: kernel records → English reconstruction

`produces: value` (the default — recomposer's resolution is plain
text, not more graph). Bridge-crossing through Anthropic on Haiku 4.5
to match the OAuth rate-limit constraint observed in Piece 5.

## Round-trip purity

The recomposer's prompt is given:
- The workload's node graph (intention_text + prism_operator + depends_on per node).
- Each node's resolution_text (or a truncation when long).

The recomposer is **not** given:
- The PRISM-IR `intention:` field from the workload root.
- The PRISM-IR doc body that triggered the decomposition.
- Any pre-decomposition framing.

The reconstruction has to come from the resolved graph alone. That's
what makes the round-trip a meaningful fidelity test — if the
reconstruction matches the original PRISM-IR intent, the kernel's
hosted graph faithfully captured the intent. If it drifts, the
failure mode is exactly the calibration signal the architecture
needs.

## Capability vector — declared, low-confidence

- σ (sigma) 0.75 — moderately high. LLMs handle structural
  summarization well; the open question is how much the resolution
  texts (chained JSON dumps in this dogfood) constrain reconstruction
  fidelity.
- π (pi) 0.5 — neutral.
- α (alpha) 1.0 — full autonomy.
- ρ (rho) 0.6 — moderate. Same workload may produce differently-
  worded reconstructions across runs.

## Cost vector

- `clock_ms: 15000` — Haiku on a structural-summarization task.
- `coin_usd: 0.05` — order-of-magnitude. Real cost captured per crossing.
- `carbon_g: 5.0` — symbolic.

## Why authored as a vendored .md, not via kernel.ir.new

Same constraint as the decomposer (OPEN-Q-026 expanded scope):
`implementation: null` is allowed by the vendored `_kernel.resolver`
body but `standing_authorization`, `intention_class`, `module`, and
`produces` are not. Hand-authored as a committed `.md` file.

## References

- `src/eightos/factory/recomposer.py` — module exposing
  `build_payload` and `adapt`.
- `src/eightos/factory/prompts/recomposer.md` — vendored prompt.
- `ir/dogfood-scan/scan-roundtrip-check.md` — the leaf this resolver
  dispatches against.
- Bridge: `ir/_kernel/bridge/anthropic.md`.
- Standing authorization: `ir/_kernel/authorization/anthropic-standing.md`.
- OPEN-Q-026 (workaround fields).
