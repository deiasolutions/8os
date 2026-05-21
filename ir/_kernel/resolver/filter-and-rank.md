---
authored_by: kernel.self
authored_on: '2026-04-27T22:00:00.000Z'
authored_via: kernel.self
authority_level: hard
bridge: null
capability:
  filter-and-rank:
    alpha:
      declared: 1.0
      measured: null
    pi:
      declared: 0.9
      measured: null
    rho:
      declared: 1.0
      measured: null
    sigma:
      declared: 1.0
      measured: null
collapsed_summary: Inside resolver — picks top-N items from a scored list.
cost:
  carbon_g: 0.001
  clock_ms: 50
  coin_usd: 0
  currency: USD
cost_model: fixed
depends_on: []
display_name: Top-N filter
expanded_into: null
id: filter-and-rank
implementation: eightos.resolvers.filter_and_rank:resolve
intention_class: structured-filter
kind: ir-node
model_name: null
parent: null
projection_types:
- _kernel.resolver
resolution_event: null
resolved_at: null
resolver: null
resolver_id: filter-and-rank
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

Inside resolver for the SCAN dogfood's third node. Reads the upstream
`score-relevance` resolution (a JSON-encoded list of scored items) and
returns the top-N items by score, with ties broken by source priority
(HackerNews > arXiv).

Pure deterministic computation; capability vector saturated for the
question "given a scored list, which N have the highest scores."

## Cost vector

- `clock_ms: 50` — a few milliseconds of Python.
- `coin_usd: 0` — local compute.
- `carbon_g: 0.001` — symbolic.

## References

- `src/eightos/resolvers/filter_and_rank.py` — the implementation.
