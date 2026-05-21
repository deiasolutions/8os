---
authored_by: kernel.self
authored_on: '2026-04-29T15:21:50.065Z'
authored_via: kernel.self
authority_level: hard
body_schema_ref: .8os/projections/_kernel/_kernel.role.yml
collapsed_summary: 'Projection definition: Role'
depends_on: []
display_name: Role
expanded_into: null
id: _kernel.role
kind: ir-node
parent: null
projection_id: _kernel.role
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

Declares an access-control role. A role grants a list of permission tags to its holders; permission tags are application-defined opaque strings (common patterns: `<op-name>:scope=<scope-id>`, `policy.write:scope=<scope-id>`). Roles are referenced by policies (§7.3) and by `visible_when` predicates (§4.4). Authority: hard. See spec v1.1 §7.2 and §8.2.
