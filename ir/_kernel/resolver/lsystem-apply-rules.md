---
authored_by: human-q88n
authored_on: '2026-04-29T12:00:00.000Z'
authored_via: human-q88n
authority_level: hard
bridge: null
capability:
  lsystem-apply-rules:
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
collapsed_summary: L-system apply-rules — one rewrite pass over current_string using params.rules.
cost:
  carbon_g: 0.001
  clock_ms: 200
  coin_usd: 0
  currency: USD
cost_model: fixed
depends_on: []
display_name: L-system apply-rules (one rewrite pass)
expanded_into: null
id: lsystem-apply-rules
implementation: harness.resolvers.apply_rules:resolve
intention_class: lsystem-apply-rules
kind: ir-node
model_name: null
module: harness.resolvers.apply_rules
parent: null
produces: value
projection_types:
- _kernel.resolver
resolution_event: null
resolved_at: null
resolver: null
resolver_id: lsystem-apply-rules
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

One pass of L-system rule rewriting. Reads upstream `lstate` from the
predecessor's resolution; for each character of `current_string`, looks
it up in `params.rules`, replaces with the rule's RHS if a rule
matches, leaves unchanged otherwise. Increments `iteration`. Emits the
new `lstate` (with `params_snapshot` carried forward).

The decomposer unrolls this resolver `params.target_iterations` times
(six instances for the fractal plant: `lsystem-apply-rules-iter-0`
through `lsystem-apply-rules-iter-5`). Each unrolled instance depends
on the previous; the chain is straight, no branching.

Cost budget at 200ms is comfortable for the deepest iteration —
iteration 5's input string can be tens of thousands of characters and
the rewrite is O(n).

## References

- `lsystem-demo/harness/resolvers/apply_rules.py` — implementation.
