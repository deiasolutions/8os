---
id: 8OS-BLOCK-1-SPEC-v1.0.1-PARTIAL
version: 1.0.1-partial
status: accepted
kind: amendment
scope: project
domain: 8os/representation
authored_by: Q88N + Claude (Chat 4 spec round)
authored_on: 2026-04-27
supersedes: null
amends: 8OS-BLOCK-1-SPEC v1.0.0
superseded_by: 8OS-BLOCK-1-SPEC v1.1.0
depends_on: 8OS-KERNEL-SPEC v0.1.0, 8OS-BLOCK-1-SPEC v1.0.0
revisit_when: implementation surfaces a contradiction with these amendments or with the eight axioms
provenance: Block 2.9 surfaced OPEN-Q-021, OPEN-Q-022, OPEN-Q-023; this amendment resolves them
---

# 8OS Block 1 Spec v1.0.1-partial — Amendments

> **Active spec is v1.1.** This v1.0.1-partial document remains the
> immediate predecessor; the active representation is v1.1
> ([`8OS-BLOCK-1-SPEC-v1_1.md`](./8OS-BLOCK-1-SPEC-v1_1.md)), which
> folds in v1.0.1-partial's three amendments (subdirectory discipline,
> mandatory `authored_via`, per-version body seal) plus OPEN-Q-019
> (`domain` lifted to optional base frontmatter, closed in Block 4.1).
> Read v1.1 for the active architectural commitment; read this
> document for the immediate predecessor's amendments.

## What this document is

This is a **partial** v1.0.1 amendment to 8OS-BLOCK-1-SPEC v1.0.0. It resolves three of the five open questions Block 2.9 surfaced (OPEN-Q-021, OPEN-Q-022, OPEN-Q-023) and explicitly defers two (OPEN-Q-024, OPEN-Q-025) plus one previously-deferred (OPEN-Q-019).

This is not a full v1.0.1. The full v1.0.1 will fold the deferred items when their answers are ready. This partial round addresses what Block 3 (the factory) needs resolved before it starts.

The discipline matches Block 2.7's spec-corrections file and Block 2.8's amendments file: spec changes ship in this document; implementation work happens in a separate Mr Code session against this spec.

## Status of v1.0.0

v1.0.0 stands. This document amends three sections of v1.0.0; all other sections are preserved verbatim. A v1.0.0 implementation that adopts these amendments becomes a v1.0.1-partial implementation. A future v1.0.1 (full) will supersede this document.

---

## Amendment 1 — Subdirectory discipline for `_kernel.*` records (resolves OPEN-Q-021)

### Background

v1.0 §3.1 (`_kernel.prediction`), §3.2 (`_kernel.calibration-policy`), and §3.3 (`_kernel.calibration-policy-proposal`) specify on-disk subdirectory layout:

- `_kernel.prediction` → `ir/<scope>/_predictions/<id>.md`
- `_kernel.calibration-policy` → `ir/<scope>/_calibration-policies/<policy-id>.md`
- `_kernel.calibration-policy-proposal` → `ir/<scope>/_calibration-proposals/<id>.md`

v1.0 implementation (`ir_ops.py:new`, lines 178-181) writes them flat in `ir/<scope>/`, distinguished only by filename suffix from projection.

This is a spec/implementation divergence. Block 2.9's report (OPEN-Q-021) flagged it as a design decision needing resolution.

### Resolution

**Implementation conforms to spec.** v1.0 §3.1, §3.2, §3.3 stand as written. The subdirectory layout is the discipline.

The mechanism by which the writer learns where to place a record is **configuration-as-content**, consistent with Block 2.7's principled-path ruling: the projection definition itself declares its target subdirectory.

### Spec changes

#### Projection definition body schema gains optional `target_subdirectory` field

The vendored body schemas for kernel-defined projection types (at `.8os/projections/_kernel/<type>.yml`) gain an optional field:

```yaml
target_subdirectory: <subdirectory-name>   # Optional. If present, records of this projection
                                           # type are written to ir/<scope>/<target_subdirectory>/<id><filename_suffix>.
                                           # If absent, records are written flat at ir/<scope>/<id><filename_suffix>.
```

This is parallel in shape to the existing `filename_suffix:` mechanism: the projection knows where its records go; the writer queries the projection.

#### Three vendored projection bodies updated

The following vendored projection definitions gain `target_subdirectory:` declarations:

```yaml
# .8os/projections/_kernel/prediction.yml
target_subdirectory: _predictions

# .8os/projections/_kernel/calibration-policy.yml
target_subdirectory: _calibration-policies

# .8os/projections/_kernel/calibration-policy-proposal.yml
target_subdirectory: _calibration-proposals
```

These are body amendments to vendored projections. Per Amendment 3 below (body-refresh discipline), they are sealed within v1.0.1-partial and refresh on `kernel.init` upgrade-mode at the v1.0.0 → v1.0.1-partial transition.

#### `kernel.ir.new` writer behavior

When writing a record:

1. Resolve the projection definition for the record's `projection_types`.
2. Read the projection's `target_subdirectory:` and `filename_suffix:` fields.
3. If `target_subdirectory:` is present, the target path is `ir/<scope>/<target_subdirectory>/<id><filename_suffix>`.
4. If `target_subdirectory:` is absent, the target path is `ir/<scope>/<id><filename_suffix>`.

If a record has multiple `projection_types` declaring conflicting `target_subdirectory:` values, the operation rejects with `CONFLICTING_PROJECTION_TARGETS`. (Same shape as existing conflict handling for `frontmatter_extensions`.)

### Migration

Existing v1.0.0 records authored under the flat layout are relocated to their projection-declared subdirectories. The migration script (`scripts/migrate-v1.0-to-v1.0.1-partial.py`) is idempotent, reads each existing record's projection_types, looks up the target_subdirectory from the (refreshed) projection definition, and moves the file. Same pattern as `migrate-v0.1-to-v0.2.py`.

---

## Amendment 2 — `authored_via` is mandatory (resolves OPEN-Q-022)

### Background

v1.0's `kernel.ir.new` operation has no input parameter for `authored_via`. Records authored via the SDK have `authored_by` populated but `authored_via` always null. The cogito story's three-field provenance — who (`authored_by`), when (`authored_on`), through-what-bridge (`authored_via`) — is incomplete for all tier 1 user content.

### Resolution

**`authored_via` is mandatory on every (I, R) record.** Generalizes axiom 0: every act of authorship enters the kernel through a named bridge.

Two named values cover the entire authorship space at v1.0.1-partial:

- `kernel.self` — the cogito bridge. Used by internal kernel operations (init, reindex, migration events) authoring records on the kernel's own behalf.
- `outside` — the generic bridge for any authorship not originating from internal kernel ops. Per axiom 0, anything not internal is outside; the bridge through which outside enters is, generically, `outside`.

Future refinement may name narrower outside-bridges (`outside.human-sdk`, `outside.api-caller`, `outside.import-script`); these are subtypes of `outside` and do not break the schema.

### Spec changes

#### `kernel.ir.new` parameter

`kernel.ir.new` accepts `authored_via` as a **required** parameter. Type: string. Validated to be non-empty.

#### SDK default

The SDK layer defaults `authored_via` to `outside` for callers who do not specify it. This default is enforced at the SDK boundary, not at the kernel. From the kernel's perspective, the parameter is always supplied.

Internal kernel operations (`kernel.init`, `kernel.reindex`, migration scripts, `kernel.bridge.cross` self-events) **must** explicitly pass `kernel.self`. The SDK default does not apply to these.

#### Record frontmatter schema

The base 8OS frontmatter schema gains `authored_via` as a **required** field, parallel to `authored_by` and `authored_on`. Records without `authored_via` are invalid.

#### `kernel.reindex --check` enforcement

`kernel.reindex --check` validates that every record carries `authored_via`. Records lacking the field are reported as schema violations.

### Migration

The migration script backfills `authored_via: outside` for all v1.0.0 records that lack the field. Internal-origin records (those whose `authored_by` matches a known kernel-internal author, e.g., the migration runner itself) backfill with `kernel.self`.

The migration is idempotent. Records already carrying `authored_via` are left unchanged.

---

## Amendment 3 — Vendored body seal discipline (resolves OPEN-Q-023)

### Background

Block 2.7's spec said vendored projection bodies are "sealed at kernel ship." Block 2.8 amended `_kernel.authorization` additively, requiring sealed bodies to refresh. Block 2.9's `kernel.init` upgrade-mode actively refreshes vendored bodies on version-boundary transitions. The v1.0 spec text does not reconcile "sealed" with "refreshed across versions."

### Resolution

**Vendored projection bodies are sealed for the lifetime of a kernel version.** The seal is per-version, not absolute.

### Spec changes

The following text is added to v1.0 §3 (or the nearest equivalent section that introduces vendored projections):

> ### Vendored projection body seal
>
> Vendored projection bodies (the `body_schema` content shipped at `.8os/projections/_kernel/<type>.yml`) are owned by the kernel binary. They are sealed for the lifetime of a single kernel version: within a version, the bodies do not change.
>
> Bodies refresh during `kernel.init` upgrade-mode when the binary's version is newer than `.8os/version`. The refresh writes the binary's current vendored bodies to disk, replacing prior versions. Records already authored against prior bodies remain valid as long as the new bodies are additive-compatible (new optional fields, no removed required fields, no semantic redefinition of existing fields).
>
> Body amendments require a kernel version bump. A patch to a vendored body without a version bump is a discipline violation.
>
> The kernel binary is the unit of body authority across versions. Two kernel binaries with the same version string MUST ship identical vendored bodies.

### Implications

- v1.0.1-partial bumps the kernel version. Vendored bodies refresh on init.
- Future development binaries that diverge from a released version must declare a different version string (e.g., `1.0.2-dev.1`) to avoid violating the per-version-identity invariant.
- The Block 2.7 phrasing "sealed at kernel ship" is superseded by the per-version seal articulated here. v1.0.1-partial supersedes that wording.

---

## Deferred — not addressed in v1.0.1-partial

The following open questions remain open after this amendment:

### OPEN-Q-019 — `domain` as base frontmatter

`domain` should be base frontmatter parallel to `stakes`, enabling `applies_to_domain` matching for calibration policies. Block 2.9 worked around it with scope-only matching.

**Why deferred:** Mechanical fold-in. Not blocking Block 3. Will land in a future v1.0.1-full or v1.0.2 alongside any other accumulated mechanical amendments.

### OPEN-Q-024 — VOI cost-vector degeneracy at zero costs

VOI's expected-loss math collapses when both compared resolvers have `coin_usd = 0`: the no-information strategy and the escalate strategy produce identical EL, making "predict-only" and "predict-then-conditional-escalate" unreachable. Block 2.9's kernel-internal pytest workload hit this.

**Why deferred:** Block 3's factory will dispatch real LLM predictors with non-zero `coin_usd`. The empirical signal from that workload is the cleanest answer to whether the math degeneracy is a spec concern or whether reality bails it out. Holding 024 open through Block 3 is intentional.

### OPEN-Q-025 — Calibration corpus predicted/actual type heterogeneity

Predictions store `predicted_value` (e.g., `<bool>`); actuals store the full `resolution_text` string. Future calibrators comparing predicted vs actual need parsing logic; the corpus does not ship a normalized comparison shape.

**Why deferred:** Affects future calibrators across many domains. The right fix is shaped by which domains accumulate first, which Block 3 will surface. Not blocking.

---

## Implementation expectations for the Mr Code session

A separate session executes this amendment against the v1.0.0 codebase. Same shape as Block 2.7 corrections and Block 2.8 amendments.

Expected deliverables:

1. **Code changes**:
   - `ir_ops.py:new` reads `target_subdirectory` from projection definition and writes accordingly. Conflict handling for multiple-projection-type records.
   - `kernel.ir.new` requires `authored_via` parameter. Validation: non-empty string.
   - SDK layer defaults `authored_via` to `outside` for non-internal callers.
   - Internal kernel operations (init, reindex, migration, bridge.cross self-events) explicitly pass `kernel.self`.
   - `kernel.reindex --check` validates `authored_via` presence.

2. **Vendored body updates**:
   - `.8os/projections/_kernel/prediction.yml` gains `target_subdirectory: _predictions`.
   - `.8os/projections/_kernel/calibration-policy.yml` gains `target_subdirectory: _calibration-policies`.
   - `.8os/projections/_kernel/calibration-policy-proposal.yml` gains `target_subdirectory: _calibration-proposals`.
   - Body schemas for all vendored projections gain `authored_via` as required base frontmatter field.

3. **Migration script** (`scripts/migrate-v1.0-to-v1.0.1-partial.py`):
   - Idempotent.
   - Relocates records to projection-declared subdirectories.
   - Backfills `authored_via: outside` (or `kernel.self` for internal-origin records).
   - Tested.

4. **Spec text amendments** to `docs/spec/8OS-BLOCK-1-SPEC-v1.0.md` per the three resolutions above. Either inline edits to v1.0.0 producing a v1.0.1 spec file, or this file (`8OS-BLOCK-1-SPEC-v1.0.1-PARTIAL.md`) ships alongside v1.0.0 and is referenced from it. Pick whichever produces cleaner commit history.

5. **Tests**:
   - All 97 existing tests pass after migration.
   - New tests cover: subdirectory placement on author, conflict rejection on conflicting projection targets, `authored_via` required on author, `authored_via` rejection on missing/empty value, SDK default behavior, internal-op explicit `kernel.self`, reindex --check enforcement, migration idempotency.

6. **OPEN-Q registry updates**:
   - `OPEN-Q-021` → RESOLVED (path discipline, Path β + Option 2)
   - `OPEN-Q-022` → RESOLVED (mandatory `authored_via`, `outside` SDK default)
   - `OPEN-Q-023` → RESOLVED (per-version body seal)
   - `OPEN-Q-019`, `OPEN-Q-024`, `OPEN-Q-025` → remain open, with notes referencing this amendment as the round in which they were explicitly deferred.

7. **Block report** (`docs/v1.0.1-partial-report.md` or similar): summarizes what landed, any new open questions surfaced (OPEN-Q-026+), test count, and any implementation surprises in the same shape as Block 2.7/2.8/2.9 reports.

8. **CLAUDE.md and README.md** updated to reference v1.0.1-partial as current.

---

## Discipline

- v1.0.1-partial is the spec. If something is unclear in this document, re-read v1.0.0 alongside it. If after re-reading it remains unclear, log the gap as OPEN-Q-026+ with a best-guess implementation marked as a guess.
- Do not extend the SDK with new operations. The three amendments here are parameter additions, schema additions, and writer-behavior changes. No new ops.
- Do not implement Block 3 work. Factory dispatch, LLM predictors, parallel resolver invocation — all explicitly out of scope. The deferred OPEN-Qs (024, 025) stay deferred.
- Migration runs once on existing data. After migration succeeds and tests pass, the v1.0.0 layout is gone. v1.0.0 backward compatibility within the live repo is not a goal.
- Keep ruff clean. Keep schemas validated. Keep `kernel.reindex --check` deterministic.

---

*End of v1.0.1-partial amendment. Authored 2026-04-27 in Chat 4 spec round. Feeds the v1.0.1-partial Mr Code implementation session, which precedes Block 3.*
