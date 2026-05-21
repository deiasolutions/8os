---
authored_by: kernel
authored_on: '2026-04-27T19:12:05.040Z'
authored_via: kernel.self
authority_defaults:
  convention: []
  hard: []
  uncalibrated: []
authority_level: hard
collapsed_summary: 'Scope declaration: Kernel Operations (_ops)'
depends_on: []
display_name: Kernel Operations
expanded_into: null
id: _ops
kind: ir-node
parent: null
parent_scope: null
projection_types:
- _kernel.scope
resolution_event: null
resolved_at: '2026-04-27T19:12:05.040Z'
resolver: kernel.binary@1.0.0
revalidate_trigger: null
scope: _kernel
status: resolved
superseded_by: null
supersedes: null
surrogate_of: null
tier: 1
valid_through: null
visibility_defaults:
- _ops
visible_to:
- _kernel
---

# Intention

The `_ops` scope holds tier 2 kernel-authored operational records — resolver-selection, authorization, capability-update — produced as side effects of kernel ops. Materialized lazily on first tier 2 write per OPEN-Q-005 (preserved under v0.2 §1.4).
