---
authored_by: kernel.self
authored_on: '2026-04-27T21:00:00.000Z'
authored_via: kernel.self
authority_level: hard
bridge: anthropic
capability:
  prism-ir-decomposition:
    alpha:
      declared: 1.0
      measured: null
    pi:
      declared: 0.5
      measured: null
    rho:
      declared: 0.6
      measured: null
    sigma:
      declared: 0.7
      measured: null
collapsed_summary: PRISM-IR decomposer — translates a PRISM-IR doc into a kernel (I, R) graph spec via the Anthropic bridge.
cost:
  carbon_g: 5.0
  clock_ms: 8000
  coin_usd: 0.05
  currency: USD
cost_model: fixed
depends_on:
- anthropic
- anthropic-standing
display_name: PRISM-IR decomposer
expanded_into: null
id: prism-ir-decomposer
implementation: null
intention_class: prism-ir-decomposition
kind: ir-node
model_name: claude-haiku-4-5
module: eightos.factory.decomposer
parent: null
produces: graph
projection_types:
- _kernel.resolver
resolution_event: null
resolved_at: null
resolver: null
resolver_id: prism-ir-decomposer
revalidate_trigger: null
scope: _kernel
standing_authorization: anthropic-standing
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

The PRISM-IR decomposer resolver. Block 3 Piece 4 — first LLM-bridge resolver
in 8OS. Takes a PRISM-IR document body (Level 0 or Level 1 PRISM-IR YAML)
and returns a JSON graph specification that the factory's materializer
translates into kernel-hosted (I, R) records.

This is a **bridge-crossing resolver**: `bridge: anthropic`, no
`implementation:` field. Decomposition runs through the Anthropic Messages
API via `kernel.bridge.cross`, authorized by the standing `anthropic-standing`
authorization.

## Contract

- **Input** (delivered by the factory through the bridge crossing): a PRISM-IR
  document body. The factory's dispatcher passes the intention's
  `intention_text` through; the decomposer module assembles the API
  request with the vendored prompt as system message and the document
  body as user message.
- **Output** (consumed by the factory): a JSON object of shape
  `{nodes: [{node_id, intention_text, depends_on, prism_operator}, ...]}`.
  The decomposer module's `parse_response` extracts the JSON from the
  model's text reply; `adapt` exposes it on `resolution_value`.
- **Materialization**: a separate concern. The factory's materializer
  (`src/eightos/factory/materializer.py`) consumes the parsed graph spec
  and authors kernel records via `kernel.ir.new` and `kernel.ir.expand`.

## Capability vector — declared, low-confidence

Initial declarations only; the calibrator refines these empirically once
the workload accumulates.

- σ (sigma) 0.7 — quality is moderate. Modern Claude models handle
  schema-shaped JSON output well, but PRISM-IR has open-ended ambiguity
  (e.g., implied `op:` types, malformed edges) where the decomposer must
  exercise judgement. We expect calibration to land σ in [0.6, 0.85].
- π (pi) 0.5 — preference is neutral. The decomposer has no opinion
  about whether being right is better than being wrong; it just decomposes.
- α (alpha) 1.0 — autonomy is full. No human in the loop during decomposition.
- ρ (rho) 0.6 — reliability is moderate. The same PRISM-IR doc may produce
  slightly different decompositions across runs (LLM stochasticity);
  ranking-stable but not bit-identical. Calibration will refine.

## Cost vector — non-zero coin

Non-zero `coin_usd` is **deliberate**. Block 2.9 hit OPEN-Q-024 — the VOI
cost-vector aggregation degenerates when both predictor and ground-truth
resolver have `coin_usd: 0`. Block 3 fixes this by running an LLM bridge
crossing at real cost.

- `clock_ms: 8000` — declared 8-second envelope. Anthropic Messages API
  responses for short prompts come back well under that.
- `coin_usd: 0.05` — order-of-magnitude estimate based on PRISM-IR
  doc sizes encountered in practice (input tokens ~2k, output tokens
  ~500). Sonnet 4.6 pricing: $3/Mtok input + $15/Mtok output ≈ $0.0135.
  Declared envelope of $0.05 leaves headroom for larger docs and
  conservative VOI math.
- `carbon_g: 5.0` — symbolic per the bridge's carbon estimate.

The Anthropic bridge captures actual `usage.input_tokens` and
`usage.output_tokens` per crossing; the recorded `cost_actual` reflects
real consumption, not this declared envelope.

**Pricing note:** the `_PRICING_USD_PER_MTOK` map currently lives in
`src/eightos/bridges/anthropic.py`. Per the master prompt, those rates
should ultimately live in this resolver's bridge (I, R) frontmatter for
live updates without code changes. See OPEN-Q-028.

## Authorization

`standing_authorization: anthropic-standing` — references
`ir/_kernel/authorization/anthropic-standing.md`, which authorizes any
kernel-internal resolver to cross the Anthropic bridge subject to the
per-crossing cost ceiling. This decomposer falls under that ceiling.

## Why authored as a vendored .md, not via kernel.ir.new

`implementation: null` is fine on its own, but `standing_authorization`,
`intention_class`, `module`, `produces`, and `domain` are projection-
extension-style frontmatter fields that the vendored `_kernel.resolver`
body does not declare. Authoring this record via `kernel.ir.new` would
fail `validate_extensions`. Same shape as `kernel.test-pass-predictor`
(Block 2.9) and the other Block 3 Piece 1 / Piece 3 / Piece 5 vendored
records — see OPEN-Q-026 (expanded scope as of Piece 5).

## `produces: graph` and `module`

The two Piece 5 fields that make decomposition-as-resolver actually work:

- `produces: graph` — tells the factory's tick to take the graph-
  producing branch instead of the default value-producing branch. After
  dispatch returns, the tick reads the resolution_value as a graph spec
  and calls the materializer to author children under the parent
  intention. The parent stays open + expanded; the walker's
  `expanded_into is None` filter (also Piece 5) ensures it isn't
  re-dispatched. Piece 6's recomposer will eventually supersede the
  parent's resolution with a composed-from-children answer.

- `module: eightos.factory.decomposer` — tells the factory's registry
  where to look for the resolver's adapter (`adapt`) and payload-builder
  (`build_payload`) functions. Because this resolver is bridge-crossing
  (`implementation: null`), the registry can't derive a module from
  `implementation`'s prefix; `module:` provides the explicit pointer.
  The dispatcher's bridge path calls `decomposer.build_payload(intention_text)`
  to assemble the Anthropic Messages API request with the vendored
  prompt as system message and the PRISM-IR doc body as user message.

## References

- `docs/spec/PRISM-IR-SPEC-v1.1.md` — the input language.
- `docs/internal/prompts/block-3-prompt.md` § "Decomposer resolver" — original spec.
- Bridge (I, R): `ir/_kernel/bridge/anthropic.md`.
- Standing authorization: `ir/_kernel/authorization/anthropic-standing.md`.
- Vendored prompt: `src/eightos/factory/prompts/decomposer.md`.
- Decomposer module: `src/eightos/factory/decomposer.py`.
- Materializer: `src/eightos/factory/materializer.py`.
- OPEN-Q-024 (cost-vector degeneracy) — exercised by this resolver.
- OPEN-Q-026 (vendored body amendment for `implementation:` /
  `standing_authorization:` / `intention_class:` extensions).
- OPEN-Q-028 (pricing map should live in bridge / resolver frontmatter).
