# SCAN dogfood — empirical witness for LLM-mediated decomposer composition

A working composition of three independently-built systems generates a
daily AI-governance briefing from real HackerNews and arXiv content.
PRISM-IR declares the workflow; an LLM-bridged decomposer translates
the PRISM-IR document into a four-node (I, R) graph; 8OS hosts the
graph; the factory walks it, dispatching real HTTP fetches and real
Anthropic Messages API calls; resolutions accumulate; an LLM
recomposer reads the resolved graph back without seeing the original
PRISM-IR doc and reconstructs an English description for round-trip
fidelity comparison. None of the three composing systems was built
knowing about the others as a primary use case.

This is **Demo #2** in the publish-track demo trio. Demo #1
([`lsystem-demo`](https://github.com/deiasolutions/lsystem-demo))
witnesses composition with a deterministic decomposer and a
browser-driven outside-call adapter. Demo #3
([`decomposition-strategy-demo`](https://github.com/deiasolutions/decomposition-strategy-demo))
witnesses the substrate composing itself — programs producing programs.
SCAN witnesses **LLM-mediated decomposition with real outside-call
execution**.

The trio together cashes out the architectural claim that the
**decomposer slot is general** — it accepts any resolver that produces
a graph spec from an intention body, regardless of whether the
resolver is deterministic Python, an LLM crossing, or a meta-program
emitting more programs.

## The durability frame

This demo was authored during Block 3 against an early v1.1 binary
(commits [`f4b3fd6`](https://github.com/deiasolutions/8os/commit/f4b3fd6)
Piece 5 end-to-end run, [`6741c37`](https://github.com/deiasolutions/8os/commit/6741c37)
Piece 6 recomposer). Since then 8OS has progressed through Blocks
4.1–4.7 to `v1.1.0-dev.6` (377 tests passing, policy machinery, Path A
cancellation, housekeeping amendment, `domain` and `data_classification`
lifted to base frontmatter, `visible_when` predicate engine).

**SCAN's records replay clean against `v1.1.0-dev.6`'s amended
schema validators.** The Block 4 amendments lifted three new fields
to base frontmatter; the Path A amendment changed the
supersede-with-replacement reversal mechanism; the policy machinery
introduced new evaluation phases on every op. The SCAN records,
authored before any of these existed, pass `kernel.reindex --check`
under all of them without modification.

The trace below is **reconstructed from on-disk timestamps** in the
record frontmatter (`authored_on`, `resolved_at`) rather than from a
fresh replay. The Block 3 numbers are canonical: same records, same
artifacts, same provenance trail in the kernel ledger. Re-running
would produce different HN/arXiv content but identical pipeline
behavior. The demo's witness is durable across kernel evolution —
records authored by Block 3's binary continue to be valid Block 4.7
records, which is itself a property worth flagging.

## Composing systems

| System | Role in the demo | Source |
|---|---|---|
| **PRISM-IR v1.1** | Declares the workflow as a Level-1 program with informal `intention:` prose plus structured `nodes:`, `edges:`, and `params:` blocks. | [`deiasolutions/prism-ir`](https://github.com/deiasolutions/prism-ir) (language spec) |
| **8OS v1.1.0-dev.6** | Hosts the workflow as an (I, R) graph. Decomposer manifests the program; factory walks; resolution events land on tier-3 ledger. The kernel binary at the time of the original run was earlier (pre-Block 4); the records are durable across the transition. | [`deiasolutions/8os`](https://github.com/deiasolutions/8os) at tag `v1.1.0-dev.6` |
| **Anthropic Messages API** (Claude Haiku 4.5) | The bridge crossing for the LLM-mediated steps: the decomposer's PRISM-IR-to-graph translation, the per-item relevance scorer, the briefing composer, and the round-trip recomposer. Real API calls; real billing; real cost accounting. | Anthropic — [`api.anthropic.com`](https://docs.anthropic.com/) |

The composition is bridged by 8OS's `kernel.bridge.cross` op against
the Anthropic bridge record at
[`ir/_kernel/bridge/anthropic.md`](https://github.com/deiasolutions/8os/blob/v1.1.0-dev.6/ir/_kernel/bridge/anthropic.md).
Bridge implementations live at
[`src/eightos/bridges/anthropic.py`](https://github.com/deiasolutions/8os/blob/v1.1.0-dev.6/src/eightos/bridges/anthropic.py)
(Block 3 Piece 3); resolver implementations at
[`src/eightos/factory/`](https://github.com/deiasolutions/8os/tree/v1.1.0-dev.6/src/eightos/factory)
and
[`src/eightos/resolvers/`](https://github.com/deiasolutions/8os/tree/v1.1.0-dev.6/src/eightos/resolvers).

## The PRISM-IR program

The workload root at
[`ir/dogfood-scan/scan-daily-briefing/_node.md`](https://github.com/deiasolutions/8os/blob/v1.1.0-dev.6/ir/dogfood-scan/scan-daily-briefing/_node.md)
carries the original `intention:` field verbatim:

> Each morning, fetch top items from selected sources, judge their
> relevance to a stated briefing topic, pick the top items by
> relevance, and compose a structured briefing artifact summarizing
> what's worth reading today.

Workload params:

```yaml
briefing_topic: AI infrastructure and governance, week of 2026-04-27
top_n: 5
fetch_window_hours: 24
```

Workflow (the four-node sequence the LLM decomposer translated the
informal intention into):

```
fetch-sources → score-relevance → filter-and-rank → generate-briefing
   (script)        (LLM)            (script)          (LLM)
```

Two of the four resolvers are bridge crossings (real Anthropic API
calls, real cost). Two are inside resolvers (no bridge, no cost). The
mix is what the demo witnesses: a single PRISM-IR document, a single
factory walk, mixed dispatch shapes, all observable in the same
ledger.

## The decomposer slot, filled by an LLM

8OS does not parse PRISM-IR directly. The kernel's pattern is to
register a **decomposer resolver** that reads a PRISM-IR document body
and emits a graph specification the kernel's materializer authors as
(I, R) records. The factory's walker then processes those records
uniformly — the kernel does not know or care whether the graph spec
was produced by deterministic Python or by an LLM.

SCAN fills the slot with an **LLM-bridged decomposer** at
[`src/eightos/factory/decomposer.py`](https://github.com/deiasolutions/8os/blob/v1.1.0-dev.6/src/eightos/factory/decomposer.py).
The decomposer crosses to the Anthropic Messages API under a vendored
prompt, sends the PRISM-IR body as the user message, and parses the
LLM's JSON reply as a graph spec. The reply is interpretive — the LLM
chooses how to translate the informal `intention:` prose into
structured nodes and edges, names the resolvers, and edits the
workflow as it sees fit (subject to the prompt's constraints). Two
runs of the decomposer against the same input could plausibly produce
different graph specs; the v1.1 calibration machinery tracks this
under `pi` (process consistency) — a `pi: 0.5` declared on the
LLM-bridged decomposer's `_kernel.resolver` record reflects exactly
that nondeterminism.

The same architectural slot is filled by:

- **Demo #1** (L-system) with a [deterministic in-process Python
  translator](https://github.com/deiasolutions/lsystem-demo/blob/main/harness/resolvers/prism_decomposer.py)
  that reads the PRISM-IR YAML body and unrolls back-edges using the
  program's `params.target_iterations`. `pi: 1.0` declared. See
  [`lsystem-demo/docs/koch-snowflake.md`](https://github.com/deiasolutions/lsystem-demo/blob/main/docs/koch-snowflake.md)
  for the deterministic-fill details.
- **Demo #3** (decomposition-strategy) with another [deterministic
  Python translator](https://github.com/deiasolutions/decomposition-strategy-demo/blob/main/harness/resolvers/prism_decomposer.py),
  ported from L-system, applied to a meta-program whose resolution is
  more PRISM-IR programs. See
  [`decomposition-strategy-demo/docs/writeup.md`](https://github.com/deiasolutions/decomposition-strategy-demo/blob/main/docs/writeup.md)
  for the self-composition framing.

**Three demos × three different fills cash out the slot's
generality.** SCAN supplies the LLM fill; the other two supply the
two deterministic fills (one shaping a known graph, one emitting new
programs). What's load-bearing is the slot's contract — *intention
body in, graph spec out* — not the resolver behind it.

## The (I, R) graph

The decomposer's graph spec materializes four kernel-hosted records
under
[`ir/dogfood-scan/scan-daily-briefing/`](https://github.com/deiasolutions/8os/tree/v1.1.0-dev.6/ir/dogfood-scan/scan-daily-briefing):

```
_node.md                          (root, expanded after decomposition)
scan-fetch-sources.md             depends_on: []
scan-score-relevance.md           depends_on: [scan-fetch-sources]
scan-filter-and-rank.md           depends_on: [scan-score-relevance]
scan-generate-briefing.md         depends_on: [scan-filter-and-rank]
```

Plus the round-trip check authored separately for Piece 6:

```
ir/dogfood-scan/scan-roundtrip-check.md           (recomposer's resolution)
```

Each record carries the standard 8OS frontmatter (id, scope, tier,
status, depends_on, parent, authored_by, authored_via, authored_on,
…). The kernel's read ops, the factory's walker, the resolution
events all work on these records the same way they work on the
L-system demo's records and Demo #3's records. The records are 8OS-typed;
nothing in their shape is SCAN-specific.

## The trace

Reconstructed from on-disk frontmatter timestamps. The original Block
3 run materialized all four children at 2026-04-28T02:12:11–12Z,
then resolved them in topological order:

| Tick | Resolver | Type | Authored | Resolved | Wall-clock |
|---|---|---|---|---|---:|
| 0 | `prism-ir-decomposer` (LLM) | bridge | — | (root expanded) | — |
| 1 | `fetch-sources` | script | 02:12:11.746Z | 02:12:15.711Z | **~4 s** |
| 2 | `score-relevance` (LLM) | bridge | 02:12:12.028Z | 02:12:26.445Z | **~14 s** |
| 3 | `filter-and-rank` | script | 02:12:12.311Z | 02:12:27.440Z | **~15 s** |
| 4 | `generate-briefing` (LLM) | bridge | 02:12:12.609Z | 02:13:01.061Z | **~49 s** |

Plus Piece 6's recomposer (separate dispatch under
`scan-roundtrip-check`):

| Tick | Resolver | Type | Result |
|---|---|---|---|
| 5 | `prism-ir-recomposer` (LLM) | bridge | reads the resolved graph; reconstructs English description without seeing the original PRISM-IR doc |

The two LLM bridges (`score-relevance`, `generate-briefing`) account
for almost all the wall-clock; the script resolvers run in
milliseconds inside the kernel binary. The trace is observable in
[`8os/.8os/events/2026/04/28/events.jsonl`](https://github.com/deiasolutions/8os) —
every bridge crossing is logged as a tier-3 event with cost,
duration, and authorization references.

## Real numbers

| Quantity | Value |
|---|---:|
| Total wall-clock (run 1: decomposition through generate-briefing) | ~49 s end-to-end (longest single resolver: generate-briefing at ~49 s; preceding nodes overlapped in dispatch order but resolved sequentially per dependency edges) |
| Anthropic API spend, total | **~$0.04** (decomposer + score-relevance + generate-briefing + recomposer) |
| Model | Claude Haiku 4.5 (all four LLM crossings) |
| Bridge crossings | 4 (decomposer, score-relevance, generate-briefing, recomposer) |
| Script resolver invocations | 2 (fetch-sources, filter-and-rank) |
| HTTP fetches (fetch-sources) | ~2 (HackerNews top stories + arXiv recent submissions in `cs.AI` / `cs.LG`) |
| Items returned by fetch-sources | ~20 |
| Items scored by score-relevance | ~20 (LLM call per item, batched in one prompt) |
| Items in final briefing | 5 (per `top_n: 5`) |
| (I, R) records authored end-to-end | 6 (the four-node sequence + root expansion + roundtrip-check) |

Costs are recorded honestly in each tier-3 event's `cost_actual`
field. The script resolvers declare `coin_usd: 0` (no API spend); the
LLM bridges declare per-call costs derived from token counts at
Haiku 4.5's published pricing.

## The artifacts

The original Block 3 run produced four artifacts, all preserved on
disk:

- [`docs/scan-block-3-bundle.md`](../scan-block-3-bundle.md) — the
  consolidated bundle that compiles the artifacts below for sharing.
- `.8os/dogfood-scan/artifacts/scan-generate-briefing.md` (4 KB) —
  the actual briefing artifact composed by Claude Haiku 4.5 from
  real HackerNews + arXiv items: "AI Infrastructure Shifts:
  Partnership Dissolution, Supply Chain Risks, and Governance Gaps."
  Five items, each with title, source attribution, URL, and
  contextualizing summary.
- `.8os/dogfood-scan/artifacts/scan-roundtrip-check-reconstruction.md`
  (2.3 KB) — the recomposer's English reconstruction of the
  workload, generated by Haiku 4.5 reading only the resolved (I, R)
  graph (no access to the original PRISM-IR document).
- `.8os/dogfood-scan/artifacts/scan-roundtrip-comparison.md` (7.9 KB)
  — side-by-side claim alignment + structural fidelity comparison
  between original and reconstruction. Human-judged verdict: high
  fidelity. The recomposer named all four resolvers verbatim,
  preserved the dependency order, and got the operator types right
  at every position. The single drift was the "each morning"
  cadence — a workload-meta-property the kernel never hosted in any
  node's resolution_text and therefore couldn't carry through. This
  is a real architectural finding (logged as
  [OPEN-Q-030](https://github.com/deiasolutions/8os/blob/v1.1.0-dev.6/docs/open-questions.md)
  — workload-meta-property propagation), not a recomposer failure.

The bundle doc consolidates these four into a single shareable
markdown file.

## Reproduce

The records and artifacts on disk are the canonical witness. Re-running
would produce different HN/arXiv content (the demo's external sources
move) but identical pipeline behavior. Reproduction is for verifying
durability, not for re-establishing the witness.

| System | Pin |
|---|---|
| 8OS binary | tag `v1.1.0-dev.6`; SCAN records committed at [`f4b3fd6`](https://github.com/deiasolutions/8os/commit/f4b3fd6) (Piece 5) and [`6741c37`](https://github.com/deiasolutions/8os/commit/6741c37) (Piece 6); bridge implementation at [`7f189f9`](https://github.com/deiasolutions/8os/commit/7f189f9) (Piece 3) |
| Decomposer registration | [`9c07642`](https://github.com/deiasolutions/8os/commit/9c07642) (Piece 4) |
| Anthropic API key | required (Claude Haiku 4.5; pricing per [docs.anthropic.com](https://docs.anthropic.com/)) |
| HackerNews + arXiv | public APIs; rate-limited but no auth |

Steps for a fresh replay (yields a different briefing — same shape,
different content):

```bash
# 1. Clone 8OS
git clone https://github.com/deiasolutions/8os.git
cd 8os
git checkout v1.1.0-dev.6

# 2. Install
uv venv && uv pip install -e .

# 3. Provision Anthropic credentials (Claude Code OAuth or env var)
#    Bridge implementation discovers credentials at dispatch time.

# 4. Clear prior children records (force fresh decomposer run + LLM calls)
rm -rf ir/dogfood-scan/scan-daily-briefing/scan-*.md
rm -rf ir/dogfood-scan/scan-roundtrip-check.md

# 5. Run the dogfood
.venv/bin/python scripts/run-scan-dogfood.py

# 6. Re-run the recomposer step (Piece 6, separate from the main flow)
#    See docs/internal/prompts/block-3-piece-6-prompt.md for the details.
```

Verifying the existing records replay clean (no fresh API calls,
zero spend):

```bash
.venv/bin/python scripts/run-scan-dogfood.py
# Expected: tick 1: leaves=0, briefing artifact path printed, exit 0
```

## Replay verification (Block 4.7 era)

The records were authored during Block 3 against a pre-Block-4 binary.
Re-verification at `v1.1.0-dev.6` (current HEAD as of this writeup):

| Check | Result |
|---|---|
| All 6 SCAN records load via `kernel.ir.list scope=dogfood-scan` | clean, no schema rejection |
| Records pass v1.1's amended frontmatter validators (`domain`, `data_classification`, `visible_when`, `authored_via`, cancelled-state, predicate shape) | clean |
| `scripts/run-scan-dogfood.py` against existing records | exit 0; tick 1: 0 leaves; briefing artifact path printed |
| `kernel.reindex --mode full` then `--mode check` | `drift_detected: False` |
| Tier-3 events from the original run | preserved on disk, readable, no migration required |

Records authored under one binary version remain valid records under a
later binary version that has added base-field validators, status enum
extensions, predicate engines, and policy evaluation phases. The
**durability across kernel evolution is itself a property worth
flagging**: the v1.1 amendments were structured to be additive
(per Block 4.5's housekeeping discipline) precisely so that real
workloads authored during the build don't need migration. SCAN is the
empirical witness that the additive-amendment discipline holds.

## Friction surfaced (preserved from original run)

The original run surfaced findings that have informed subsequent
architecture decisions:

- **OPEN-Q-029** — PRISM-IR node id namespacing in kernel id-to-path.
  PRISM-IR `nodes:` carry id fields scoped to the program; kernel
  slugs are globally unique. The original SCAN run hit this directly:
  PRISM-IR nodes named `fetch-sources`, `score-relevance`, etc. would
  have collided with the resolver records of the same names. The fix
  was a per-workload `scan-` prefix on the PRISM-IR doc's node ids.
  Workable for one demo; sketchy as a long-term pattern. **Resolved
  by Block 4.6's namespacing fix to the L-system decomposer**, which
  prefixes child node_ids with the parent program's id.
  Demo #3's decomposer ports the same fix.
- **OPEN-Q-030** — Workload-meta-properties (cadence, params,
  ownership) not surfaced in the round-trip. The recomposer correctly
  reconstructed the workflow but did not name the "each morning"
  cadence — a workload-meta-property that didn't appear in any node's
  `resolution_text`. This is a representation gap in the (I, R)
  graph, not a recomposer failure. Resolution candidates are
  enumerated in
  [`docs/open-questions.md`](../open-questions.md);
  pairs naturally with the broader PRISM-IR / 8OS interface
  amendments queue.
- **OPEN-Q-025** — Calibration corpus predicted/actual type
  heterogeneity, sharpened by the SCAN run. Each node JSON-encodes
  its structured output into `resolution_text` so the next node can
  `json.loads` it; the `resolution_text` field has become a
  type-erased channel. Resolution candidates: extending
  `kernel.ir.resolve` to accept a structured payload, or each
  resolver declaring its output shape in its `_kernel.resolver`
  record.
- **OPEN-Q-026** — Resolver and bridge frontmatter fields read by the
  factory but not declared in vendored projection bodies. The fields
  (`implementation`, `standing_authorization`, `intention_class`,
  `produces`, `module`, `prices`) accreted as the factory grew during
  Block 3. SCAN is the witness that the workaround (hand-authored
  records bypassing `validate_extensions`) suffices through Block 3;
  the formal amendment is queued for v1.0.1-full / v1.0.2.

These findings are preserved as historical record. They are not
blockers for the witness; the witness IS that the workload ran
end-to-end and produced a real briefing despite the substrate's then-
incomplete commitments. Subsequent kernel work has resolved most of
them.

## What this demo witnesses (and what it does not)

This demo witnesses **LLM-mediated decomposition with real outside-call
execution at substrate scale** — that the (I, R) primitive carries
enough architectural weight to host a workload whose decomposition is
nondeterministic (LLM interpretive translation), whose execution
crosses real bridges (HTTP + Anthropic API), whose intermediate state
flows through the kernel ledger as ordinary (I, R) resolutions, and
whose output is empirically interesting (a publishable daily
briefing). The empirical witness is the artifacts on disk and the
trace reconstructed above.

It does **not** witness:

- **PRISM-IR's expressive coverage** of the 43 Workflow Patterns. That
  is a separate formal claim made by the
  [PRISM-IR project](https://github.com/deiasolutions/prism-ir).
- **8OS's eight-axiom kernel ABI**. That is a separate structural
  claim of the 8OS project, evidenced by the kernel spec at
  [`docs/spec/8OS-KERNEL-SPEC-v0.1.md`](../spec/8OS-KERNEL-SPEC-v0.1.md)
  and the test suite that runs against it.
- **Strict reproducibility** of the briefing artifact. The HN and
  arXiv content moves; the LLM resolvers carry nondeterminism (`pi:
  0.5`); two runs against the same fixed time would produce
  different artifacts in detail. The witness is reproducibility *of
  the pipeline shape*, not of the content.
- **A specific quality threshold** for the LLM outputs. The briefing
  is a real, readable, accurate-to-its-sources artifact; whether it
  meets any specific editorial standard is application-level, not
  substrate-level. The substrate's job is hosting the work product;
  the work product's quality is the resolvers'.

The demo's claim is narrower than any of those, and is the one this
artifact actually establishes.

---

*Reciprocal references in the trio: this writeup is paired with
[`lsystem-demo/docs/koch-snowflake.md`](https://github.com/deiasolutions/lsystem-demo/blob/main/docs/koch-snowflake.md)
(Demo #1, deterministic decomposer + outside-call adapter) and
[`decomposition-strategy-demo/docs/writeup.md`](https://github.com/deiasolutions/decomposition-strategy-demo/blob/main/docs/writeup.md)
(Demo #3, self-composing decomposer + (I, R) graph as both
intermediate and output). The three writeups are paired evidence; the
decomposer-slot generality claim is fully cashed only with all three
in hand.*
