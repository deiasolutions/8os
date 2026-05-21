---
authored_by: kernel.self
authored_on: '2026-04-27T22:00:00.000Z'
authored_via: kernel.self
authority_level: hard
bridge: anthropic
capability:
  score-relevance:
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
      declared: 0.75
      measured: null
collapsed_summary: LLM resolver — scores per-item relevance against the briefing topic.
cost:
  carbon_g: 3.0
  clock_ms: 15000
  coin_usd: 0.05
  currency: USD
cost_model: fixed
depends_on:
- anthropic
- anthropic-standing
display_name: Per-item relevance scorer
expanded_into: null
id: score-relevance
implementation: null
intention_class: relevance-scoring
kind: ir-node
model_name: claude-haiku-4-5
module: eightos.factory.score_relevance
parent: null
projection_types:
- _kernel.resolver
resolution_event: null
resolved_at: null
resolver: null
resolver_id: score-relevance
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

Bridge-crossing LLM resolver for the SCAN dogfood's second node. Reads
the upstream `fetch-sources` resolution (a JSON-encoded list of items)
plus the briefing topic from the workload's PRISM-IR `params:` block,
calls Claude via the Anthropic Messages API, and produces a relevance
score in [0, 1] per item plus a short reason.

Uses Haiku 4.5 — scoring is a moderate-difficulty task that doesn't
need Sonnet-class capability and benefits from the lower cost.

## Capability vector

Initial low-confidence declarations; calibrator refines empirically.

- σ (sigma) 0.75 — moderate. LLMs handle relevance scoring well in
  general; per-item judgments may vary by topic phrasing.
- π (pi) 0.5 — neutral.
- α (alpha) 1.0 — full autonomy.
- ρ (rho) 0.65 — moderate. Same prompt may produce slightly different
  scores across runs (LLM stochasticity).

## Cost vector

- `clock_ms: 15000` — Haiku is fast; 15s envelope leaves headroom for
  longer item lists.
- `coin_usd: 0.05` — order-of-magnitude. Real cost captured via
  bridge's usage tokens.
- `carbon_g: 3.0` — symbolic.

## References

- `src/eightos/factory/score_relevance.py` — module exposing
  `build_payload`, `adapt`.
- `src/eightos/factory/prompts/score_relevance.md` — vendored prompt.
- Bridge: `ir/_kernel/bridge/anthropic.md`.
- Standing authorization: `ir/_kernel/authorization/anthropic-standing.md`.
