---
authored_by: kernel.self
authored_on: '2026-04-27T14:52:46.276Z'
authored_via: kernel.self
authority_level: hard
collapsed_summary: 'Projection definition: Bridge Declaration'
depends_on: []
display_name: Bridge Declaration
expanded_into: null
id: _kernel.bridge
kind: ir-node
parent: null
projection_id: _kernel.bridge
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

Declares an inside/outside bridge (axiom 0). Two bridges are vendored at init: `kernel.self` (the kernel's *cogito*) and `human-<operator>` (the human's sovereignty per #NOKINGS). Both are real bridges with real provenance — neither is a magic exception. See spec §2.4 and §3.4.

```yaml
body_shape: free
filename_suffix: .md
optional_frontmatter:
- description: URL, identity, or other endpoint payload
  name: endpoint
  type: any
- description: 'active|quarantined|deprecated|removed; defaults to active when absent. kernel.bridge.cross rejects crossings into bridges with bridge_status: quarantined per BLOCK-2.7-SPEC-CORRECTIONS Patch 4.'
  name: bridge_status
  type: string
projection_id: _kernel.bridge
required_frontmatter:
- description: must equal the (I, R)'s id
  name: bridge_id
  type: string
- description: human-readable name
  name: display_name
  type: string
- description: api|human|simulation|script|sensor|other
  name: bridge_type
  type: string
- description: whether crossings require authorization
  name: requires_authorization
  type: boolean
- description: single|session|persistent
  name: scope_of_authority
  type: string
- description: '{clock_ms_max, coin_usd_max, carbon_g_max}'
  name: cost_envelope
  type: object
spec_reference: docs/spec/8OS-BLOCK-1-SPEC.md#3-4-_kernel-bridge
```
