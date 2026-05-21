---
authored_by: human-q88n
authored_on: '2026-04-29T12:00:00.000Z'
authored_via: human-q88n
authority_level: hard
bridge: null
capability:
  lsystem-emit-to-canvas:
    alpha:
      declared: 1.0
      measured: null
    pi:
      declared: 0.5
      measured: null
    rho:
      declared: 0.85
      measured: null
    sigma:
      declared: 0.95
      measured: null
collapsed_summary: L-system emit-to-canvas — Playwright transmits the flat command stream to the simdecisions turtledraw adapter and screenshots the result.
cost:
  carbon_g: 0.5
  clock_ms: 30000
  coin_usd: 0
  currency: USD
cost_model: fixed
depends_on: []
display_name: L-system emit-to-canvas (Playwright bridge to turtledraw)
expanded_into: null
id: lsystem-emit-to-canvas
implementation: harness.resolvers.emit_to_canvas:resolve
intention_class: lsystem-emit-to-canvas
kind: ir-node
model_name: null
module: harness.resolvers.emit_to_canvas
parent: null
produces: value
projection_types:
- _kernel.resolver
resolution_event: null
resolved_at: null
resolver: null
resolver_id: lsystem-emit-to-canvas
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

Terminal node of the L-system workflow. Crosses to the simdecisions
turtledraw adapter via Playwright per the contract at
`lsystem-demo/docs/adapter-contract.md`:

1. Launch headless Chromium.
2. Navigate to `http://localhost:5173/?set=turtle-draw` (the Vite dev
   server in simdecisions/browser must be running).
3. Wait for the `<canvas>` element under `div.tdraw-canvas-container`
   to mount.
4. Fill `input.tdraw-input` with the upstream `lstate.flat_commands`
   string and press Enter. Single-shot if the string fits in one paste;
   chunked sends with brief waits between chunks otherwise. The
   resolver logs which path was taken so the writeup can reference the
   actual run.
5. Wait briefly for the canvas to finish drawing.
6. Screenshot the canvas region; write the PNG to
   `lsystem-demo/output/fractal-plant.png`.
7. Return resolution metadata: image path, command count, chunking
   path, browser timing.

This resolver is the single bridge crossing in the demo (in spirit,
though not via `kernel.bridge.cross` — the existing bridge ops target
LLM APIs, not browser-automation surfaces, and the contract for crossing
the simdecisions adapter doesn't fit that shape). The Playwright
invocation is modeled as a bridge crossing in the writeup; in the (I, R)
graph, it's a single resolution event with `resolution_value` carrying
the rendered image's path and the command-stream metadata.

## Capability vector

- σ (sigma) 0.95 — high. Playwright + p5.js canvas is reliable; the
  occasional edge case (window resize race, font load timing) lands σ
  short of 1.0.
- ρ (rho) 0.85 — high but not perfect. Browser timing makes
  pixel-identical reruns probabilistic on the order of 95%+; the
  declared value is conservative.
- α (alpha) 1.0 — full autonomy.
- π (pi) 0.5 — neutral.

## Cost vector

- `clock_ms: 30000` — generous budget. Headless Chromium cold-start +
  Vite page load + canvas render + screenshot. Typical run is 5–15s.
- `coin_usd: 0` — local processes only.
- `carbon_g: 0.5` — Chromium CPU consumption is the main driver.

## References

- `lsystem-demo/harness/resolvers/emit_to_canvas.py` — implementation.
- `lsystem-demo/docs/adapter-contract.md` — adapter contract.
- `simdecisions/browser/src/primitives/drawing-canvas/DrawingCanvasApp.tsx`
  — adapter source.
