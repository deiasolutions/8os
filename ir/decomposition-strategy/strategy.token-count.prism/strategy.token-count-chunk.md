---
authored_by: decomposition-strategy-prism-decomposer
authored_on: '2026-04-29T22:57:43.812Z'
authored_via: outside
authority_level: convention
collapsed_summary: 'Decomposition-strategy workflow node ''chunk''. Resolver: chunker.token-count.'
depends_on: []
expanded_into: null
id: strategy.token-count-chunk
kind: ir-node
parent: strategy.token-count
projection_types: []
resolution_event: 01KQDQDGZPRE4GNABFC4N8A5C3
resolved_at: '2026-04-29T22:58:06.966Z'
resolver: chunker.token-count
revalidate_trigger: null
scope: decomposition-strategy
status: resolved
superseded_by: null
supersedes: null
surrogate_of: null
tier: 1
valid_through: null
visible_to:
- decomposition-strategy
---

# Intention

Decomposition-strategy workflow node 'chunk'. Resolver: chunker.token-count.

```yaml
prism_operator:
  op: script
  resolver: chunker.token-count
  model: null
```

# Resolution

{"strategy_id": "token-count", "seed_input_path": "seed/notes-on-substrate-composition.md", "chunks": [{"ordinal": 0, "char_offset_start": 0, "char_offset_end": 1192, "summary": "# Notes on substrate composition  A substrate, in the sense used here, is a s..."}, {"ordinal": 1, "char_offset_start": 1192, "char_offset_end": 2409, "summary": "and the compiler does not need to know what the source language was used for."}, {"ordinal": 2, "char_offset_start": 2409, "char_offset_end": 3718, "summary": "compositions it permits."}, {"ordinal": 3, "char_offset_start": 3718, "char_offset_end": 4927, "summary": "to the hardware directly, generates code outside the IR, sends messages witho..."}, {"ordinal": 4, "char_offset_start": 4927, "char_offset_end": 6171, "summary": "failure cascades."}, {"ordinal": 5, "char_offset_start": 6171, "char_offset_end": 6793, "summary": "can carry the work product of a program back into the substrate as the intent..."}], "metrics": {"chunk_count": 6, "mean_chunk_chars": 1132, "min_chunk_chars": 622, "max_chunk_chars": 1309}}
