---
authored_by: kernel.self
authored_on: '2026-04-27T20:00:00.000Z'
authored_via: kernel.self
authority_level: hard
bridge_id: anthropic
bridge_status: active
bridge_type: api
collapsed_summary: Anthropic Messages API bridge for Block 3 LLM resolvers (decomposer, recomposer, score-relevance, generate-briefing).
cost_envelope:
  carbon_g_max: 50.0
  clock_ms_max: 60000
  coin_usd_max: 1.0
depends_on: []
display_name: Anthropic Messages API
endpoint: https://api.anthropic.com/v1/messages
expanded_into: null
id: anthropic
implementation: eightos.bridges.anthropic:cross
kind: ir-node
parent: null
projection_types:
- _kernel.bridge
requires_authorization: true
resolution_event: null
resolved_at: null
resolver: null
revalidate_trigger: null
scope: _kernel
scope_of_authority: persistent
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

Anthropic Messages API bridge — the first real outside-contact bridge in 8OS,
authored in Block 3 Piece 3.

OPEN-Q-006 ("where does bridge code live") closes via this bridge: the
outside-contact code lives in `src/eightos/bridges/anthropic.py`, registered
via this (I, R)'s `implementation:` frontmatter field. `kernel.bridge.cross`
reads that field at dispatch time and calls into the bridge module. Bridge
(I, R)s without `implementation:` (e.g., `kernel.self`) continue to use the
v0.2 echo behavior — backward compatible.

The `implementation:` field is not declared in the vendored
`_kernel.bridge` projection body — same situation as resolvers'
`implementation:` field per OPEN-Q-026 (which this commit expands to cover
bridges as well as resolvers). Consequence: in Block 3, no new bridge can
be authored via `kernel.ir.new` (the unknown field would be rejected by
`validate_extensions`). The Anthropic bridge here is hand-authored as a
committed `.md` file. Formal declaration of `implementation:` on
`_kernel.bridge` body is queued for v1.0.1-full or v1.0.2 alongside the
resolver-side amendment.

## Auth

OAuth via the same credential path Claude Code uses on the same machine.
**No `ANTHROPIC_API_KEY` required**; no keys, tokens, or credentials are
checked into the repo. If Claude Code is installed and authenticated on
the machine running 8OS, this bridge inherits that authentication.

If no valid OAuth credential is available at bridge invocation time
(Claude Code not installed, not authenticated, or token refresh fails
after retry), the bridge surfaces an authorization-tier error.

## Cost capture

The Anthropic API response carries `usage.input_tokens` and
`usage.output_tokens`. The bridge function captures these and computes
`cost_actual.coin_usd` from declared prices in this (I, R) (see
`prices` block below — to be filled in once pricing is confirmed).
The bridge crossing's tier 3 event records token counts and computed
cost alongside the resolution payload.

## Cost envelope

`cost_envelope` declares the per-crossing maximum cost the kernel
will tolerate from this bridge. Set to single-digit-USD-budget-aligned
values for Block 3's dogfood workload:
- `clock_ms_max: 60000` — Claude Messages API responses come back well
  under a minute for the workloads in Block 3 (decomposition, brief
  generation).
- `coin_usd_max: 1.0` — per-crossing cap; aggregate budget for the
  dogfood is single-digit USD and tracked at the workload level.
- `carbon_g_max: 50.0` — symbolic; not enforced for VOI in v1.0.

## Status

Active. Block 3 Piece 3.

## References

- `docs/internal/prompts/block-3-prompt.md` § "Anthropic bridge"
- `docs/spec/8OS-BLOCK-1-SPEC-v1.0.md` §3.4 (`_kernel.bridge`)
- OPEN-Q-006 (resolved by this commit)
- OPEN-Q-026 (expanded to cover bridges by this commit)
- OPEN-Q-028 (logged if OAuth investigation blocked; otherwise absent)
