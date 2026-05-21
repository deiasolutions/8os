---
authored_by: human-q88n
authored_on: '2026-04-29T20:00:00.000Z'
authored_via: human-q88n
authority_level: hard
bridge: null
capability:
  meta.compare-strategies:
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
collapsed_summary: Comparison reporter — reads three strategy chunkers' resolutions, emits a side-by-side comparison Markdown artifact at output/comparison.md.
cost:
  carbon_g: 0.001
  clock_ms: 30
  coin_usd: 0
  currency: USD
cost_model: fixed
depends_on: []
display_name: Decomposition-strategy comparison reporter
expanded_into: null
id: meta.compare-strategies
implementation: harness.resolvers.meta_compare_strategies:resolve
intention_class: decomposition-strategy-meta-compare
kind: ir-node
model_name: null
module: harness.resolvers.meta_compare_strategies
parent: null
projection_types:
- _kernel.resolver
resolution_event: null
resolved_at: null
resolver: null
resolver_id: meta.compare-strategies
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

Phase 4 of Demo #3 — the comparison reporter. Reads each of the three
strategy programs' terminal chunk records via
`read_upstream_resolution_value`, formats a Markdown table of metrics
+ chunk-boundary maps, writes the artifact to the demo repo's
`output/comparison.md`, and returns `{path, summary}` as its
resolution.

Deterministic. Same three child resolutions → same comparison.md.

## Contract

- **Input**: a tier-1 (I, R) authored by the orchestrator after
  Phase 3 completes, with `depends_on` set to the three strategy
  chunk records (e.g., `strategy.token-count-chunk`,
  `strategy.structural-chunk`, `strategy.density-chunk`). The
  intention's body carries an embedded `prism_operator: { resolver:
  meta.compare-strategies }` so the dispatcher routes it here.
- **Output**: writes `output/comparison.md` to the demo repo;
  returns `resolution_value = {comparison_path, comparison_bytes,
  strategies_compared}`.

## References

- `decomposition-strategy-demo/harness/resolvers/meta_compare_strategies.py`
  — implementation.
- `decomposition-strategy-demo/output/comparison.md` — artifact
  produced at demo run time.
