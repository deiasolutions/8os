---
authored_by: q88n
authored_on: '2026-04-29T00:00:00.000Z'
authored_via: outside
authority_level: convention
collapsed_summary: Decomposition-strategy meta-program — emits three PRISM-IR child programs (token-count, structural, density), each implementing a different chunking strategy against a fixed seed input. The orchestrator authors the children as tier-1 (I, R) records after this program resolves, then dispatches them in a separate factory tick. Self-composition witness for the publish trio.
depends_on: []
domain: decomposition-strategy-prism-decomposer
expanded_into: decomposition-meta
id: decomposition-meta
kind: ir-node
parent: null
projection_types:
- prism-ir
resolution_event: null
resolved_at: null
resolver: null
revalidate_trigger: null
scope: decomposition-strategy
status: open
superseded_by: null
supersedes: null
surrogate_of: null
tier: 1
valid_through: null
visible_to:
- decomposition-strategy
---

# Intention

A meta-program: a PRISM-IR program whose resolution is more PRISM-IR programs.
Run 1 dispatches this meta-program, which emits three child programs as a
structured resolution payload. Phase 2 (orchestrator-driven) authors those
emissions as fresh tier-1 `(I, R)` records under the same scope through
`kernel.ir.new`. Run 2 dispatches the children, each of which decomposes the
fixed seed input (a small markdown document) using a different chunking
strategy. Phase 4 emits a comparison artifact.

The 8OS-hosted frontmatter `id` (above) and the PRISM-IR body `id` (below)
match exactly per v1.1 identity discipline.

The composition under test is the substrate composing itself: the kernel
hosting a program whose resolution is more programs the kernel then runs.
Together with Demo #1 (`lsystem-demo`, deterministic decomposer + outside-call
adapter) and Demo #2 (`scan-demo`, LLM-mediated decomposer + real HTTP),
Demo #3 fills the third structural slot in the demo trio: the substrate
producing what the substrate consumes. See `lsystem-demo/docs/koch-snowflake.md`
for the decomposer-slot generality framing this demo extends.

The meta-program is deliberately small: a single task node that runs the
strategy-emitter resolver. The work is not in graph structure; it's in the
resolver's emission of three complete child PRISM-IR programs, each of
which is itself a workflow the kernel will run.

```yaml
v: 1.1.0
prism: decomposition-meta
version: 1.1.0
conformance: level-1

id: decomposition-meta
name: Decomposition-strategy meta-program
domain: decomposition-strategy/meta
intention: |
  Emit three child PRISM-IR programs — each implementing a different
  decomposition strategy (token-count, structural, density) — for a
  fixed seed input. The orchestrator authors the children as tier-1
  (I, R) records after this program resolves; Run 2 dispatches them.
  This program does not invoke the children; emitting them is its job,
  and authoring them is the orchestrator's job.

failure_tolerance:
  emit_strategies: escalate

constraints:
  - sla: total flow under 5s
    fail: drop
    priority: low

params:
  seed_input_path: "seed/notes-on-substrate-composition.md"
  strategies:
    - discriminator: "token-count"
      tokens_per_chunk: 200
    - discriminator: "structural"
      heading_levels: ["#", "##", "###"]
    - discriminator: "density"
      window_sentences: 5
      unique_word_ratio_threshold: 0.55

entities:
  - id: meta_state
    fields: [seed_input_path, emissions]

nodes:
  - id: start
    t: start
  - id: emit_strategies
    t: task
    o: { op: script, resolver: meta.emit-strategies }
    out: [emissions]
  - id: end
    t: end

edges:
  - { s: start, t: emit_strategies }
  - { s: emit_strategies, t: end }

metrics:
  - id: emissions_count
    expr: length(meta_state.emissions) at end
  - id: cycle_time_p95
    expr: rate(start -> end, p95)
```

## Resolver semantics (informational)

The single `op: script, resolver: meta.emit-strategies` declaration above
binds to a deterministic Python implementation registered as a
`_kernel.resolver` record in the host 8OS instance. The implementation lives
in this repo at `harness/resolvers/meta_emit_strategies.py`; the registration
record lives in `8os/ir/_kernel/resolver/meta.emit-strategies.md` (installed
once, before Run 1).

`meta.emit-strategies` does the following on dispatch:

1. Read the seed input from `params.seed_input_path` (relative to the demo
   repo root). Confirm it exists and is non-empty. Capture its byte length
   and SHA-256 for the resolution payload's metadata.
2. For each of the three strategies declared in `params.strategies`,
   construct a complete child PRISM-IR program body (Intention prose +
   fenced YAML `prism:` block specifying a single-node workflow whose task
   is `chunker.<discriminator>`). The body is the markdown that will become
   the `intention_text` of the child (I, R); the orchestrator will pair it
   with explicit frontmatter fields when calling `kernel.ir.new`.
3. Return the `emissions` list as `resolution_value`. Each emission carries
   `discriminator`, `program_id`, `collapsed_summary`, and `intention_body`
   (the constructed body text).

The emission shape is fixed in `docs/contract.md` ("Emission shape (Phase 1
→ Phase 2 boundary)"). The orchestrator reads `resolution_value.emissions`
verbatim and authors each via `kernel.ir.new`.

## Self-composition witness

When Phase 1 completes, the kernel ledger contains:

- One tier-1 (I, R) for the meta-program (this record), `status: resolved`,
  with three emissions in its `resolution_value`.
- One tier-3 creation event recording this program's authoring (from when
  the orchestrator bootstrapped it).
- One tier-3 resolution event recording the emit-strategies dispatch
  (resolver, cost, resolution payload reference).

Phase 2 then authors three more tier-1 (I, R) records, each producing
its own tier-3 creation event. The substrate is observing the resolutions
of one of its programs become the intentions of three more — citably,
phase-by-phase, in the same ledger.

## Hosting note

The 8OS frontmatter at the top of this file presumes the file is mirrored
into the host 8OS repo at `8os/ir/decomposition-strategy/decomposition-meta.prism.md`
when the demo runs. The decomposition-strategy-demo repo is the canonical
authoring location; `harness/run_demo.py`'s setup phase imports this file
into 8OS (and ensures the `decomposition-strategy` `_kernel.scope` record
exists).

The child programs (`strategy.token-count`, `strategy.structural`,
`strategy.density`) are NOT mirrored from this repo; they do not exist
until Phase 2 authors them as resolutions of this program. They are
emitted, not authored. That's the headline.
