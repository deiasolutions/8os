---
authored_by: kernel.self
authored_on: '2026-04-27T18:32:18.349Z'
authored_via: kernel.self
authority_level: hard
bridge: null
capability:
  kernel/voi:
    alpha:
      declared: 1.0
      measured: null
    pi:
      declared: 1.0
      measured: null
    rho:
      declared: 1.0
      measured: null
    sigma:
      declared: 1.0
      measured: null
collapsed_summary: 'Resolver: Kernel Value-of-Information'
cost:
  carbon_g: 0
  clock_ms: 1
  coin_usd: 0
  currency: USD
depends_on: []
display_name: Kernel Value-of-Information
expanded_into: null
id: kernel.voi
kind: ir-node
model_name: null
parent: null
projection_types:
- _kernel.resolver
resolution_event: null
resolved_at: '2026-04-27T18:32:18.349Z'
resolver: kernel.binary@1.0.0
resolver_id: kernel.voi
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

The kernel-internal resolver that computes the expected value of escalation given a prediction, a candidate ground-truth resolver, and stakes (v1.0 §4). Pure inside resolver, near-zero cost, deterministic given inputs. Stakes-unknown defaults to `escalate-directly` per §3.7 — the kernel's expression of epistemic humility: in the absence of information that would justify economizing on authority, defer to the more authoritative source. VOI's recommendations may later be refined by the calibrator if they are observed to diverge from sovereign judgment. Reference math documented in `eightos.voi`'s module docstring.
