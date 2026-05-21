---
authored_by: kernel.self
authored_on: '2026-04-27T14:52:46.276Z'
authored_via: kernel.self
authority_level: hard
collapsed_summary: 'Projection definition: Capability Update'
depends_on: []
display_name: Capability Update
expanded_into: null
id: _kernel.capability-update
kind: ir-node
parent: null
projection_id: _kernel.capability-update
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

Records a calibration-driven update to a resolver's capability vector, produced by `kernel.calibrator`. See spec §3.6.4.

```yaml
body_shape: free
filename_suffix: .md
optional_frontmatter: []
projection_id: _kernel.capability-update
required_frontmatter:
- description: '{resolver_id, previous, updated, corpus_summary}'
  name: capability_update
  type: object
spec_reference: docs/spec/8OS-BLOCK-1-SPEC.md#3-6-4-_kernel-capability-update
```
