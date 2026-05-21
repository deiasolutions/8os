---
authored_by: lsystem-prism-decomposer
authored_on: '2026-04-29T21:17:49.625Z'
authored_via: outside
authority_level: convention
collapsed_summary: 'L-system rule rewrite, iteration 1. Reads upstream lstate, applies params.rules to current_string, increments iteration. Resolver: lsystem-a'
depends_on:
- koch-snowflake-apply_rules-iter-0
expanded_into: null
id: koch-snowflake-apply_rules-iter-1
kind: ir-node
parent: koch-snowflake
projection_types: []
resolution_event: 01KQDHPR8AZWM9HXYY4P9SW2YQ
resolved_at: '2026-04-29T21:18:17.866Z'
resolver: lsystem-apply-rules
revalidate_trigger: null
scope: lsystem
status: resolved
superseded_by: null
supersedes: null
surrogate_of: null
tier: 1
valid_through: null
visible_to:
- lsystem
---

# Intention

L-system rule rewrite, iteration 1. Reads upstream lstate, applies params.rules to current_string, increments iteration. Resolver: lsystem-apply-rules.

```yaml
prism_operator:
  op: script
  resolver: lsystem-apply-rules
  model: null
```

# Resolution

{"current_string": "F-F++F-F-F-F++F-F++F-F++F-F-F-F++F-F++F-F++F-F-F-F++F-F++F-F++F-F-F-F++F-F++F-F++F-F-F-F++F-F++F-F++F-F-F-F++F-F", "iteration": 2, "params_snapshot": {"axiom": "F++F++F", "rules": {"F": "F-F++F-F"}, "target_iterations": 4, "angle_degrees": 60, "forward_step_px": 7, "start_x": 357, "start_y": 614, "start_heading_degrees": 0, "pen_color": {"r": 120, "g": 220, "b": 140}, "pen_width": 1, "background_color": {"r": 14, "g": 10, "b": 26}}, "elapsed_ms": 67.39612500314252}
