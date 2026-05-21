---
authored_by: human-q88n
authored_on: '2026-04-29T20:00:00.000Z'
authored_via: human-q88n
authority_level: hard
bridge: null
capability:
  chunker.density:
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
collapsed_summary: Density chunker — splits the seed at sentence boundaries where the rolling unique-word ratio over a 5-sentence window drops below 0.55. Heuristic for vocabulary-shift / wrap-up signals. Deterministic.
cost:
  carbon_g: 0.0001
  clock_ms: 15
  coin_usd: 0
  currency: USD
cost_model: fixed
depends_on: []
display_name: Density (vocabulary-ratio) decomposition chunker
expanded_into: null
id: chunker.density
implementation: harness.resolvers.chunker_density:resolve
intention_class: decomposition-strategy-chunker-density
kind: ir-node
model_name: null
module: harness.resolvers.chunker_density
parent: null
projection_types:
- _kernel.resolver
resolution_event: null
resolved_at: null
resolver: null
resolver_id: chunker.density
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

The density chunker. Reads the seed text from disk, splits it into
sentences, and walks a sliding window of `params.window_sentences`
(default 5). For each window position, computes the unique-word ratio
(`unique_lowercased_alphanumeric / total_lowercased_alphanumeric`).
When the ratio drops below `params.unique_word_ratio_threshold`
(default 0.55), emits a chunk boundary at the end of the last sentence
in the window — heuristic signal for "the local vocabulary just got
repetitive, something is wrapping up here."

The strategy is illustrative, not principled. It produces chunk
boundaries that are visibly different from the token-count and
structural strategies' boundaries, which is the demo's only
requirement.

Determinism: pure function of the seed text + window/threshold params.

## References

- `decomposition-strategy-demo/harness/resolvers/chunker_density.py`
- `decomposition-strategy-demo/docs/contract.md` — chunk shape (Phase 3).
