---
authored_by: kernel.self
authored_on: '2026-04-27T14:52:46.271Z'
authored_via: kernel.self
authority_level: hard
collapsed_summary: 'Projection definition: prism-ir'
depends_on: []
display_name: PRISM-IR Process Flow
expanded_into: null
id: prism-ir
kind: ir-node
parent: null
projection_id: prism-ir
projection_types:
- _kernel.projection
resolution_event: null
resolved_at: '2026-04-27T14:52:46.271Z'
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

Migrated projection 'prism-ir' from v0.1 .8os/projections/prism-ir.yml.

```yaml
applies_to_tier: 1
body_shape: yaml-fenced
description: PRISM-IR (Process Representation, Intent Simulation & Manifestation — Intermediate Representation) hosted as an 8OS projection per PRISM-IR v1.1 Level 1 conformance. The (I, R)'s Intention is the process flow expressed in PRISM-IR YAML; the Resolution is the simulation/execution trace. The 8OS frontmatter `id` MUST equal the PRISM-IR top-level `id` per v1.1 identity discipline.
display_name: PRISM-IR Process Flow
filename_suffix: .prism.md
id: prism-ir
kind: projection
notes: 'v1.1 Level 1 specifies prism / version / conformance as additional frontmatter

  fields alongside the 8OS frontmatter. The current 8OS kernel.ir.new operation

  (Block 1 §7.6.3) writes only the canonical 8OS frontmatter; it does not yet

  accept arbitrary projection-specific frontmatter additions despite Block 1 §2

  reserving that capability. Until the kernel honors §2''s "PROJECTION-SPECIFIC

  EXTENSIONS" clause, Level 1 PRISM-IR (I, R) records hosted on this kernel

  carry the prism / version / conformance declarations inside the body''s YAML

  fenced block (which is the v1.0.0 PRISM-IR top-level schema) rather than as

  duplicate frontmatter keys. See OPEN-Q-010 in docs/open-questions.md and the

  Block 2.5 report for the friction this surfaced and the suggested v1.2

  amendment path.

  '
prism_ir_spec_version: 1.1.0
required_body_top_level_keys:
- v
- id
- name
- intention
- nodes
- edges
required_extensions: []
spec_reference: docs/spec/PRISM-IR-SPEC-v1.1.md
```
