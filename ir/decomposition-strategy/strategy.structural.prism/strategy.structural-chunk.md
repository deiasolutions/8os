---
authored_by: decomposition-strategy-prism-decomposer
authored_on: '2026-04-29T22:57:34.683Z'
authored_via: outside
authority_level: convention
collapsed_summary: 'Decomposition-strategy workflow node ''chunk''. Resolver: chunker.structural.'
depends_on: []
expanded_into: null
id: strategy.structural-chunk
kind: ir-node
parent: strategy.structural
projection_types: []
resolution_event: 01KQDQDA912SW52AY1AX8QFZMZ
resolved_at: '2026-04-29T22:58:00.097Z'
resolver: chunker.structural
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

Decomposition-strategy workflow node 'chunk'. Resolver: chunker.structural.

```yaml
prism_operator:
  op: script
  resolver: chunker.structural
  model: null
```

# Resolution

{"strategy_id": "structural", "seed_input_path": "seed/notes-on-substrate-composition.md", "chunks": [{"ordinal": 0, "char_offset_start": 0, "char_offset_end": 885, "summary": "# Notes on substrate composition"}, {"ordinal": 1, "char_offset_start": 885, "char_offset_end": 2435, "summary": "## What a substrate is"}, {"ordinal": 2, "char_offset_start": 2435, "char_offset_end": 4023, "summary": "## What composition looks like"}, {"ordinal": 3, "char_offset_start": 4023, "char_offset_end": 5554, "summary": "## Why the substrate-vs-program distinction matters"}, {"ordinal": 4, "char_offset_start": 5554, "char_offset_end": 6793, "summary": "## Closing observation"}], "metrics": {"chunk_count": 5, "mean_chunk_chars": 1358, "min_chunk_chars": 885, "max_chunk_chars": 1588}}
