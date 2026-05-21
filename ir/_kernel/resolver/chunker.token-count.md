---
authored_by: human-q88n
authored_on: '2026-04-29T20:00:00.000Z'
authored_via: human-q88n
authority_level: hard
bridge: null
capability:
  chunker.token-count:
    alpha:
      declared: 1.0
      measured: null
    pi:
      declared: 0.5
      measured: null
    rho:
      declared: 1.0
      measured: null
    sigma:
      declared: 1.0
      measured: null
collapsed_summary: Token-count chunker — splits the seed text into chunks of approximately N whitespace-tokens each (boundary aligned to nearest token end). Deterministic.
cost:
  carbon_g: 0.0001
  clock_ms: 10
  coin_usd: 0
  currency: USD
cost_model: fixed
depends_on: []
display_name: Token-count decomposition chunker
expanded_into: null
id: chunker.token-count
implementation: harness.resolvers.chunker_token_count:resolve
intention_class: decomposition-strategy-chunker-token-count
kind: ir-node
model_name: null
module: harness.resolvers.chunker_token_count
parent: null
projection_types:
- _kernel.resolver
resolution_event: null
resolved_at: null
resolver: null
resolver_id: chunker.token-count
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

The token-count chunker. Reads the seed text from disk, walks it by
whitespace-bounded tokens, emits a chunk boundary every
`params.tokens_per_chunk` tokens (default 200), aligned so chunks
don't split mid-word.

Determinism: pure function of the seed text + `tokens_per_chunk`.

## References

- `decomposition-strategy-demo/harness/resolvers/chunker_token_count.py`
- `decomposition-strategy-demo/docs/contract.md` — chunk shape (Phase 3).
