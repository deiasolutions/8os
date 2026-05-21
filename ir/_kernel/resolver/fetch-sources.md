---
authored_by: kernel.self
authored_on: '2026-04-27T22:00:00.000Z'
authored_via: kernel.self
authority_level: hard
bridge: null
capability:
  fetch-sources:
    alpha:
      declared: 1.0
      measured: null
    pi:
      declared: 0.8
      measured: null
    rho:
      declared: 0.85
      measured: null
    sigma:
      declared: 0.9
      measured: null
collapsed_summary: Inside resolver — fetches recent items from HN and arXiv.
cost:
  carbon_g: 0.05
  clock_ms: 8000
  coin_usd: 0
  currency: USD
cost_model: fixed
depends_on: []
display_name: HN + arXiv source fetcher
expanded_into: null
id: fetch-sources
implementation: eightos.resolvers.fetch_sources:resolve
intention_class: source-fetch
kind: ir-node
model_name: null
parent: null
projection_types:
- _kernel.resolver
resolution_event: null
resolved_at: null
resolver: null
resolver_id: fetch-sources
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

Inside resolver for the SCAN dogfood's first node. Pulls top items from
two public APIs:

- HackerNews top stories (Firebase API; no auth).
- arXiv recent submissions in cs.AI / cs.LG (Atom XML API; no auth).

Returns a structured list (10 items per source) each with title, url,
abstract (when present), source label, and source priority for tie-
breaking. The adapter JSON-encodes the list into resolution_text so
downstream resolvers can parse it.

## Capability vector

- σ (sigma) 0.9 — high. The fetch is a deterministic API call;
  "quality" here means "did it return current items," and the APIs
  are reliable.
- π (pi) 0.8 — moderately high.
- α (alpha) 1.0 — full autonomy.
- ρ (rho) 0.85 — moderately high. Network failures possible; the
  resolver tolerates per-source errors and continues.

## Cost vector

- `clock_ms: 8000` — two API endpoints + per-story metadata fetches;
  HN's per-story walk is the slowest.
- `coin_usd: 0` — no API costs.
- `carbon_g: 0.05` — symbolic.

## References

- `src/eightos/resolvers/fetch_sources.py` — implementation.
