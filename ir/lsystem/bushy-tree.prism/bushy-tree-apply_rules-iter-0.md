---
authored_by: lsystem-prism-decomposer
authored_on: '2026-04-29T21:19:03.396Z'
authored_via: outside
authority_level: convention
collapsed_summary: 'L-system rule rewrite, iteration 0. Reads upstream lstate, applies params.rules to current_string, increments iteration. Resolver: lsystem-a'
depends_on:
- bushy-tree-seed
expanded_into: null
id: bushy-tree-apply_rules-iter-0
kind: ir-node
parent: bushy-tree
projection_types: []
resolution_event: 01KQDHRWV4T2VA16KZVGAGKBVB
resolved_at: '2026-04-29T21:19:28.100Z'
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

L-system rule rewrite, iteration 0. Reads upstream lstate, applies params.rules to current_string, increments iteration. Resolver: lsystem-apply-rules.

```yaml
prism_operator:
  op: script
  resolver: lsystem-apply-rules
  model: null
```

# Resolution

{"current_string": "FF+[+F-F-F]-[-F+F+F]", "iteration": 1, "params_snapshot": {"axiom": "F", "rules": {"F": "FF+[+F-F-F]-[-F+F+F]"}, "target_iterations": 4, "angle_degrees": 22.5, "forward_step_px": 4, "start_x": 640, "start_y": 760, "start_heading_degrees": -90, "pen_color": {"r": 120, "g": 220, "b": 140}, "pen_width": 1, "background_color": {"r": 14, "g": 10, "b": 26}}, "elapsed_ms": 69.81258299856563}
