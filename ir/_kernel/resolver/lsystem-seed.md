---
authored_by: human-q88n
authored_on: '2026-04-29T12:00:00.000Z'
authored_via: human-q88n
authority_level: hard
bridge: null
capability:
  lsystem-seed:
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
collapsed_summary: L-system seed — initialize lstate from the PRISM-IR root's params (axiom, iteration=0).
cost:
  carbon_g: 0.001
  clock_ms: 20
  coin_usd: 0
  currency: USD
cost_model: fixed
depends_on: []
display_name: L-system seed (initialize lstate)
expanded_into: null
id: lsystem-seed
implementation: harness.resolvers.seed:resolve
intention_class: lsystem-seed
kind: ir-node
model_name: null
module: harness.resolvers.seed
parent: null
produces: value
projection_types:
- _kernel.resolver
resolution_event: null
resolved_at: null
resolver: null
resolver_id: lsystem-seed
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

Seeds the L-system workflow. Walks up to the PRISM-IR root record,
extracts `params.axiom` and `params.rules`, and emits the initial
`lstate` payload: `current_string = axiom`, `iteration = 0`,
`params_snapshot = <full params block>`. Downstream resolvers read this
payload directly and propagate `params_snapshot` forward through the
chain so no resolver below seed has to walk back to the root.

Deterministic, no I/O beyond reading the root record. Listed cost
budget is generous; actual clock is well under 5ms in practice.

## References

- `lsystem-demo/harness/resolvers/seed.py` — implementation.
