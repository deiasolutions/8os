# Block 4.5 — v1.1 Spec Amendments

**Status**: Authoritative. Resolves the eight v1.1 spec gaps that accumulated across the four tier-A implementation blocks (4.1–4.4). Edits to `8OS-BLOCK-1-SPEC-v1_1.md` are folded into the relevant sections of that document; this file documents what was edited and why. Same shape as `BLOCK-2.7-SPEC-CORRECTIONS.md` and `BLOCK-2.8-SPEC-AMENDMENTS.md` from prior housekeeping rounds.

**Provenance**: Authored by Q88N + Claude in dialogue, in the Block 4.5 implementation session dated 2026-04-29. The eight items are the queue surfaced during Blocks 4.1–4.4 implementation, recorded in each block's report and consolidated in `docs/build-state-2026-04-29.md`. Path A on item 5 (supersede-with-replacement of cancelled records via `kernel.ir.new` extension) was locked in the Block 4.5 prompt; this file ratifies it.

**Scope**: Amendments-only. No kernel code, no JSON schemas, no tests modified by this block. Implementation of the architecturally consequential item (Amendment 4 below) follows as Block 4.6.

**Relationship to v1.1.0 spec version**: After the in-place edits, the v1.1 spec's version stays at `1.1.0` (the spec was already published at v1.1.0; only the binary carries `-dev.N` suffixes during implementation). This file is the canonical record of what changed in v1.1's text between its initial draft (2026-04-28) and the post-tier-A consolidated version.

**Six in-place spec amendments and two appendix items.** Items are numbered 1–6 below; items 7 (`kernel.ir.list` `include_cancelled` default) and 8 (version-string-pin antipattern) are recorded in Appendix A for traceability without spec edits.

---

## Amendment 1 — Null vs empty string for optional string base fields

**Source**: Block 4.1 F5 + Block 4.3 F3 (`docs/block-4.1-report.md`, `docs/block-4.3-report.md`).

**Current spec**: v1.1 §4.7 ("Validation discipline") enumerates rejection cases but does not state how `null` and `""` should be distinguished for optional string base fields. Two such fields (`domain` per §4.3, `data_classification` per §4.2) are documented as `string | null, optional`. Block 4.1 (for `domain`) and Block 4.3 (for `data_classification`) both implemented `""` as a schema violation by parallel with v1.0.1-partial Amendment 2's explicit non-empty discipline for `authored_via`. The spec text was silent.

**Amendment**: Add a bullet to §4.7's "Validation rejects records that:" list, between the existing `authored_via` bullet and the `status` bullet:

> - Carry an empty string for any optional string base field (e.g., `domain`, `data_classification`); use `null` or omit the field to indicate the absence of a value.

The discipline now reads uniformly: optional string base fields use `null` (or omission) for absence; `""` is a schema violation. Pairs with v1.0.1-partial Amendment 2's explicit non-empty discipline for `authored_via`. Future optional string base fields inherit the discipline by default.

---

## Amendment 2 — `kernel.ir.cancel` output: drop `cancellation_event_id`

**Source**: Block 4.2 F1 (`docs/block-4.2-report.md`).

**Current spec**: v1.1 §3.8's output table lists both `cancellation_event_id` and `tier3_event_id` as separate fields. Per §3.8's atomicity clause, exactly one tier 3 cancellation event is written per call. The two field names refer to the same id.

**Amendment**: Drop `cancellation_event_id` from §3.8's output. The amended output is:

```json
{ "ir_status_after": "cancelled",
  "affected_dependents": <int>,
  "dropped_pending_ops": <int>,
  "tier3_event_id": "<id>" }
```

`tier3_event_id` is the canonical name, matching every other op in §3 that writes a tier 3 event (resolve, expand, supersede, promote, etc.). The implementation already returns `tier3_event_id`; this amendment makes the spec text agree.

This is a pre-publication amendment (v1.1 has no released callers depending on `cancellation_event_id`), so no alias is documented. Block 4.2's `data.cancellation_event_id` (echoed for callers reading structured output) is removable in Block 4.6 without backward-compat risk.

---

## Amendment 3 — `IR_NOT_CANCELLABLE` description: drop `stale`

**Source**: Block 4.2 (primary spec finding) (`docs/block-4.2-report.md`).

**Current spec**: Three sections speak to which statuses reject `kernel.ir.cancel`:

- v1.1 §5.2 (transition table) explicitly permits `stale → cancelled`.
- v1.1 §3.8 (errors): `IR_NOT_CANCELLABLE` (already `superseded` or `stale` — supersede or let stale persist).
- v1.1 §18.1: `IR_NOT_CANCELLABLE` — (I, R) status is `superseded` or `stale`; supersede or let stale persist instead.

§5.2 contradicts §3.8 and §18.1. §5.2 is the authoritative source for state transitions; §3.8's error list and §18.1's repetition are caching errors of an earlier draft. Block 4.2 implemented against §5.2; the binary permits cancelling `stale` records. Test 3 in `tests/kernel/test_block_4_2_cancel.py` locks the behavior.

**Amendment to §3.8**: Update the errors line to read:

> **Errors**: `IR_NOT_FOUND`, `IR_ALREADY_CANCELLED`, `IR_NOT_CANCELLABLE` (status is `superseded`; supersede the new content instead), `CANCELLATION_AUTHORITY_INSUFFICIENT`, `LEASE_HELD`, `POLICY_DENIED`.

**Amendment to §18.1**: Update `IR_NOT_CANCELLABLE`'s description to read:

> `IR_NOT_CANCELLABLE` — (I, R) status is `superseded`. The state must be in `{open, resolved, stale}` for cancellation. Already-cancelled records reject with `IR_ALREADY_CANCELLED`; superseded records cannot be cancelled (supersede the new content instead).

§5.2's transition table is unchanged. After this amendment, all three sections agree.

---

## Amendment 4 — `kernel.ir.new` accepts `supersedes:` for supersede-with-replacement of cancelled records

**Source**: Block 4.2 F3 (`docs/block-4.2-report.md`). The architecturally consequential item.

**Path committed (Path A, locked in the Block 4.5 prompt)**: extend `kernel.ir.new` (v1.1 §3.2) with an optional `supersedes:` field. `kernel.ir.supersede` (§3.7) keeps its current contract — it operates only on living records (`open`, `resolved`, `stale`); it rejects `cancelled` and `superseded` targets. Reversal of a cancellation is a creation act with explicit lineage to the cancelled record, not a mutation of the cancelled record.

**Rationale (recorded for the historical record; Path A is locked)**:

- v1.1 §5.2 makes `cancelled` terminal. `kernel.ir.supersede` operates on the living lineage; reaching into the cancelled state from supersede would give "supersede" two different meanings depending on the target's status.
- Lineage from a cancelled record is a property of the *new* record, not of the *old* one. Path A names that correctly. The audit trail reads: cancellation event, gap, then a creation event with backward-pointing lineage.
- Skill revocation cascade (per §9.6) and policy supersession of cancelled policies (per §8.8) both read more cleanly when the cancelled record stays terminal and the new record carries the lineage pointer.
- Cancelled records remain immutable. Path B would have required writing to a terminal record, weakening the terminal-state invariant.

### 4a — Amendments to §3.2 (`kernel.ir.new`)

**Input schema** — add an optional field. The amended input is:

```json
{ "scope": "<scope-id>",
  "id": "<slug>",
  "projection_types": [<projection-type-string>, ...],
  "frontmatter": { ...base 8OS fields... },
  "frontmatter_extensions": { ...projection-declared fields... },
  "body": "<markdown-string>",
  "authored_via": "<bridge-string>",
  "supersedes": "<ir-id>"|null }
```

Default: `null`. When non-null, the kernel validates: (a) the target id exists (`IR_NOT_FOUND` if not); (b) the target's status is `cancelled` (`IR_SUPERSEDES_TARGET_NOT_CANCELLED` otherwise). The target's scope is unconstrained — cross-scope reversal is permitted at v1.1. A future amendment may add a same-scope constraint if sovereignty boundaries demand it; v1.1 does not.

**Output**: when `supersedes` is non-null, the new record's frontmatter carries the `supersedes:` lineage pointer. The cancelled target's frontmatter is unchanged: no `superseded_by` is written, no status transition, no event is emitted on the target. The cancelled record stays terminally `cancelled`; the lineage is one-directional from the new record only.

The `kernel.ir.new` output schema gains no new fields. The act of creating an (I, R) with `supersedes:` is recorded in the new record's frontmatter and in the standard creation tier 3 event.

**Errors** — append `IR_NOT_FOUND` and `IR_SUPERSEDES_TARGET_NOT_CANCELLED` to §3.2's errors list. The amended list:

> **Errors**: `ID_CONFLICT`, `SCHEMA_INVALID`, `CONFLICTING_PROJECTION_FIELDS`, `CONFLICTING_PROJECTION_TARGETS`, `AUTHORITY_INSUFFICIENT`, `SCOPE_NOT_FOUND`, `LEASE_HELD`, `POLICY_DENIED`, `CLASSIFICATION_VIOLATION`, `IR_NOT_FOUND`, `IR_SUPERSEDES_TARGET_NOT_CANCELLED`.

`IR_NOT_FOUND` covers the case where `supersedes` references a non-existent id — matching the kernel's existing pattern of using `IR_NOT_FOUND` uniformly for "id doesn't exist" (cf. `kernel.ir.supersede`, `kernel.ir.resolve`, `kernel.ir.cancel`). `IR_SUPERSEDES_TARGET_NOT_CANCELLED` covers the case where the target exists but is not in `cancelled` status. The split mirrors `kernel.ir.cancel`'s own pattern (`IR_NOT_FOUND` vs `IR_NOT_CANCELLABLE`).

**New supersede-with-replacement clause** to add to §3.2 between "Required field" and "Lease check":

> **Supersede-with-replacement of cancelled records**: when the `supersedes` input is non-null, the new (I, R) is authored as a replacement for a previously-cancelled target. The target must exist and have status `cancelled`. The new (I, R) carries `status: open` and a frontmatter `supersedes:` pointer to the cancelled target. The cancelled target is not mutated by this op; it remains terminally `cancelled` with no forward pointer to the new record. Discovery of "what replaced this cancelled record" is via index lookup on the new records' `supersedes:` field, not a property of the cancelled one. This is the canonical reversal path named in §3.8's reversibility clause; `kernel.ir.supersede` (§3.7) remains the path for living records and rejects cancelled targets.

### 4b — Amendments to §3.8 (`kernel.ir.cancel`)

The existing reversibility clause names the mechanism in prose but does not cross-reference §3.2's input field. Amend the clause to read:

> **Reversibility**: cancellation is terminal. There is no "uncancel" op. Going forward from a cancelled (I, R) requires authoring a new (I, R) via `kernel.ir.new` (§3.2) with the optional `supersedes: <cancelled-id>` input field. The new (I, R) carries `status: open` and a frontmatter `supersedes:` pointer to the cancelled target; the cancelled (I, R) remains `status: cancelled` permanently and is not mutated by the new authoring. Both records persist; the lineage is unidirectional (new record points back at the cancelled target; cancelled target carries no forward pointer to its replacement). This asymmetry is intentional: cancelled records are immutable, and discovery of replacements is via index lookup on the new records' `supersedes:` field rather than a forward-pointer on the cancelled one.

The updated clause makes the mechanism implementable as written and clarifies the asymmetry from `kernel.ir.supersede` (which writes bidirectional pointers; this path writes the unidirectional pointer only).

### 4c — Amendments to §5.2 (transition table)

None. Cancellation stays terminal. The new (I, R) is a separate record at `status: open`, not a transition of the cancelled one. The forbidden transition `cancelled → anything` remains in §5.2 verbatim — Path A respects it precisely because the new record is a *new* record, not a transition of the old one.

### 4d — Amendments to §18.1 (error codes)

Add the new error code under "(I, R) lifecycle errors":

> `IR_SUPERSEDES_TARGET_NOT_CANCELLED` — `kernel.ir.new` was called with a `supersedes:` input pointing at an (I, R) whose status is not `cancelled`. Supersede-with-replacement applies only to cancelled records; for living records (`open`, `resolved`, `stale`), use `kernel.ir.supersede` (§3.7).

Placement: between the existing `IR_NOT_CANCELLABLE` and `IR_ALREADY_CANCELLED` entries (the cancellation-related cluster).

### Implementation follow-up

Block 4.6 implements the `supersedes:` field on `kernel.ir.new`'s input schema and handler, the two new error code emissions, and the `kernel.ir.list` `include_cancelled` default fix from Appendix A. Block 4.2's skipped Test 12 (`test_supersede_with_replacement_after_cancellation`) unskips at that point.

---

## Amendment 5 — Public `resolve_*` helper convention

**Source**: Block 4.1 F4 (`docs/block-4.1-report.md`), reaffirmed in Block 4.3.

**Current spec**: v1.1 §4.7 enumerates validation discipline at write time and reindex time but says nothing about how the reference implementation resolves base-field inheritance (record-level → scope-default → null). Blocks 4.1 (`domain`) and 4.3 (`data_classification`) implemented public helpers (`resolve_domain`, `resolve_data_classification`) parallel to the existing private helper (`_resolve_stakes`); the public scope was an intentional divergence from the stakes pattern, justified by anticipated reuse across multiple v1.1 base fields. The convention was established de facto across two blocks but is not in spec.

**Amendment**: Add a paragraph at the end of §4.7, after the existing rejection bullet list:

> **Resolution-helper convention (reference implementation)**: helpers that resolve base-field inheritance (record-level → scope-default → null) are public-scoped, parallel to `resolve_domain` (§4.3) and `resolve_data_classification` (§4.2) in the reference implementation. Future optional base fields with scope-default inheritance follow the same shape and naming. This is reference-implementation guidance, not a contractual obligation on alternative kernel implementations.

Naming the two existing helpers anchors the convention concretely so the next base-field block doesn't reinvent it as private.

---

## Amendment 6 — `not` semantics for `visible_when` predicates

**Source**: Block 4.4 F5 (`docs/block-4.4-report.md`).

**Current spec**: v1.1 §4.4 specifies `any`, `all`, and `not` as composite operators for `visible_when` predicates. The semantics of `not` for multi-element arrays is not stated. Block 4.4 implemented "none-of-array" semantics: `not: [a, b]` evaluates true iff every child evaluates false (logically `not (a or b)`). Test 17 in `tests/kernel/test_block_4_4_visible_when.py` locks this behavior. The spec was silent.

**Amendment**: Add a sentence to §4.4, immediately after the prose paragraph that introduces `any`, `all`, and `not` (the paragraph beginning "Predicates compose `any` (logical OR), `all` (logical AND), and `not`."):

> **`not` semantics for multi-element arrays**: `not: [a, b, ...]` is logically `not (a or b or ...)` — the kernel evaluates the array as a disjunction and negates the result. The composite is true when every child evaluates false (none-of-array semantics). Equivalently, `not: [a, b]` is interchangeable with `all: [{not: [a]}, {not: [b]}]` for binary cases; the `not:` shape is the canonical compact form.

---

## Appendix A — Items recorded for traceability (no spec edits)

### Item 7 — `kernel.ir.list` `include_cancelled` default (implementation gap, scheduled for Block 4.6)

**Source**: Block 4.2 F5 (`docs/block-4.2-report.md`).

**Status**: v1.1 §3.10 already specifies the discipline correctly:

> Defaults: `include_kernel: false` (results from `_kernel` scope are excluded by default per v0.2 §4.2). `include_cancelled: false` (cancelled (I, R)s are excluded by default to avoid surprising callers; explicit opt-in to see them).

The gap is between spec and implementation. The current `kernel.ir.list.v1.input.json` schema lacks the `include_cancelled` field; the handler does not filter cancelled records. No spec change is required.

**Resolution path**: Block 4.6 (the `supersedes:`-on-`kernel.ir.new` implementation block per Amendment 4) bundles the `include_cancelled` schema-and-handler fix. Adding the field to `kernel.ir.list.v1.input.json` and the handler's filter logic is a small additive change; bundling with Block 4.6's main work costs nothing.

### Item 8 — Version-string-pin antipattern in upgrade-path tests

**Source**: Block 4.3 F1 (named) + Block 4.4 F3 (recurred) (`docs/block-4.3-report.md`, `docs/block-4.4-report.md`).

**Status**: project-discipline note. Not a v1.1 spec item.

**Pattern**: Tests asserting against version transitions must use the `KERNEL_VERSION` import from `src/eightos/__init__.py`, not hard-coded version literals (e.g., `"1.1.0-dev.3"`). Hard-coded literals tie the test to a specific block's version and break silently at the next bump. Block 4.3 (`tests/kernel/test_block_4_2_cancel.py::test_upgrade_from_dev1_to_dev2_is_clean`) and Block 4.4 (`tests/kernel/test_block_4_3_data_classification.py::test_upgrade_from_dev2_to_dev3_refreshes_scope_body`) each surfaced the antipattern in tests written by the prior block.

**Convention**: Upgrade-path tests use `KERNEL_VERSION` to assert the post-upgrade version. The test name should not pin a specific dev-version (rename `test_upgrade_from_dev2_to_dev3_*` to `test_upgrade_from_dev2_*`). When the test needs to capture both endpoints of an upgrade, the source endpoint is fixture-set (rewinding `.8os/version` to the prior literal) and the target endpoint is `KERNEL_VERSION`.

**Future tooling option (deferred)**: A helper `assert_upgrade_to_current(env, previous_version)` could be factored out to encapsulate the convention; or a lint rule flagging `r'"\d+\.\d+\.\d+-dev\.\d+"'` literals in test files could prevent reintroduction. Either is its own small block; not amendment-shaped.

---

*End of Block 4.5 Spec Amendments.*
