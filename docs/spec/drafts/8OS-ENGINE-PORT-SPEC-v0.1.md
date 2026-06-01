---
spec_id: 8OS-ENGINE-PORT-SPEC
version: 0.1.0
status: DRAFT — §A/§C/§D/§E helpers implemented (Slice 1); §B Session + §E
  containment enforcement proposed
kind: spec-draft
scope: project
depends_on: 8OS-KERNEL-SPEC-v0.2; 8OS-BLOCK-1-SPEC-v1_2; TURTLES-PRINCIPLE-v0_1
date: 2026-06-01
---

# 8OS Engine Port — v0.1 (draft)

## Purpose

The **engine port** is the single contract that an orchestration engine targets
to drive 8OS: it is what an external engine (e.g. a discrete-event simulator)
hosts, what the in-tree reference orchestrator (the *factory*,
`src/eightos/factory/`) implements, and what a downstream host imports to consume
8OS as a dependency.

8OS stays the **substrate**: it records truth (the tier-3 event ledger), gates
single outside-calls, and contains leaks. Forecasting, fleet budgeting, and
whole-program simulation are the **engine's** job, not the substrate's.

## One contract, two transports

The same op-dispatch core is reachable two ways:

- **In-process** — `eightos.api` (this spec). The only supported import surface;
  everything `_`-prefixed is internal. Ships `py.typed`.
- **Subprocess** — the `8os <op>` JSON wire contract (host-agnostic).

The in-process surface is a **thin typed façade** over the same dispatch the CLI
calls. Per the non-redundancy rule it *references* existing canon — the operation
set (Block-1), base frontmatter, projection-declared `required_frontmatter` — and
only *defines* the genuinely-new surface (execution mode, cost read, conformance).

## Surface

### A. Op dispatch — `run(op, payload) -> envelope`
Dispatches the seventeen SDK operations + `kernel.outside.http`. Op names and
payload/return shapes are defined by Block-1 + the per-op JSON schemas; not
restated here. Implemented (`eightos.api.run`).

### B. Execution session — simulate vs real *(proposed)*
```
Session(repo, *, mode="real" | "simulate")   # context manager; carries batch_id + mode
```
A run/session carries an ambient **mode**; everything dispatched inside inherits
it, like a transaction. In `simulate`, bridge crossings (`kernel.bridge.cross`,
`kernel.outside.http`) **do not fire** — they return a forecast and record an
*alterverse* branch rather than a real tier-3 crossing. A `simulate` session
cannot emit a real outside-call (**proof, not bake**). Inside-only programs behave
identically in both modes; the mode gates only the inside/outside boundary
(axiom 0). Mode lives on the session, not per-op or global.

### C. Orchestration primitives
- `leaves(repo, scope) -> list[IRRecord]` — dispatchable leaves (open, deps
  resolved, non-configuration). Implemented.
- `emit_marker(repo, *, kind, payload, ...) -> event_id` — an engine-authored
  tier-3 marker event, the supported replacement for hand-importing the event
  writer (axiom-8-clean). Implemented.
- Types: `IRRecord`, the adapter contract `Adapted = {resolution_text,
  resolution_value?, cost_actual}`, and the resolver `Produces = "value"|"graph"`
  convention.

### D. Cost surface
- `cost_of(envelope_or_event) -> CostVector` — read the three-currency cost
  (`clock_ms`/`coin_usd`/`carbon_g`) off a result or event. Implemented.
- Per-call budget gates are existing operations — `kernel.outside.http` (budget /
  rate / expiry) and `_kernel.lease` — referenced, not re-specified. The port
  **emits** per-(I,R) cost and exposes the lease/gate primitives; it does **not**
  own a fleet budget ledger. Fleet-level budgeting is an engine concern.

### E. Conformance + leak containment
- `is_feedable(record) -> {feedable, missing}` — checks the **canonical** base
  fields a record must carry to be fed to the factory (a subset of
  `BASE_FRONTMATTER_FIELDS`); projection-specific `required_frontmatter` is
  validated authoritatively by `kernel.ir.new`. Implemented.
- **Leak containment** *(proposed enforcement):* a program that spawns programs
  must spawn *feedable* ones. By axiom 0, a carry-forward leak forces a later
  crossing back to the outside to recover lost value — a real cost in Coin /
  Carbon / Clock, and a reversal of axiom 7's inward migration. Containment is
  therefore a requirement, enforced at materialization:
  - spawned node ids are **auto-namespaced** (uniqueness carries forward);
  - workload-level metadata (cadence, ownership, `data_classification`, params)
    **passes through** decompose→recompose (it stays inside the graph).

## Design decisions

- **D1** — Prediction-economics (calibration / VOI / holdout) is **engine-side**,
  not port surface. 8OS exposes only the lineage and prediction *records*.
- **D2** — Execution mode is **per-session** (§B).
- **D3** — The **fleet budget ledger is engine-side**; the port emits per-(I,R)
  cost + per-call gates only. (The tier-3 event/audit ledger is 8OS-side and
  unaffected.)
- **D4** — The feedability field set is defined **by reference** to existing
  canon (non-redundant); leak containment is a firm requirement (§E).

## Implementation status

- **Implemented (Slice 1):** `eightos.api` — `run`, `leaves`, `emit_marker`,
  `cost_of`, `is_feedable`, the public types, and `py.typed`. No behavior change
  to existing operations; the façade only exposes existing canon plus pure reads.
- **Proposed (subsequent slices):** the `Session` simulate/real API (§B) and the
  materialization-time leak containment (§E).

## Anti-privilege note (Turtles)

The port keeps orchestration expressible as a program the engine runs, never a
privileged layer above the substrate (`TURTLES-PRINCIPLE-v0_1`): no exempt voice.
The engine's own self-claims (forecasts, budget decisions) re-enter 8OS as (I, R)
records on the same graph — which is why surrogate lineage and prediction records
live in 8OS even though the forecasting that produces them is engine-side.
