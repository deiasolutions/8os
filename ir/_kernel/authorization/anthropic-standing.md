---
authored_by: kernel.self
authored_on: '2026-04-27T20:00:00.000Z'
authored_via: kernel.self
authority_level: hard
authorized_action: bridge-cross
authorizes:
  bridge: anthropic
  for_ir: '*'
  scope_of_authority: persistent
  cost_ceiling:
    clock_ms: 60000
    coin_usd: 1.0
    carbon_g: 50.0
collapsed_summary: Standing authorization for any kernel-internal resolver to cross the Anthropic bridge within per-crossing cost ceilings.
depends_on:
- anthropic
expanded_into: null
id: anthropic-standing
kind: ir-node
parent: null
projection_types:
- _kernel.authorization
resolution_event: null
resolved_at: null
resolver: null
revalidate_trigger: null
scope: _kernel
status: open
superseded_by: null
supersedes: null
surrogate_of: null
tier: 1
valid_through: null
visible_to:
- _kernel
---

# Intention

Standing authorization for the Anthropic bridge.

Block 3 Piece 3 — first real outside-contact bridge. Authorizes any
kernel-internal resolver (decomposer, recomposer, score-relevance,
generate-briefing) to cross the Anthropic bridge for the lifetime of
this authorization, subject to the per-crossing cost ceiling.

Authorization shape per Block 2.8's `_kernel.authorization` extension:
- `authorized_action: bridge-cross` (default; v0.2 backward-compatible).
- `authorizes` block carries the v0.2 fields (bridge, for_ir,
  scope_of_authority, cost_ceiling).
- `for_ir: '*'` — wildcard, this authorization applies to crossings
  for any (I, R). Per-resolver authorizations could narrow this in
  future blocks.

## Cost ceiling

Matches the bridge's own `cost_envelope` per-crossing limit:
- `clock_ms: 60000` — 60 seconds.
- `coin_usd: 1.0` — per-crossing cap.
- `carbon_g: 50.0` — symbolic.

The aggregate Block 3 dogfood budget (single-digit-USD per the prompt's
discipline) is tracked at the workload level by the human running the
dogfood, not by this authorization. This authorization's job is the
per-crossing ceiling, not portfolio management.

## References

- `docs/spec/8OS-BLOCK-1-SPEC-v1.0.md` §3.4 (`_kernel.authorization`)
- `docs/spec/BLOCK-2.8-SPEC-AMENDMENTS.md` Amendment 2 (extension shape)
- Bridge (I, R): `ir/_kernel/bridge/anthropic.md`
