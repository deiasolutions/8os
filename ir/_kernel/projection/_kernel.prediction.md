---
authored_by: kernel.self
authored_on: '2026-04-27T18:32:18.349Z'
authored_via: kernel.self
authority_level: hard
body_schema_ref: .8os/projections/_kernel/_kernel.prediction.yml
collapsed_summary: 'Projection definition: Prediction'
depends_on: []
display_name: Prediction
expanded_into: null
id: _kernel.prediction
kind: ir-node
parent: null
projection_id: _kernel.prediction
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

Records a prediction about an intention's resolution, authored by a predictor resolver before (and possibly instead of, or alongside) the candidate ground-truth resolver runs. The prediction's `subject_intention` names the intention; the predictor's `probability` and `predicted_resolution` carry the prediction itself; `predictor` references the resolver that produced it. The prediction does not carry an escalation_cost field — VOI looks up the candidate ground-truth resolver's current cost at consultation time. See spec v1.0 §3.1 and §3.7.
