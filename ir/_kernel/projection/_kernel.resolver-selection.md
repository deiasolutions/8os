---
authored_by: kernel.self
authored_on: '2026-04-27T14:52:46.276Z'
authored_via: kernel.self
authority_level: hard
collapsed_summary: 'Projection definition: Resolver Selection'
depends_on: []
display_name: Resolver Selection
expanded_into: null
id: _kernel.resolver-selection
kind: ir-node
parent: null
projection_id: _kernel.resolver-selection
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

Records a selector decision when `kernel.selector.select` is invoked. See spec §3.6.3.

```yaml
body_shape: free
filename_suffix: .md
optional_frontmatter: []
projection_id: _kernel.resolver-selection
required_frontmatter:
- description: '{for_ir, domain, demands, selected_resolver_id, fitness_scores}'
  name: selection
  type: object
spec_reference: docs/spec/8OS-BLOCK-1-SPEC.md#3-6-3-_kernel-resolver-selection
```
