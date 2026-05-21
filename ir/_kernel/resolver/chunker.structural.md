---
authored_by: human-q88n
authored_on: '2026-04-29T20:00:00.000Z'
authored_via: human-q88n
authority_level: hard
bridge: null
capability:
  chunker.structural:
    alpha:
      declared: 1.0
      measured: null
    pi:
      declared: 0.5
      measured: null
    rho:
      declared: 1.0
      measured: null
    sigma:
      declared: 1.0
      measured: null
collapsed_summary: Structural chunker — splits the seed text at markdown heading boundaries (#, ##, ###). Variable-sized chunks; respects authored hierarchy. Deterministic.
cost:
  carbon_g: 0.0001
  clock_ms: 10
  coin_usd: 0
  currency: USD
cost_model: fixed
depends_on: []
display_name: Structural (heading-based) decomposition chunker
expanded_into: null
id: chunker.structural
implementation: harness.resolvers.chunker_structural:resolve
intention_class: decomposition-strategy-chunker-structural
kind: ir-node
model_name: null
module: harness.resolvers.chunker_structural
parent: null
projection_types:
- _kernel.resolver
resolution_event: null
resolved_at: null
resolver: null
resolver_id: chunker.structural
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

The structural chunker. Reads the seed text from disk and splits at
every line beginning with one of the configured heading prefixes
(`#`, `##`, `###` by default). Variable-sized chunks; the first chunk
holds any preamble before the first heading.

Determinism: pure function of the seed text + `heading_levels`.

## References

- `decomposition-strategy-demo/harness/resolvers/chunker_structural.py`
- `decomposition-strategy-demo/docs/contract.md` — chunk shape (Phase 3).
