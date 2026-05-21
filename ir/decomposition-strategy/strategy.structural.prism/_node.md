---
authored_by: meta.emit-strategies
authored_on: '2026-04-29T22:57:11.538Z'
authored_via: outside
authority_level: convention
collapsed_summary: structural decomposition strategy — emitted by meta.emit-strategies for seed seed/notes-on-substrate-composition.md
depends_on: []
domain: decomposition-strategy-prism-decomposer
expanded_into: strategy.structural
id: strategy.structural
kind: ir-node
parent: null
projection_types:
- prism-ir
resolution_event: null
resolved_at: null
resolver: null
revalidate_trigger: null
scope: decomposition-strategy
status: open
superseded_by: null
supersedes: null
surrogate_of: null
tier: 1
valid_through: null
visible_to:
- decomposition-strategy
---

# Intention

Apply the structural decomposition strategy to a fixed seed input. This program was emitted by `meta.emit-strategies` as part of the decomposition-strategy demo's self-composition trace. The 8OS frontmatter (above this Intention section, authored by the orchestrator at Phase 2) and the PRISM-IR body `id` (below) match exactly per v1.1 identity discipline: both are `strategy.structural`.

The chunker resolver `chunker.structural` is registered in the host 8OS instance as a deterministic Python implementation. Calling it with the params declared below produces a list of chunk-boundary records as `resolution_value.chunks`, in a fixed shape shared across all three strategies (so the comparison resolver can read them uniformly).

```yaml
v: 1.1.0
prism: strategy.structural
version: 1.1.0
conformance: level-1
id: strategy.structural
name: Structural decomposition strategy
domain: decomposition-strategy/structural
intention: Decompose the seed input at 'seed/notes-on-substrate-composition.md' into
  chunks using the structural strategy. Emit chunk boundaries as character offsets
  into the seed plus per-chunk summaries. The chunks are not interpreted further by
  this program; the comparison resolver consumes them downstream.
failure_tolerance:
  chunk: retry
constraints:
- sla: total flow under 5s
  fail: drop
  priority: low
params:
  seed_input_path: seed/notes-on-substrate-composition.md
  heading_levels:
  - '#'
  - '##'
  - '###'
entities:
- id: chunk_state
  fields:
  - chunks
nodes:
- id: start
  t: start
- id: chunk
  t: task
  o:
    op: script
    resolver: chunker.structural
  out:
  - chunks
- id: end
  t: end
edges:
- s: start
  t: chunk
- s: chunk
  t: end
metrics:
- id: chunk_count
  expr: length(chunk_state.chunks) at end
```

## Resolver semantics (informational)

The single `op: script, resolver: chunker.structural` declaration above binds to a deterministic Python implementation registered as a `_kernel.resolver` record at `8os/ir/_kernel/resolver/chunker.structural.md`. The implementation lives in the demo repo's `harness/resolvers/` directory. The chunker reads the seed text from disk, applies its strategy, and returns the chunks as `resolution_value`.

## Hosting note

This program was emitted by `meta.emit-strategies` and authored as a tier-1 (I, R) by the demo's orchestrator at Phase 2. It did not exist before Run 1; it was the resolution of another PRISM-IR program. Run 2 (executed after this record was authored) decomposes and dispatches it.
