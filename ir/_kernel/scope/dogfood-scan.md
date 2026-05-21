---
authored_by: human-q88n
authored_on: '2026-04-27T22:00:00.000Z'
authored_via: human-q88n
authority_defaults:
  convention: []
  hard: []
  uncalibrated: []
authority_level: hard
collapsed_summary: 'Scope declaration: dogfood-scan — Block 3 SCAN-pillar daily briefing dogfood workload.'
depends_on: []
display_name: SCAN dogfood
expanded_into: null
id: dogfood-scan
kind: ir-node
parent: null
parent_scope: null
projection_types:
- _kernel.scope
resolution_event: null
resolved_at: '2026-04-27T22:00:00.000Z'
resolver: kernel.binary@1.0.1-partial
revalidate_trigger: null
scope: _kernel
status: resolved
superseded_by: null
supersedes: null
surrogate_of: null
tier: 1
valid_through: null
visibility_defaults:
- dogfood-scan
visible_to:
- _kernel
---

# Intention

Scope `dogfood-scan` — Block 3's first end-to-end machine-machine dogfood
workload. The SCAN-pillar daily briefing flow runs here: a single PRISM-IR
doc gets decomposed by `prism-ir-decomposer`, the decomposer's graph
spec gets materialized as four child intentions
(`fetch-sources` → `score-relevance` → `filter-and-rank` →
`generate-briefing`), and the factory ticks through them to produce a
real briefing artifact.

This scope holds workload (I, R)s only. Configuration records
(resolvers, bridges, scope declaration itself) live under `_kernel`;
operation outputs (selections, authorizations, capability updates)
live under `_ops`. This scope's records are tier 1 work.

Authored by `human-q88n` per #NOKINGS — scope declaration is a
foundational decision and per OPEN-Q-015's resolution requires hard
authority. The human running the dogfood has hard authority over
their own project; this scope is part of their authoritative graph.

## Reference

- `docs/internal/prompts/block-3-prompt.md` § "The dogfood workload"
- `ir/dogfood-scan/scan-daily-briefing.prism.md` — the workload root.
