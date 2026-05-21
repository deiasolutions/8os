# SPEC-AUTONOMOUS-DISPATCH-001 — OUTLINE

**Status:** DRAFT OUTLINE — NEEDS DAVE INPUT  
**Author:** Q88N (with Claude drafting)  
**Date:** 2026-04-27  
**Block target:** TBD (Block 4 candidate)  
**Closes loop on:** Block 3 manual Mr Code dispatch

---

## 1. Purpose

Remove the human (Mr Code) from the normal-run dispatch path. After a one-time manual feed of this spec, the substrate authors and dispatches its own runs from PRISM-IR documents in a queue, end-to-end, with humans only in the spec-authoring, failure-review, and audit roles.

## 2. Scope

### 2.1 In scope
- Queue surface for PRISM-IR documents awaiting dispatch
- Daemon(s) that pick up queued docs and run the Block 3 pipeline (decompose → factory → recompose)
- Failure surfacing and ledger emission per run (success and failure)
- Three Currencies (Clock, Coin, Carbon) ledgered per run, including failures
- Integration with `REQUIRE_BUILD_INTEGRITY_FLOW=True`
- Integration with EXEC-03 `DeciderRouter` / `Channel`
- Retry policy (bounded)
- Operator escalation surface (where surfaced failures land)

### 2.2 Out of scope
- Authoring of new PRISM-IR docs by the substrate (that's the *next* recursion; this spec stops at "human writes spec → substrate runs spec")
- Pricing, billing, BYOK metering surfaces
- Interactive demo glass (chat.shiftcenter.com)
- Surrogate model training pipeline
- Parallel dispatch / fan-out (single-stream first; parallelism is a follow-on)

### 2.3 Non-goals
- Replacing Mr Code entirely. Mr Code still: writes specs, fixes breakages, reviews surfaced failures.
- AGI-style autonomous goal-setting. The substrate runs queued work; it doesn't decide what to queue.

## 3. Definitions

- **Normal run:** A PRISM-IR doc whose decomposition succeeds, whose factory dispatch completes within retry policy, and whose recomposition produces a validated artifact.
- **Escalated run:** Any run that fails decomposition, exhausts retries, or trips an integrity-flow check.
- **Queue surface:** Filesystem directory (state-machine convention) where PRISM-IR docs land for pickup.
- **Dispatch trigger:** The mechanism that wakes the daemon to check the queue.

## 4. Components

### 4.1 Queue surface
- Directory layout under existing state-machine convention (`backlog/` → `queue/` → `_active/` → `_done/` or `_failed/`)
- File naming convention for PRISM-IR docs awaiting dispatch
- **NEEDS DAVE INPUT (OPEN-Q-1):** Exact directory paths and naming.

### 4.2 Dispatcher daemon
- Picks up docs from queue
- Invokes decomposer
- Hands resolver graph to factory
- Invokes recomposer on completed graph
- Writes artifact to designated output location
- Emits ledger entries
- Pattern: derived from SPEC-MOBILE-WORKDESK-001 daemon shape (`scheduler_daemon.py` + `dispatcher_daemon.py`), reused for this purpose

### 4.3 Dispatch trigger
- **NEEDS DAVE INPUT (OPEN-Q-2):** Polling interval, filesystem watch, scheduled cadence (e.g., SCAN's 7am/11am/3pm), or hybrid?

### 4.4 Failure handling
- Per-run ledger entry on success and failure (Three Currencies + model + tokens in/out)
- Move failed runs to `_failed/` with diagnostic bundle
- **NEEDS DAVE INPUT (OPEN-Q-3):** Retry policy — max retries, backoff, what classes of failure are retryable vs. immediately escalated.

### 4.5 Operator escalation surface
- **NEEDS DAVE INPUT (OPEN-Q-4):** Where do escalated runs surface? Wiki page, dashboard pane, dedicated `_escalated/` directory, all of the above?

### 4.6 Integrity flow integration
- Runs under `REQUIRE_BUILD_INTEGRITY_FLOW=True` (assumed default after EXEC-02)
- Build integrity flow file lives in `.wiki/processes/`
- **NEEDS DAVE INPUT (OPEN-Q-5):** Does autonomous dispatch require any *additional* integrity gates beyond the existing flow, or is the existing flow sufficient?

### 4.7 DeciderRouter / Channel integration
- Autonomous daemon is the natural consumer of `DeciderRouter` (from EXEC-03)
- Channel routing for resolver dispatch unchanged from Block 3
- No new ops in 16-op SDK
- **NEEDS DAVE INPUT (OPEN-Q-6):** Confirm DeciderRouter has no autonomous-mode-specific configuration needed, or specify what config is needed.

## 5. Acceptance criteria

### 5.1 A normal run completes end-to-end with no human in the dispatch path.
### 5.2 A failed run produces a ledger entry, a diagnostic bundle, and surfaces to the operator escalation surface (4.5) without blocking subsequent queue items.
### 5.3 Three Currencies are ledgered for every run (success and failure).
### 5.4 The 16-op SDK contract is unchanged.
### 5.5 The kernel is unchanged.
### 5.6 No version bump of PRISM-IR.
### 5.7 The existing 247-test baseline still passes after this spec lands.
### 5.8 At least one autonomous run completes against a real PRISM-IR doc, end-to-end, and produces an artifact equivalent in fidelity to the Block 3 manual run.
### 5.9 Build integrity flow (`REQUIRE_BUILD_INTEGRITY_FLOW=True`) is not bypassed.
### 5.10 **NEEDS DAVE INPUT (OPEN-Q-7):** Any acceptance criterion specific to retry, escalation, or operator-review SLAs?

## 6. Dependencies

- Block 3 pipeline (`a8516bb`) — committed
- EXEC-02 (`REQUIRE_BUILD_INTEGRITY_FLOW`) — past
- EXEC-03 (`DeciderRouter` / `Channel`) — past
- SPEC-MOBILE-WORKDESK-001 daemon shape — referenced, not consumed; this spec authors its own daemon files in the right location
- State-machine directory convention (`_active/`, `_done/`, `backlog/`, `queue/`) — existing

## 7. Risks

### 7.1 Silent failure storm
A bug in the daemon could burn budget on retries. Mitigation: hard cap on Coin/Clock per run; daemon shuts itself off above threshold.

### 7.2 Drift between manual and autonomous artifact fidelity
The Block 3 run was supervised. Autonomous runs may produce subtly different artifacts. Mitigation: AC 5.8 requires fidelity equivalence on at least one matched comparison.

### 7.3 Integrity flow bypass through automation
Easy to accidentally route around the flow when removing the human. Mitigation: AC 5.9; integrity flow is non-optional.

### 7.4 **NEEDS DAVE INPUT (OPEN-Q-8):** Any other risk class you want explicitly enumerated?

## 8. Decomposition shape (for Mr Code)

This spec is a candidate for master-spec decomposition into ordered individual specs. Sketch:
- Piece 1: Queue surface + directory layout
- Piece 2: Dispatcher daemon skeleton (no dispatch yet, just queue read + ledger write)
- Piece 3: Pipeline integration (decompose → factory → recompose) inside daemon
- Piece 4: Failure handling + retry policy
- Piece 5: Operator escalation surface
- Piece 6: Integrity flow + DeciderRouter wiring confirmation
- Piece 7: End-to-end autonomous run against real PRISM-IR doc (AC 5.8)

**NEEDS DAVE INPUT (OPEN-Q-9):** Master-spec-with-decomposition, or single-shot spec? If master, confirm Piece order.

## 9. Open questions index

| ID | Section | Question |
|---|---|---|
| OPEN-Q-1 | 4.1 | Queue directory paths and file naming convention |
| OPEN-Q-2 | 4.3 | Dispatch trigger mechanism (poll / watch / scheduled / hybrid) |
| OPEN-Q-3 | 4.4 | Retry policy (max retries, backoff, retryable classes) |
| OPEN-Q-4 | 4.5 | Operator escalation surface (where do failures land) |
| OPEN-Q-5 | 4.6 | Additional integrity gates needed, or existing flow sufficient |
| OPEN-Q-6 | 4.7 | DeciderRouter autonomous-mode config |
| OPEN-Q-7 | 5.10 | Retry / escalation / SLA acceptance criteria |
| OPEN-Q-8 | 7.4 | Additional risk classes |
| OPEN-Q-9 | 8 | Master spec with decomposition vs. single-shot |

## 10. Naming

**NEEDS DAVE INPUT:** Spec name. Candidates:
- SPEC-AUTONOMOUS-DISPATCH-001
- SPEC-AUTONOMY-001
- SPEC-FACTORY-AUTONOMY-001
- SPEC-DISPATCH-AUTONOMY-001
- (your call)

---

**End of outline.**
