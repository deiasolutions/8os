---
authored_by: kernel.self
authored_on: '2026-04-27T18:32:18.349Z'
authored_via: kernel.self
authority_level: hard
body_schema_ref: .8os/projections/_kernel/_kernel.calibration-policy-proposal.yml
collapsed_summary: 'Projection definition: Calibration Policy Proposal'
depends_on: []
display_name: Calibration Policy Proposal
expanded_into: null
id: _kernel.calibration-policy-proposal
kind: ir-node
parent: null
projection_id: _kernel.calibration-policy-proposal
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

Records the calibrator's proposal to update a calibration policy in response to observed evidence. Proposals are not effective; they queue as `proposal_status: pending` until standing authorization match (per §3.4) or runtime countersignature transitions them to `approved`, at which point the calibrator is dispatched to author the actual supersession on the target policy. Append-only discipline: status transitions are recorded by superseding the proposal with a new (I, R) carrying the new proposal_status; query the latest record in the supersession chain to get current status. See spec v1.0 §3.3 and §3.4. Block 2.8 spec amendment Q1: field renamed from `status` to `proposal_status` to avoid collision with base 8OS frontmatter `status`.
