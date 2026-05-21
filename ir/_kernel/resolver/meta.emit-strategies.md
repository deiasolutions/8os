---
authored_by: human-q88n
authored_on: '2026-04-29T20:00:00.000Z'
authored_via: human-q88n
authority_level: hard
bridge: null
capability:
  meta.emit-strategies:
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
collapsed_summary: Meta-resolver — emits three child PRISM-IR programs (token-count, structural, density chunkers) as the resolution of the decomposition-strategy meta-program. Phase 2 of the demo authors each emission as a tier-1 (I, R) via kernel.ir.new.
cost:
  carbon_g: 0.001
  clock_ms: 20
  coin_usd: 0
  currency: USD
cost_model: fixed
depends_on: []
display_name: Decomposition-strategy meta-emit-strategies
expanded_into: null
id: meta.emit-strategies
implementation: harness.resolvers.meta_emit_strategies:resolve
intention_class: decomposition-strategy-meta-emit
kind: ir-node
model_name: null
module: harness.resolvers.meta_emit_strategies
parent: null
projection_types:
- _kernel.resolver
resolution_event: null
resolved_at: null
resolver: null
resolver_id: meta.emit-strategies
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

The headline resolver of Demo #3. Reads the meta-program's params
(seed input path + the three strategies' configurations), constructs
three complete child PRISM-IR program bodies, and returns them as the
meta-program's resolution.

Self-composition: the resolution of one PRISM-IR program is three more
PRISM-IR programs, of the same shape, hosted by the same kernel.

Deterministic. Same params → identical emissions every run.

## Contract

- **Input**: the meta-program's `emit_strategies` task (I, R). Resolver
  reads `params.seed_input_path` and `params.strategies` from the
  meta-program's PRISM-IR body via `read_parent_prism_params`.
- **Output**: `resolution_value.emissions` — list of `{discriminator,
  program_id, collapsed_summary, intention_body}` records. The
  `intention_body` is a complete PRISM-IR program body (Intention prose
  + fenced YAML block), suitable for `kernel.ir.new`'s `intention_text`
  field. The orchestrator (Phase 2) reads each emission and authors
  the corresponding child record.

## References

- `decomposition-strategy-demo/harness/resolvers/meta_emit_strategies.py`
  — implementation.
- `decomposition-strategy-demo/docs/contract.md` — emission shape.
