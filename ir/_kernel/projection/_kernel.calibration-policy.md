---
authored_by: kernel.self
authored_on: '2026-04-27T18:32:18.349Z'
authored_via: kernel.self
authority_level: hard
body_schema_ref: .8os/projections/_kernel/_kernel.calibration-policy.yml
collapsed_summary: 'Projection definition: Calibration Policy'
depends_on: []
display_name: Calibration Policy
expanded_into: null
id: _kernel.calibration-policy
kind: ir-node
parent: null
projection_id: _kernel.calibration-policy
projection_types:
- _kernel.projection
resolution_event: null
resolved_at: '2026-04-27T18:32:18.349Z'
resolver: kernel.binary@1.0.0
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

Declares, for a scope or domain, how the kernel invests in keeping its predictors honest. Specifies what predictor is being calibrated against what ground-truth resolver, when holdouts fire, when recalibration triggers, and what signal to fall back to when ground-truth is impractical (the muddy-puddle-or-distant-galaxy case per v1.0 §3.6). calibration_signal: ground_truth requires non-null ground_truth_resolver; calibration_signal: proxy requires proxy_specification (cross-field check applied at ir.new time). Authority: hard. See spec v1.0 §3.2 and §3.6.
