---
authored_by: decomposition-strategy-orchestrator
authored_on: '2026-04-29T22:58:09.326Z'
authored_via: outside
authority_level: convention
collapsed_summary: Comparison phase — read three strategy chunkers' outputs, emit side-by-side comparison.md.
depends_on:
- strategy.token-count-chunk
- strategy.structural-chunk
- strategy.density-chunk
expanded_into: null
id: comparison
kind: ir-node
parent: null
projection_types: []
resolution_event: 01KQDQDV29FWCSSMXEK3BVGWR0
resolved_at: '2026-04-29T22:58:17.289Z'
resolver: meta.compare-strategies
revalidate_trigger: null
scope: decomposition-strategy
status: resolved
superseded_by: null
supersedes: null
surrogate_of: null
tier: 1
valid_through: null
visible_to:
- decomposition-strategy
---

# Intention

Phase 4 of the decomposition-strategy demo. Reads the three strategy chunkers' resolutions (token-count, structural, density) and emits a side-by-side comparison artifact at `output/comparison.md`. Authored by the orchestrator after Phase 3 completes.

```yaml
prism_operator:
  op: script
  resolver: meta.compare-strategies
```

# Resolution

{"comparison_path": "output/comparison.md", "comparison_bytes": 3277, "strategies_compared": ["token-count", "structural", "density"]}
