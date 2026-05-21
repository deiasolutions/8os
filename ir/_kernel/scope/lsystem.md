---
authored_by: human-q88n
authored_on: '2026-04-29T12:00:00.000Z'
authored_via: human-q88n
authority_defaults:
  convention: []
  hard: []
  uncalibrated: []
authority_level: hard
collapsed_summary: 'Scope declaration: lsystem — Lindenmayer fractal plant demo, host scope for the PRISM-IR + 8OS + simdecisions composition.'
depends_on: []
display_name: L-system demo
expanded_into: null
id: lsystem
kind: ir-node
parent: null
parent_scope: null
projection_types:
- _kernel.scope
resolution_event: null
resolved_at: '2026-04-29T12:00:00.000Z'
resolver: kernel.binary@1.1.0-dev.6
revalidate_trigger: null
scope: _kernel
status: resolved
superseded_by: null
supersedes: null
surrogate_of: null
tier: 1
valid_through: null
visibility_defaults:
- lsystem
visible_to:
- _kernel
---

# Intention

Scope `lsystem` — host scope for the L-system composition demo (PRISM-IR
+ 8OS + simdecisions turtledraw). This scope holds the workload's tier-1
work nodes: the root PRISM-IR record `lsystem-fractal-plant` and the
seven-to-nine (I, R) records the demo's deterministic decomposer
materializes from it.

The decomposer (`lsystem-prism-decomposer`) translates the PRISM-IR doc
into a graph spec; the materializer authors children under the root with
`depends_on` edges that reflect the unrolled iteration loop. The factory
walks the children in topological order; the terminal node
(`emit-to-canvas`) crosses to the simdecisions turtledraw adapter via
Playwright and produces the rendered PNG.

The demo's repo lives at `https://github.com/deiasolutions/lsystem-demo`;
this scope hosts the kernel-side records the demo's `harness/run_demo.py`
authors and walks. The Python implementations (resolvers, run script)
ship from the `lsystem-demo` Python package, installable editable
alongside this 8OS binary.

Authored by `human-q88n` per #NOKINGS — scope declarations require hard
authority through the human's identity bridge.

## Reference

- `https://github.com/deiasolutions/lsystem-demo` — demo repo and writeup.
- `lsystem-demo/prism/lsystem-fractal-plant.prism.md` — canonical PRISM-IR program.
- `lsystem-demo/docs/adapter-contract.md` — turtledraw adapter contract.
