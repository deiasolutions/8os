---
authored_by: kernel.self
authored_on: '2026-04-30T15:54:03.940Z'
authored_via: kernel.self
authority_level: hard
body_schema_ref: .8os/projections/_kernel/_kernel.lease.yml
collapsed_summary: 'Projection definition: Lease'
depends_on: []
display_name: Lease
expanded_into: null
id: _kernel.lease
kind: ir-node
parent: null
projection_id: _kernel.lease
projection_types:
- _kernel.projection
resolution_event: null
resolved_at: '2026-04-30T15:54:03.940Z'
resolver: kernel.binary@1.1.0-dev.7
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

Declares a multi-writer coordination claim. Acquired by authoring this projection type via `kernel.ir.new`; checked by every write op in op_pipeline.py phase 2; rejected with `LEASE_HELD` when an active lease held by another writer covers the target scope or (I, R). Expires automatically when `valid_through` (axiom-4 base field) elapses; explicit release via supersession is optional — kernel treats expired leases as released. `lease_for` may name a scope (locks all (I, R)s in it) or a specific (I, R) id (locks one record); kernel walks parent scopes during conflict detection. See spec v1.1 §7.1, §13.3-13.5, §8.6 phase 2.
