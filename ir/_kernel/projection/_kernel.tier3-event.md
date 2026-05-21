---
authored_by: kernel.self
authored_on: '2026-04-27T14:52:46.276Z'
authored_via: kernel.self
authority_level: hard
collapsed_summary: 'Projection definition: Tier 3 Event Pointer'
depends_on: []
display_name: Tier 3 Event Pointer
expanded_into: null
id: _kernel.tier3-event
kind: ir-node
parent: null
projection_id: _kernel.tier3-event
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

Typed projection over tier 3 events written to .8os/events/. (I, R) records of this type are pointers to canonical events in JSONL streams. See spec §3.6.1.

```yaml
body_shape: free
filename_suffix: .md
optional_frontmatter: []
projection_id: _kernel.tier3-event
required_frontmatter: []
spec_reference: docs/spec/8OS-BLOCK-1-SPEC.md#3-6-1-_kernel-tier3-event
```
