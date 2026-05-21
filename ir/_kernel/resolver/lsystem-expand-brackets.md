---
authored_by: human-q88n
authored_on: '2026-04-29T12:00:00.000Z'
authored_via: human-q88n
authority_level: hard
bridge: null
capability:
  lsystem-expand-brackets:
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
collapsed_summary: L-system expand-brackets — walk bracketed string with explicit (x,y,heading) stack; emit flat absolute-coordinate command stream.
cost:
  carbon_g: 0.001
  clock_ms: 1000
  coin_usd: 0
  currency: USD
cost_model: fixed
depends_on: []
display_name: L-system expand-brackets (state-machine pass)
expanded_into: null
id: lsystem-expand-brackets
implementation: harness.resolvers.expand_brackets:resolve
intention_class: lsystem-expand-brackets
kind: ir-node
model_name: null
module: harness.resolvers.expand_brackets
parent: null
produces: value
projection_types:
- _kernel.resolver
resolution_event: null
resolved_at: null
resolver: null
resolver_id: lsystem-expand-brackets
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

Translates the bracketed L-system string into the simdecisions
turtledraw adapter's flat command grammar. The adapter has no `[`/`]`
push/pop primitives; the bracket semantics live here.

Maintains an explicit `(x, y, heading)` stack. Walks the input string
character by character:
- `F` — emit `forward <step>`; advance turtle pose.
- `+` — emit `right <angle>`; turn turtle.
- `-` — emit `left <angle>`; turn turtle.
- `[` — push current pose to stack.
- `]` — pop stack; emit `penup; goto <x> <y>; <align heading>; pendown`
  to restore turtle without drawing.
- All other characters (`X`, etc.) — no-op (rule-only symbols).

Reads `forward_step_px`, `angle_degrees`, `start_x`, `start_y`,
`start_heading_degrees`, `pen_color`, `pen_width`, `background_color`
from `lstate.params_snapshot`. Emits flat command stream as a single
semicolon-separated string into `lstate.flat_commands`.

Output prefixed with adapter-state setup: `clear; background <r> <g> <b>;
penup; goto <start_x> <start_y>; pendown; color <r> <g> <b>; width <n>`
followed by the body of forward/turn/goto commands.

Cost budget at 1s accommodates an iteration-6 input string (~30k chars
post-rewrite) with the pop-restore pen-state dance per `]` (which is
the most expensive operation per character in the average case).

## References

- `lsystem-demo/harness/resolvers/expand_brackets.py` — implementation.
- `lsystem-demo/docs/adapter-contract.md` — adapter command grammar.
