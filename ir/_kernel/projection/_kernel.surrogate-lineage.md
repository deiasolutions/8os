---
authored_by: kernel.self
authored_on: '2026-04-27T14:52:46.276Z'
authored_via: kernel.self
authority_level: hard
collapsed_summary: 'Projection definition: Surrogate Lineage'
depends_on: []
display_name: Surrogate Lineage
expanded_into: null
id: _kernel.surrogate-lineage
kind: ir-node
parent: null
projection_id: _kernel.surrogate-lineage
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

Declares a surrogate resolver's lineage (axiom 7). Surrogates emerge from operational history — they are not bootstrapped. See spec §3.5.

```yaml
body_shape: free
filename_suffix: .md
optional_frontmatter: []
projection_id: _kernel.surrogate-lineage
required_frontmatter:
- description: must equal the (I, R)'s id
  name: surrogate_id
  type: string
- description: resolver this surrogate approximates
  name: surrogate_of
  type: string
- description: '{start, end, event_count}'
  name: training_corpus
  type: object
- description: '{holdout_event_count, accuracy_metric, accuracy_value}'
  name: validation
  type: object
- description: ISO-8601 when training completed
  name: trained_on
  type: string
- description: what trained the surrogate
  name: trained_by
  type: string
spec_reference: docs/spec/8OS-BLOCK-1-SPEC.md#3-5-_kernel-surrogate-lineage
```
