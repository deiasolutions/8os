---
authored_by: kernel.self
authored_on: '2026-04-29T15:21:50.065Z'
authored_via: kernel.self
authority_level: hard
body_schema_ref: .8os/projections/_kernel/_kernel.policy-evaluation.yml
collapsed_summary: 'Projection definition: Policy Evaluation'
depends_on: []
display_name: Policy Evaluation
expanded_into: null
id: _kernel.policy-evaluation
kind: ir-node
parent: null
projection_id: _kernel.policy-evaluation
projection_types:
- _kernel.projection
resolution_event: null
resolved_at: '2026-04-29T15:21:50.065Z'
resolver: kernel.binary@1.1.0-dev.6
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

Caches the result of a policy evaluation. Keyed by an `op_signature` hash incorporating the op name, the canonical JSON serialization of the op input, and the canonical serialization of the caller context (caller_id, caller_scope, caller_roles, caller_authority_level, caller_data_classification_at_most). Caller context is included in the hash because policy decisions may reference caller-identity leaves (per Block 4.7 Q-NEW-4). Cached evaluations are valid iff `valid_through` has not elapsed AND all `policies_consulted` are still in status open or resolved (Block 4.7 implements eager invalidation: when a policy is superseded, evaluations citing it have their `valid_through` set to expired). Authority: convention. See spec v1.1 §7.4 and §8.5.
