---
authored_by: kernel.self
authored_on: '2026-04-29T15:21:50.065Z'
authored_via: kernel.self
authority_level: hard
body_schema_ref: .8os/projections/_kernel/_kernel.policy.yml
collapsed_summary: 'Projection definition: Policy'
depends_on: []
display_name: Policy
expanded_into: null
id: _kernel.policy
kind: ir-node
parent: null
projection_id: _kernel.policy
projection_types:
- _kernel.projection
resolution_event: null
resolved_at: '2026-04-29T15:21:50.065Z'
resolver: kernel.binary@1.1.0-dev.6
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

Declares a policy that gates kernel operations. The condition can be an inline predicate (same language as `visible_when` per §4.4 — `any`/`all`/`not` over leaves; Block 4.7 implements caller-context-only semantics per Block 4.7 finding F-PRED) or a resolver reference (the kernel dispatches the resolver synchronously to obtain the decision per Block 4.7 Q-RESOLVER). When multiple policies match an op, the kernel evaluates in author order, short-circuits on the first deny, accumulates transforms and follow-ups. Authority: hard. See spec v1.1 §7.3 and §8.
