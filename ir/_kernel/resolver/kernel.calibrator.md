---
authored_by: kernel.self
authored_on: '2026-04-27T14:52:46.276Z'
authored_via: kernel.self
authority_level: hard
bridge: null
capability:
  kernel/calibration:
    alpha:
      declared: 1.0
      measured: null
    pi:
      declared: 0.9
      measured: null
    rho:
      declared: 0.95
      measured: null
    sigma:
      declared: 0.9
      measured: null
collapsed_summary: 'Kernel-internal resolver: Kernel Calibrator'
cost:
  carbon_g: 0
  clock_ms: 0
  coin_usd: 0
  currency: USD
depends_on: []
display_name: Kernel Calibrator
expanded_into: null
id: kernel.calibrator
kind: ir-node
parent: null
projection_types:
- _kernel.resolver
resolution_event: null
resolved_at: '2026-04-27T14:52:46.276Z'
resolver: kernel.binary@0.1.0
resolver_id: kernel.calibrator
revalidate_trigger: null
scope: _kernel
status: resolved
superseded_by: null
supersedes: null
surrogate_of: null
tier: 1
valid_through: null
visible_to:
- _kernel
---

# Intention

The kernel-internal resolver responsible for updating other resolvers' measured capability vectors based on tier 3 event aggregation per axiom 5. Vendored at init. Full implementation deferred to the prediction-economics block.
