---
authored_by: kernel.self
authored_on: '2026-04-27T22:00:00.000Z'
authored_via: kernel.self
authority_level: hard
bridge: anthropic
capability:
  generate-briefing:
    alpha:
      declared: 1.0
      measured: null
    pi:
      declared: 0.5
      measured: null
    rho:
      declared: 0.7
      measured: null
    sigma:
      declared: 0.8
      measured: null
collapsed_summary: LLM resolver — composes the daily briefing from the top-N items.
cost:
  carbon_g: 8.0
  clock_ms: 30000
  coin_usd: 0.15
  currency: USD
cost_model: fixed
depends_on:
- anthropic
- anthropic-standing
display_name: Briefing composer
expanded_into: null
id: generate-briefing
implementation: null
intention_class: briefing-composition
kind: ir-node
model_name: claude-haiku-4-5
module: eightos.factory.generate_briefing
parent: null
projection_types:
- _kernel.resolver
resolution_event: null
resolved_at: null
resolver: null
resolver_id: generate-briefing
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

Bridge-crossing LLM resolver for the SCAN dogfood's fourth and final
node. Reads the upstream `filter-and-rank` resolution (a JSON-encoded
ranked list of items) and the briefing topic, calls Claude Sonnet 4.6,
and produces a structured markdown briefing artifact.

The briefing's structure: a one-paragraph framing tying the items to
the briefing topic, then one short paragraph per item summarizing why
it matters for the topic, then a closing list of raw links for
follow-up reading.

Uses Sonnet 4.6 — composition is the highest-stakes step in the flow
(the briefing IS the artifact); spending Sonnet pricing here is
warranted.

## Capability vector

- σ (sigma) 0.8 — moderately high. Sonnet handles structured prose
  composition well.
- π (pi) 0.5 — neutral.
- α (alpha) 1.0 — full autonomy.
- ρ (rho) 0.7 — moderately high. Some run-to-run variance in tone /
  emphasis; structurally stable.

## Cost vector

- `clock_ms: 30000` — Sonnet on a multi-paragraph composition task.
- `coin_usd: 0.15` — order-of-magnitude. Real cost captured per crossing.
- `carbon_g: 8.0` — symbolic.

## References

- `src/eightos/factory/generate_briefing.py` — module exposing
  `build_payload`, `adapt`.
- `src/eightos/factory/prompts/generate_briefing.md` — vendored prompt.
- Bridge: `ir/_kernel/bridge/anthropic.md`.
- Standing authorization: `ir/_kernel/authorization/anthropic-standing.md`.
