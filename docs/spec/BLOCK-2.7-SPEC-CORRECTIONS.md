# Block 2.7 — Spec Corrections and Question Resolutions

**Status**: Authoritative. Consumed by Mr Code alongside `8OS-BLOCK-1-SPEC-v0.2.md` and `BLOCK-2.7-PROMPT.md`. Resolves seven implementation questions raised before Mr Code began coding. Patches three errata in the v0.2 spec text. Mr Code proceeds against the spec as patched here.

**Provenance**: Authored by Q88N + Claude in dialogue, in response to Mr Code's question batch dated mid-Block-2.7.

**Scope**: This file does not introduce new design decisions. Every resolution either (a) clarifies an ambiguity in the v0.2 spec, (b) corrects an erratum in the v0.2 spec text, or (c) confirms that Mr Code's proposed default for an undecided point is correct.

---

## Part 1 — Three direct patches to the v0.2 spec text

These are corrections, not amendments. Mr Code applies them to his working copy of `8OS-BLOCK-1-SPEC-v0.2.md` (or treats them as authoritative overrides without modifying the file — both work). A v0.2.1 housekeeping commit can fold them back into the canonical spec after implementation confirms.

### Patch 1 — §1.1 stale folder tree line

The §1.1 folder tree shows `ir/_kernel/_scope.yml` as a real file. Remove that line. Scopes are declared as (I, R)s under `ir/_kernel/scope/<scope-id>.md` per §1.4 prose. The folder tree should reflect this — no `_scope.yml` file under `ir/_kernel/`.

### Patch 2 — §7.1 step 8 author identity

Spec text reads `resolver: kernel.migration`. Replace with: `authored through kernel.self`. The string `kernel.migration` was a placeholder name from before the cogito bridge work. After §2.4 and §3.4 named `kernel.self` as the canonical kernel-self-observation provenance, migration events absorb into that mechanism. There is no `kernel.migration` resolver.

### Patch 3 — §3 add operation-output projection types

The v0.1 implementation vendored four kernel projection types as operation outputs: `tier3-event`, `authorization`, `resolver-selection`, `capability-update`. v0.2 §3 is silent on these because the drafting pass focused on configuration-object projection types and missed the operation-output ones. This is a real omission. The v0.2 kernel needs nine kernel projection types total: the five configuration types specified in §3.1–3.5, plus four operation-output types specified here.

The four operation-output projection types live under the same `_kernel.*` naming convention for consistency. The v0.1 unprefixed names (`authorization`, `resolver-selection`, `capability-update`, `tier3-event`) are renamed to `_kernel.authorization`, `_kernel.resolver-selection`, `_kernel.capability-update`, `_kernel.tier3-event` in v0.2. The migration script renames existing records and rewires affected operations.

Add the following as §3.6 of the v0.2 spec:

---

### §3.6 Operation-output projection types

In addition to the five configuration projection types (§3.1–3.5), the kernel ships with four projection types that describe records produced as operation side effects. These are vendored at bootstrap through `kernel.self` like the configuration types, but they describe ephemeral operational artifacts rather than configuration state.

#### §3.6.1 `_kernel.tier3-event`

**Purpose**: typed projection over tier 3 events written to `.8os/events/YYYY/MM/DD/*.jsonl`.

**Projection-declared frontmatter**: none beyond base 8OS frontmatter (these records carry their content in the body or in the JSONL stream itself; the projection exists primarily so that tier 3 events appear in the projection-to-ids index and are discoverable through `ir.list --projection _kernel.tier3-event`).

**Body shape**: free-form, typically empty for events stored canonically in the JSONL stream. (I, R) records of this type are pointers to the canonical event location.

**Authority**: `convention` for events authored by user-scope resolvers; `hard` for events authored by `kernel.self` (migrations, reindex completions, init).

**On-disk location**: `ir/<scope>/_events/<event-id>.md` for the (I, R) pointer; canonical event payload remains in `.8os/events/YYYY/MM/DD/*.jsonl`.

**Bootstrap**: vendored at init.

#### §3.6.2 `_kernel.authorization`

**Purpose**: record an authorization decision per axiom 6, produced by the gatekeeper when a bridge crossing requires authorization.

**Projection-declared frontmatter**:
- `bridge_id`: the bridge being crossed.
- `subject_resolution`: the (I, R) the authorization permits.
- `authorized_by`: the human or hard-authority resolver granting authorization.
- `authorization_scope`: `single | session | persistent`.
- `granted_on`: timestamp.
- `expires_on`: optional timestamp; null for persistent authorizations.

**Body shape**: free-form rationale for the authorization, optional.

**Authority**: matches `authorized_by` authority; typically `hard`.

**On-disk location**: `ir/<scope>/_authorizations/<authorization-id>.md`.

**Bootstrap**: vendored at init.

#### §3.6.3 `_kernel.resolver-selection`

**Purpose**: record a selector decision when `kernel.selector.select` is invoked.

**Projection-declared frontmatter**:
- `subject_intention`: the (I, R) being resolved.
- `selected_resolver`: the resolver chosen.
- `candidate_resolvers`: array of resolvers considered.
- `selection_rationale`: brief structured rationale (cost weight, capability weight, authority weight, tiebreaker if any).
- `selected_on`: timestamp.

**Body shape**: free-form additional context, optional.

**Authority**: `convention` (selector decisions are conventional unless overridden).

**On-disk location**: `ir/<scope>/_selections/<selection-id>.md`.

**Bootstrap**: vendored at init.

#### §3.6.4 `_kernel.capability-update`

**Purpose**: record a calibration-driven update to a resolver's capability vector, produced by `kernel.calibrator`.

**Projection-declared frontmatter**:
- `resolver_id`: the resolver whose capabilities are being updated.
- `previous_capabilities`: capability vector before update.
- `updated_capabilities`: capability vector after update.
- `corpus_summary`: summary of the calibration corpus that drove the update (`{event_count, period_start, period_end}`).
- `updated_on`: timestamp.

**Body shape**: free-form rationale, optional.

**Authority**: `convention` (calibration updates are conventional; humans may supersede them with hard authority if calibration is judged wrong).

**On-disk location**: `ir/<scope>/_calibrations/<update-id>.md`.

**Bootstrap**: vendored at init.

---

End of §3.6 patch.

### Patch 4 — Bridge `bridge_status` field on `_kernel.bridge`

The v0.2 spec §3.4 specifies the `_kernel.bridge` projection's required frontmatter (`bridge_id`, `display_name`, `bridge_type`, `requires_authorization`, `scope_of_authority`, `cost_envelope`) and one optional field (`endpoint`), but is silent on a bridge-availability field. The v0.1 implementation honored a `status: quarantined` value (see `kernel.bridge.cross` quarantine semantics) on the bare word `status`, but `status` is a base 8OS frontmatter field (the (I, R) lifecycle status: `open`/`resolved`/etc.) — the v0.1 name was sloppy and v0.2's no-collision rule (§2.1) rejects it.

This is the same class of error as Patch 5's `bridge_type` collision. The fix follows the same discipline: namespace the field to disambiguate.

Add `bridge_status` to `_kernel.bridge`'s optional frontmatter:

- **Field**: `bridge_status`
- **Type**: enum
- **Values**: `active | quarantined | deprecated | removed`
- **Default**: `active` when absent.
- **Semantics**: `kernel.bridge.cross` rejects crossings into a bridge with `bridge_status: quarantined` with `BRIDGE_UNREACHABLE`. `deprecated` and `removed` are reserved for future enforcement (warnings on use, hard rejection, respectively); v0.2 records them but does not act on them differently from `active` outside of the `quarantined` check.

The name `bridge_status` is parallel to the existing `bridge_id`/`bridge_type` namespacing on `_kernel.bridge`'s extensions.

Apply by:
- Adding the field to `_kernel.bridge`'s `optional_frontmatter` declaration in `init_op.py` (the source-of-truth dict that vendors `.8os/projections/_kernel/bridge.yml` at init time).
- Updating `bridge_ops.py::cross` to read `bridge_fm.get("bridge_status")` instead of `bridge_fm.get("status")`.
- Adding the field to spec §3.4's `_kernel.bridge` definition under "Optional frontmatter extensions".
- Regenerating `.8os/projections/_kernel/bridge.yml` so the vendored body schema reflects the declaration.
- Migration: any v0.1 bridge yaml carrying `status: <value>` has the field rewritten to `bridge_status: <value>` when migrated into the v0.2 (I, R) form.

---

End of §3.6 / Patch 4.

### Patch 5 — Rename base frontmatter field `bridge_type` → `authored_via`

The v0.1 spec (§2 base frontmatter) declared a field called `bridge_type` that records the bridge through which an (I, R) was authored — but the field stores a **bridge ID**, not a bridge type. The name is misleading. Worse, v0.2's `_kernel.bridge` projection (§3.4) declares its own `bridge_type` field for the bridge's category enum (`api | human | ...`). Two fields with the same name, different meanings — §2.1's no-collision rule rejects the projection definition outright, and the spec is unimplementable as written.

This is a v0.1 drafting accident inherited by v0.2. The implementation field stores an ID under a name that means something else; v0.2's projection field correctly uses the name for what it semantically is.

When spec and implementation disagree, spec wins and implementation aligns. The implementation field gets renamed to `authored_via` — clean alongside `authored_by` and `authored_on`, completing a three-field provenance story (who, when, through what bridge).

Apply by:
- Renaming `bridge_type` to `authored_via` in `_projections.py`'s `BASE_FRONTMATTER_FIELDS`.
- Updating every callsite that reads or writes the base field (the projection-declared `bridge_type` on `_kernel.bridge` records is preserved as the correct v0.2 spelling). Approximately nine locations across `ir_ops.py`, `authorize_op.py`, `init_op.py`, and `selector_op.py`.
- Updating spec §2 base frontmatter section to document `authored_via` and remove the old `bridge_type` line. The v0.1 archive at `docs/spec/8OS-BLOCK-1-SPEC-v0.1.md` is left as-is (historical record).
- Migration: any v0.1 (I, R) on disk carrying `bridge_type: <bridge-id>` in its frontmatter has the field rewritten to `authored_via: <bridge-id>`. Idempotent — running twice is a no-op (second run finds no `bridge_type` to rename).

After this patch, `bridge_type` exists in the codebase only as the projection-declared extension on `_kernel.bridge` records. Base frontmatter has no field by that name.

---

End of §3.6 / Patch 4 / Patch 5.

---

## Naming discipline — projection-declared frontmatter (project-wide)

Block 2.7 surfaced three base-frontmatter / projection-extension name collisions in close succession (`bridge_type` → Patch 5, `status` → Patch 4 became `bridge_status`, and the implicit lesson from both). The pattern is clear: v0.1 base frontmatter took generic field names (`status`, `bridge_type`, etc.) on the assumption that nothing else would compete for them. v0.2's projection-declared extension surface (§2.1) makes that assumption false — extensions live at the same flat top level as base fields and §2.1's no-collision rule rejects any overlap.

**Discipline (effective Block 2.7+):** Projection-declared frontmatter fields use **namespaced names** by default (e.g., `bridge_status`, `resolver_id`, `projection_id`, `surrogate_id`, `cost_envelope`) — typically prefixed with the projection's domain word — unless there is a documented reason to claim a generic name. Generic names are reserved for base 8OS frontmatter; extensions earn their slot by being explicit about which domain they belong to.

**Why this matters before v1.0:** prediction-economics in v1.0 will introduce several new frontmatter fields (predictor, probability, escalation_cost, calibration_baseline, etc.). Knowing the namespacing discipline up front prevents a third round of collision-finding when those projection types land. The discipline is cheap to follow and expensive to retrofit.

**Existing v0.2 extensions that already follow this discipline:**
- `bridge_id`, `bridge_type`, `bridge_status`, `cost_envelope`, `scope_of_authority` (on `_kernel.bridge`)
- `resolver_id`, `cost`, `capability` (on `_kernel.resolver` — `cost`/`capability` are arguable; both could have been `resolver_cost`/`resolver_capability` for full consistency, but they are descriptive enough in context)
- `projection_id`, `filename_suffix`, `body_shape`, `required_frontmatter`, `optional_frontmatter` (on `_kernel.projection`)
- `surrogate_id`, `surrogate_of`, `training_corpus`, `validation`, `trained_on`, `trained_by` (on `_kernel.surrogate-lineage`)
- `parent_scope`, `authority_defaults`, `visibility_defaults` (on `_kernel.scope`)

The discipline documented here is descriptive of the existing v0.2 design (with the Patch 4/5 corrections folded in), and prescriptive for v1.0 and beyond.

---

## Housekeeping items (deferred to v0.2.1 fold-back)

These are non-blocking polish items surfaced during Block 2.7 implementation. They get folded into the canonical spec when v0.2.1 lands. No OPEN-Q file entries — they are doc cleanup, not unresolved questions.

- **§1.4 line on the `_kernel` scope declaration** has awkward grammar after Patch 1's removal of the stale `_scope.yml` folder-tree line. The sentence currently reads: "Declared at kernel ship time. Vendored as `ir/_kernel/_scope.yml` is removed; the scope declaration is itself an (I, R) at `ir/_kernel/scope/_kernel.md` of `projection_types: [_kernel.scope]`." Suggest rewording to: "Declared at kernel ship time as an (I, R) at `ir/_kernel/scope/_kernel.md` of `projection_types: [_kernel.scope]` (the v0.1.0 `ir/_kernel/_scope.yml` convention is removed). Bootstrap creates this (I, R) before any other." Says the same thing, parses cleanly.

- **PRISM-IR-SPEC-v1.1 example frontmatter** — the example at `docs/spec/PRISM-IR-SPEC-v1.1.md:143` carries `bridge_type: null` in (I, R) frontmatter. After Patch 5, the base frontmatter spelling is `authored_via: null`. PRISM-IR examples track 8OS base frontmatter; they need a v1.1.1 housekeeping update to match. (Mechanically a one-line rename in the example.)

---

## Part 2 — Question-by-question resolutions (numbered to match Mr Code's batch)

### Question 1 — kernel.self cogito bridge: spec or future block?

**Resolution**: spec. The cogito bridge IS intended for v0.2. It is not leaked from a future block.

**Mr Code's framing of the apparent absence is correct, with one likely cause**: the v0.2 spec was amended in conversation *after* its first draft to add §2.4 and revise §3.1, §3.4, and §4.1 with the cogito mechanics. If Mr Code is reading a stale local version of the spec that predates these amendments, that explains why `kernel.self`, `cogito`, and `bootstrap bridge` appear nowhere.

**Action**: before proceeding, verify the spec file at `docs/spec/8OS-BLOCK-1-SPEC-v0.2.md` contains §2.4 with title "Authority foundations — the kernel's *cogito* and the human's sovereignty". If yes: read and proceed. If no: re-vendor from `/mnt/user-data/outputs/8OS-BLOCK-1-SPEC-v0.2.md` (the canonical version with all amendments applied).

**Default Mr Code proposed** (write the §2.4 amendment from the prompt, revise §3.4): would be correct in the absence of the canonical version. With the canonical version available, just re-vendor instead — avoids re-deriving content that already exists.

### Question 2 — migration-event author conflict (kernel.migration vs kernel.self)

**Resolution**: `kernel.self`. Mr Code's default is correct.

**Reasoning**: there is no `kernel.migration` resolver. The string was a placeholder name that didn't get cleaned up when the cogito bridge work named `kernel.self` as the canonical self-observation provenance. Migration events are kernel observing what it just did to its own representation — exactly what `kernel.self` is for.

**Action**: implement migration event authoring through `kernel.self`. Patch 2 in Part 1 above corrects the spec text.

### Question 3 — resolver count (three or four)

**Resolution**: three. The spec is correct (`kernel.selector`, `kernel.gatekeeper`, `kernel.calibrator`). The "four" in the Block 2.7 prompt is leftover from earlier conversation drafts where I was holding `kernel.voi` open as a fourth, before the v0.2/prediction-economics split deferred `kernel.voi` to a later block.

**Action**: implement three kernel-internal resolvers. Mr Code's default is correct.

### Question 4 — disposition of v0.1's vendored kernel projection types

**Resolution**: keep all four, but rename them with the `_kernel.` prefix for consistency and add their specifications to §3 as a new §3.6 (Patch 3 in Part 1 above).

**Reasoning**: the v0.1 four projection types (`tier3-event`, `authorization`, `resolver-selection`, `capability-update`) are operation-output projections — they describe records produced as side effects of operations. They are categorically different from the v0.2 five (`_kernel.scope`, `_kernel.projection`, `_kernel.resolver`, `_kernel.bridge`, `_kernel.surrogate-lineage`), which describe configuration objects. v0.2 §3 missed them in drafting. The fix is additive: keep them, prefix them, specify them.

**The naming asymmetry Mr Code flagged** (mixing `_kernel.scope` with un-prefixed `authorization`) is genuinely ugly and worth eliminating in v0.2. The op-rewiring cost is minimal — three string changes in the affected operations (`kernel.authorize`, `kernel.selector.select`, `kernel.calibrator`).

**Action**:
- Rename v0.1's four types to `_kernel.tier3-event`, `_kernel.authorization`, `_kernel.resolver-selection`, `_kernel.capability-update`.
- Add the specifications from Patch 3 above as §3.6 of the v0.2 spec.
- Migration script renames existing records' projection_type field.
- Rewire the affected operations to use the new names.
- Mr Code's default of "keep them under existing names with naming asymmetry" is overridden in favor of the cleaner rename.

**Log this as OPEN-Q-013-RESOLVED** in `docs/open-questions.md` with reference to this corrections file.

### Question 5 — §1.1 vs §1.4 self-conflict

**Resolution**: follow the prose. §1.1 has a stale folder tree line. Mr Code's default is correct.

**Action**: Patch 1 in Part 1 above corrects the spec text. No code-level concern.

### Question 6 — bootstrap order paradox

**Resolution**: drop the "vendored authority bypass" framing. With `kernel.self` specified in §2.4 and §3.4, authority is grounded in the cogito bridge, not in a bypass. The validation question (separate from the authority question) resolves through the vendored body schemas.

**The validation answer**: the kernel's vendored body schemas at `.8os/projections/_kernel/<type>.yml` are the validation source for bootstrap records. The kernel reads them directly during init, before the projection-to-ids index exists. After bootstrap (I, R)s are written, the projection-to-ids index gets built and points at the projection-definition (I, R)s, which themselves carry frontmatter referencing the vendored body schemas. The vendored schemas remain the authoritative validation source even after the (I, R)s exist; the (I, R)s are the queryable record but not the validation source.

**This is a clean separation**: vendored schemas validate; (I, R)s record. The kernel never validates against itself recursively because validation always traces to sealed vendored bodies.

**Action**: implement bootstrap-record creation by reading the vendored body schemas at `.8os/projections/_kernel/<type>.yml` for validation. After all bootstrap records are written, rebuild indexes including projection-to-ids. The projection-definition (I, R)s reference the vendored schemas; they do not replace them as validation sources.

**Log this as OPEN-Q-014-RESOLVED** in `docs/open-questions.md` with reference to this corrections file.

### Question 7 — authority enforcement on the user scope at init

**Resolution**: Mr Code's default is correct. All scope-declaration (I, R)s require hard authority regardless of which scope they declare, because declaring a scope is a foundational decision about the project's authority structure.

**Reasoning**: even a user scope declaration sets defaults and visibility for everything authored under it. The human running init *has* hard authority over their own project per #NOKINGS sovereignty. Init authoring the user scope at hard authority on the operator's behalf is exactly what user sovereignty looks like operationally. No conflict.

**Action**: implement scope-declaration writes with `authority_level: hard` requirement enforced uniformly. Init authors the user scope through the user's identity bridge (`human-<primary-operator-id>`) at hard authority. The `_kernel` scope is authored through `kernel.self` at hard authority. Both grounded, both honored.

**Log this as OPEN-Q-015-RESOLVED** in `docs/open-questions.md` with reference to this corrections file.

---

## Part 3 — Summary of action items for Mr Code

In execution order:

1. **Verify spec freshness**: confirm `docs/spec/8OS-BLOCK-1-SPEC-v0.2.md` contains §2.4 and the cogito bridge content. Re-vendor if not.

2. **Apply three patches** (or treat them as authoritative overrides without modifying the file):
   - Patch 1: remove stale `_scope.yml` line from §1.1 folder tree.
   - Patch 2: change `kernel.migration` to `kernel.self` in §7.1 step 8.
   - Patch 3: add §3.6 specifying four operation-output projection types.

3. **Implement Block 2.7 against the patched v0.2 spec**, with these specific resolutions in hand:
   - Cogito bridge per §2.4 and §3.4 (now confirmed in-spec).
   - Migration events authored through `kernel.self`.
   - Three kernel-internal resolvers (`selector`, `gatekeeper`, `calibrator`).
   - Nine kernel projection types total (five configuration + four operation-output, all `_kernel.*` prefixed).
   - Bootstrap validation through vendored body schemas, not recursive self-validation.
   - Scope-declaration writes uniformly require hard authority.

4. **Migration script** renames v0.1's four projection types to their `_kernel.*` prefixed equivalents and rewires the three affected operations.

5. **Log resolutions** in `docs/open-questions.md`:
   - OPEN-Q-013-RESOLVED: operation-output projection types renamed and specified (Question 4).
   - OPEN-Q-014-RESOLVED: bootstrap validation through vendored schemas (Question 6).
   - OPEN-Q-015-RESOLVED: scope-declaration uniformly hard authority (Question 7).

6. **Block 2.7 acceptance criterion unchanged**: all surviving v0.1 tests pass; new v0.2 tests pass; ruff clean; `kernel.reindex --check` deterministic; PRISM-IR example accessible at id `expense-approval` (without suffix) after migration.

---

## Part 4 — One closing note on process

This question batch surfaced a real spec-drafting gap (Question 4 — operation-output projection types missed in v0.2 §3). The omission would have caused implementation breakage if Mr Code had proceeded without flagging it. The catch is exactly the discipline this project values — implementation surfaces gaps that conversation alone misses, and the discipline of asking before defaulting protects against silent breakage.

For future spec rounds: add a "read prior version, diff explicitly" pass before any new spec gets vendored. v0.2 was drafted from v0.1 in a single artifact-creation pass without that diff discipline. Catching it now is cheap; catching it in production would be expensive.
