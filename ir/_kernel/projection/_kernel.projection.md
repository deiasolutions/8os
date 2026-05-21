---
authored_by: kernel.self
authored_on: '2026-04-27T14:52:46.276Z'
authored_via: kernel.self
authority_level: hard
collapsed_summary: 'Projection definition: Projection Definition'
depends_on: []
display_name: Projection Definition
expanded_into: null
id: _kernel.projection
kind: ir-node
parent: null
projection_id: _kernel.projection
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

Declares a projection type. Projection types are opaque labels the kernel uses to group (I, R)s into queryable categories and to drive frontmatter-extension validation per §2.1 and filename-suffix application per §2.2. See spec §3.2.

```yaml
body_shape: free
filename_suffix: .md
optional_frontmatter:
- description: reference to the body schema YAML
  name: body_schema_ref
  type: string
projection_id: _kernel.projection
required_frontmatter:
- description: must equal the (I, R)'s id
  name: projection_id
  type: string
- description: human-readable name
  name: display_name
  type: string
spec_reference: docs/spec/8OS-BLOCK-1-SPEC.md#3-2-_kernel-projection
```
