---
authored_by: human-q88n
authored_on: '2026-04-29T20:00:00.000Z'
authored_via: human-q88n
authority_level: hard
bridge: null
capability:
  decomposition-strategy-prism-decomposer:
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
collapsed_summary: Deterministic PRISM-IR translator for the decomposition-strategy demo — parses a PRISM-IR program (meta or child strategy), emits a graph spec for the materializer.
cost:
  carbon_g: 0.001
  clock_ms: 50
  coin_usd: 0
  currency: USD
cost_model: fixed
depends_on: []
display_name: Decomposition-strategy PRISM-IR decomposer (deterministic)
expanded_into: null
id: decomposition-strategy-prism-decomposer
implementation: harness.resolvers.prism_decomposer:resolve
intention_class: decomposition-strategy-prism-decomposer
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
resolver_id: decomposition-strategy-prism-decomposer
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

Deterministic in-process counterpart to Block 3's LLM-bridged
`prism-ir-decomposer`, sized for the decomposition-strategy demo.
Same architectural slot (PRISM-IR doc body → graph spec → materializer
authors kernel records); deterministic Python implementation. Ported
from the L-system demo's `lsystem-prism-decomposer` with a fix for
the no-back-edge namespacing path.

The slot is general; the fill is workload-specific. Block 3's SCAN
demo exercises the slot with an LLM decomposer (interpretive
translation). The L-system demo and Demo #3 exercise the same slot
with deterministic decomposers (mechanical translation of explicit
PRISM-IR graphs). Three demos × different fills cash out the
architectural claim that the decomposer slot is not LLM-shaped.

## Contract

- **Input**: the (I, R) record's body text — a PRISM-IR v1.1 Level-1
  program in a fenced YAML block.
- **Output**: a graph spec `{nodes: [{node_id, intention_text,
  depends_on, prism_operator}, ...]}` — the same shape Block 3's
  decomposer emits. The factory's materializer authors records via
  `kernel.ir.new` / `kernel.ir.expand`.

## Capability vector

- σ (sigma) 1.0 — deterministic. Output bit-identical to its input.
- π (pi) 0.5 — neutral.
- α (alpha) 1.0 — full autonomy.
- ρ (rho) 1.0 — reproducible. Same input → same output every run.

## Cost vector

- `clock_ms: 50` — small budget. Reads one record body, parses ~80
  lines of YAML, emits ~3 graph-spec nodes per program.
- `coin_usd: 0` — no bridge crossing.
- `carbon_g: 0.001` — symbolic.

## Idempotency

On dispatch, computes the expected child id list from the program;
if every expected id already exists in the kernel's `id-to-path`
index, returns an empty graph spec. The materializer authors zero
records. Combined with the factory walker's filter (parents with
`expanded_into != null` are skipped post-materialization), the demo
is safely re-runnable.

## Namespacing

Every emitted child node_id is prefixed with the program's id (e.g.,
`decomposition-meta-emit_strategies`, `strategy.token-count-chunk`)
so the meta-program and three strategy programs can coexist in the
same `decomposition-strategy` scope without colliding on shared task
names. The L-system port had a bug in this area — the namespacing
block only ran in the back-edge code path; the no-back-edge path
emitted unnamespaced ids. Demo #3's port runs namespacing in both
paths.

## References

- `decomposition-strategy-demo/harness/resolvers/prism_decomposer.py`
  — implementation.
- `decomposition-strategy-demo/prism/decomposition-meta.prism.md`
  — Phase 1 input program.
- `lsystem-demo/harness/resolvers/prism_decomposer.py` — sibling
  deterministic decomposer; same architectural slot, same
  implementation pattern, different domain.
