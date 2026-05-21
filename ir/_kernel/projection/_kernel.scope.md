---
authored_by: kernel.self
authored_on: '2026-04-27T14:52:46.276Z'
authored_via: kernel.self
authority_level: hard
collapsed_summary: 'Projection definition: Scope Declaration'
depends_on: []
display_name: Scope Declaration
expanded_into: null
id: _kernel.scope
kind: ir-node
parent: null
projection_id: _kernel.scope
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

Declares a scope. Per axiom 3, every (I, R) belongs to exactly one scope; scopes form a hierarchy with `parent_scope` linking child to parent. Authority is `hard` only — scope creation is a foundational decision. See spec §3.1.

```yaml
body_shape: free
filename_suffix: .md
optional_frontmatter:
- description: human-readable name
  name: display_name
  type: string
projection_id: _kernel.scope
required_frontmatter:
- description: parent in the scope hierarchy
  name: parent_scope
  type: string|null
- description: default authority attribution per level
  name: authority_defaults
  type: object
- description: default visible_to for (I, R)s in this scope
  name: visibility_defaults
  type: array
spec_reference: docs/spec/8OS-BLOCK-1-SPEC.md#3-1-_kernel-scope
```
