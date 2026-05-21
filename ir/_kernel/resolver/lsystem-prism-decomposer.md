---
authored_by: human-q88n
authored_on: '2026-04-29T12:00:00.000Z'
authored_via: human-q88n
authority_level: hard
bridge: null
capability:
  lsystem-prism-decomposer:
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
collapsed_summary: Deterministic PRISM-IR translator — parses an L-system PRISM-IR program, unrolls back-edges, emits a graph spec for the materializer.
cost:
  carbon_g: 0.001
  clock_ms: 50
  coin_usd: 0
  currency: USD
cost_model: fixed
depends_on: []
display_name: L-system PRISM-IR decomposer (deterministic)
expanded_into: null
id: lsystem-prism-decomposer
implementation: harness.resolvers.prism_decomposer:resolve
intention_class: lsystem-prism-decomposer
kind: ir-node
model_name: null
module: harness.resolvers.prism_decomposer
parent: null
produces: graph
projection_types:
- _kernel.resolver
resolution_event: null
resolved_at: null
resolver: null
resolver_id: lsystem-prism-decomposer
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

Deterministic, in-process counterpart to Block 3's LLM-bridged
`prism-ir-decomposer`. Same architectural slot (PRISM-IR doc body →
graph spec → materializer authors kernel records); deterministic Python
implementation instead of an LLM bridge crossing.

The slot is general; the fill is workload-specific. Block 3's SCAN demo
exercises the slot with an LLM decomposer (interpretive translation of
informal PRISM-IR intent into a pragmatic graph). The L-system demo
exercises the same slot with a deterministic decomposer (mechanical
translation of an explicit PRISM-IR graph, unrolling back-edges using
the program's own `params.target_iterations`). Two demos with different
fills cash out the architectural claim that the decomposer slot is not
LLM-shaped.

## Contract

- **Input**: the (I, R) record's body text (a PRISM-IR v1.1 Level-1
  program in a fenced YAML block).
- **Output**: a graph spec `{nodes: [{node_id, intention_text,
  depends_on, prism_operator}, ...]}` — the same shape Block 3's
  decomposer emits. The factory's materializer
  (`src/eightos/factory/materializer.py`) consumes it via
  `kernel.ir.new` / `kernel.ir.expand`.

## Capability vector

- σ (sigma) 1.0 — deterministic. Output bit-identical to its input.
- π (pi) 0.5 — neutral.
- α (alpha) 1.0 — full autonomy.
- ρ (rho) 1.0 — reproducible. Same input → same output every run.

The 1.0 declarations are honest: this resolver is a pure function of its
input. No calibration drift expected. If `measured` ever lands below 1.0
for σ or ρ, something has gone wrong upstream of the resolver itself
(file corruption, YAML parsing change, etc.) and is worth investigating.

## Cost vector

- `clock_ms: 50` — small budget. The decomposer reads one record body,
  parses ~150 lines of YAML, emits ~10 graph-spec nodes. No I/O
  (everything is in-process).
- `coin_usd: 0` — no bridge crossing.
- `carbon_g: 0.001` — symbolic.

## Idempotency

The decomposer is safely re-runnable. On dispatch, it computes the
expected child id list from the program; if every expected id already
exists in the kernel's `id-to-path` index, it returns an empty graph
spec. The materializer then authors zero records. The factory's walker
filter (parent records with `expanded_into != null` are skipped) handles
the post-materialization steady state; this idempotency layer handles
the partial-failure mid-run state.

## References

- `lsystem-demo/harness/resolvers/prism_decomposer.py` — implementation.
- `lsystem-demo/prism/lsystem-fractal-plant.prism.md` — input program.
- `src/eightos/factory/decomposer.py` — Block 3's LLM decomposer; same
  architectural slot, different fill.
- `ir/_kernel/resolver/prism-ir-decomposer.md` — Block 3's resolver
  registration; structural template for this record.
