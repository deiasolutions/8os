---
authored_by: kernel.self
authored_on: '2026-04-27T14:52:46.276Z'
authored_via: kernel.self
authority_level: hard
collapsed_summary: 'Projection definition: Resolver Registration'
depends_on: []
display_name: Resolver Registration
expanded_into: null
id: _kernel.resolver
kind: ir-node
parent: null
projection_id: _kernel.resolver
projection_types:
- _kernel.projection
resolution_event: null
resolved_at: '2026-04-27T14:52:46.276Z'
resolver: kernel.binary@0.1.0
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

Registers a resolver with declared cost (Clock, Coin, Carbon — axiom 5) and capability (σ, π, α, ρ — axiom 5) vectors. Kernel-internal resolvers (`kernel.selector`, `kernel.gatekeeper`, `kernel.calibrator`) are vendored at init; user resolvers are added post-init via `kernel.ir.new` with `projection_types: [_kernel.resolver]`. See spec §3.3.

```yaml
body_shape: free
filename_suffix: .md
optional_frontmatter:
- description: for LLM resolvers, the model id
  name: model_name
  type: string|null
projection_id: _kernel.resolver
required_frontmatter:
- description: must equal the (I, R)'s id
  name: resolver_id
  type: string
- description: human-readable name
  name: display_name
  type: string
- description: bridge id, or null for inside resolvers
  name: bridge
  type: string|null
- description: '{clock_ms, coin_usd, carbon_g, currency}'
  name: cost
  type: object
- description: '{<domain>: {sigma, pi, alpha, rho}}'
  name: capability
  type: object
spec_reference: docs/spec/8OS-BLOCK-1-SPEC.md#3-3-_kernel-resolver
```
