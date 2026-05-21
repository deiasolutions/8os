---
authored_by: kernel.self
authored_on: '2026-04-27T14:52:46.276Z'
authored_via: kernel.self
authority_level: hard
collapsed_summary: 'Projection definition: Authorization Record'
depends_on: []
display_name: Authorization Record
expanded_into: null
id: _kernel.authorization
kind: ir-node
parent: null
projection_id: _kernel.authorization
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

Records an authorization decision per axiom 6, produced by the gatekeeper when a bridge crossing requires authorization. See spec §3.6.2.

```yaml
body_shape: free
filename_suffix: .md
optional_frontmatter: []
projection_id: _kernel.authorization
required_frontmatter:
- description: '{bridge, for_ir, scope_of_authority, cost_ceiling}'
  name: authorizes
  type: object
spec_reference: docs/spec/8OS-BLOCK-1-SPEC.md#3-6-2-_kernel-authorization
```
