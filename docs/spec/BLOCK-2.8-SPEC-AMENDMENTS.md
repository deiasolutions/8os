# Block 2.8 — Spec Amendments

**Status**: Authoritative. Consumed by Mr Code alongside `8OS-BLOCK-1-SPEC-v1.0.md` and `BLOCK-2.8-PROMPT.md`. Resolves two real spec gaps surfaced in Block 2.8's pre-implementation question batch. Mr Code proceeded against the v1.0 spec as amended here. Same shape as Block 2.7's corrections file but smaller — only two amendments, both additive.

**Provenance**: Authored by Q88N + Claude in dialogue, in response to Mr Code's question batch dated mid-Block-2.8 (questions Q1 and Q2 from the four-question batch).

**Scope**: This file does not introduce new design decisions. Both amendments fix v1.0 spec drafting gaps the way they were caught — implementation surfaces what conversation alone misses (Block 2.7's lesson, applied again).

**Relationship to v0.2.1 housekeeping**: This file is the v1.0.1 analogue of `BLOCK-2.7-SPEC-CORRECTIONS.md` (the v0.2.1 housekeeping batch). Both amendments fold into `8OS-BLOCK-1-SPEC-v1.0.md` at the eventual v1.0.1 housekeeping pass. The implementation already applies them; the canonical spec text catches up.

---

## Amendment 1 — `_kernel.calibration-policy-proposal` lifecycle field renamed `status` → `proposal_status`

### Spec gap

The v1.0 spec at §3.3 declared the calibration-policy-proposal lifecycle field as:

> `status: pending | approved | rejected | superseded` — lifecycle state.

This collides with base 8OS frontmatter's `status` field — the (I, R) lifecycle status (`open | resolved | superseded | stale`) declared in v0.1 §2 and registered in `BASE_FRONTMATTER_FIELDS` (`src/eightos/_projections.py:47`). Per v0.2 §2.1's no-collision rule, the projection definition is unimplementable as drafted: the kernel's `validate_extensions` rejects projection definitions that declare required fields colliding with base names, and the `_kernel.calibration-policy-proposal` projection-definition (I, R) cannot be vendored.

### Why this happened

Block 2.7 caught this exact class of error twice (Patch 4 `bridge_status`, Patch 5 `authored_via`). The corrections file's "Naming discipline" section called out the pattern explicitly:

> "Why this matters before v1.0: prediction-economics in v1.0 will introduce several new frontmatter fields ... Knowing the namespacing discipline up front prevents a third round of collision-finding when those projection types land. The discipline is cheap to follow and expensive to retrofit."

The discipline was established. The v1.0 spec author did not apply it to this one new field. This is a v1.0 drafting miss — same class as v0.2's drafting misses on `bridge_type` and `bridge_status` from the v0.2 → v0.2.1 housekeeping batch.

### Resolution

Rename the projection-declared field to `proposal_status` — namespaced parallel to `bridge_status` (Patch 4), `bridge_id` / `bridge_type`, `resolver_id`, `projection_id`, `surrogate_id`. Values unchanged: `pending | approved | rejected | superseded`. Semantics unchanged.

The fix is a one-line rename in v1.0 spec §3.3's required_frontmatter declaration, plus updated prose anywhere the field is referenced (§3.3 transition descriptions, §3.4 supersession-chain mechanics, §6.1 calibration-corpus relationship, §7.3 test discipline).

### Implementation

Block 2.8 implementation applies this rename throughout:

- Vendored body schema at `.8os/projections/_kernel/_kernel.calibration-policy-proposal.yml` declares `proposal_status` in `required_frontmatter` (init_op.py).
- Projection-definition (I, R) at `ir/_kernel/projection/_kernel.calibration-policy-proposal.md` body documents the rename and links to this amendments file.
- The proposal auto-dispatch path (`_dispatch_proposal_approval` in `ir_ops.py`) writes `proposal_status` on both pending and approved proposal records.
- Tests in `tests/test_v1_prediction_economics.py` use `proposal_status` exclusively and explicitly assert that `status` is NOT in the projection's required_frontmatter (parallel to the discipline check).

### v1.0.1 fold-back action

Apply this rename to v1.0 spec §3.3's required_frontmatter declaration. The implementation is already aligned; the canonical spec text catches up at v1.0.1 housekeeping.

### Log entry

Logged as **OPEN-Q-017-RESOLVED** in `docs/open-questions.md` with reference to this amendments file.

---

## Amendment 2 — `_kernel.authorization` extension for supersede-calibration-policy authorizations

### Spec gap

The v1.0 spec at §3.4 reuses v0.2's existing `_kernel.authorization` projection for standing authorizations against calibration-policy proposals:

> "A standing authorization (using v0.2's existing `_kernel.authorization` projection from §3.6.2) may pre-grant approval for calibration-policy proposals matching defined conditions."

The example body in §3.4 uses fields the v0.2 projection does not declare:

```yaml
authorized_action: supersede-calibration-policy
authorized_subject: [calibration-policy-lending-default]
granted_by: human-q88n
granted_on: 2026-04-27T12:00:00Z
expires_on: null
conditions:
  - field: holdout_rate
    change_within: 0.05
  ...
```

But v0.2 §3.6.2's `_kernel.authorization` declares fields designed for **bridge-crossing** authorizations only — `bridge_id`, `subject_resolution`, `authorized_by`, `authorization_scope`, `granted_on`, `expires_on`. The actual implementation's vendored body at `.8os/projections/_kernel/_kernel.authorization.yml` carried a single nested `authorizes: {bridge, for_ir, scope_of_authority, cost_ceiling}` block (already a divergence between v0.2 spec text and v0.2 implementation, but functionally bridge-crossing-only).

The v1.0 spec implies the projection is reused but does not specify the field amendments. The Block 2.8 prompt's Piece 3 listed three projection types gaining optional fields:

> "Three v0.2 projection types gain optional fields. The additions are all optional; existing v0.2 records remain valid without them."

`_kernel.authorization` was not in that list. The spec text says "use v0.2's existing projection"; the prompt says nothing about extending it. Implementation must surface the gap.

### Why this happened

The v1.0 spec author wrote §3.4's standing-authorization mechanics referencing the existing projection by name without diff-checking the projection's declared field set against the new use case. This is the same shape of error as v0.2 §3.6 missing the operation-output projection types in v0.2 drafting (Block 2.7 Patch 3) — drafting in conversation can miss what reading the existing schema would catch.

### Resolution (additive option, per Q2 sharpened framing)

Extend `_kernel.authorization` additively. One projection, two shape variants, backward compatible.

**New optional projection-declared fields:**

- `authorized_action: bridge-cross | supersede-calibration-policy` — declares which shape this authorization carries. Required-by-convention, but typed as optional in the projection so existing v0.2 records (which don't declare it) remain valid; absence is treated as `bridge-cross` for v0.2 backward compatibility.
- `authorized_subject: <ir-id> | [<ir-id>, ...]` — required-when `authorized_action: supersede-calibration-policy`; absent for `bridge-cross`.
- `conditions: [...]` — optional list of predicate dicts the standing authorization checks against incoming proposals' `proposed_changes` and `evidence_summary`. Three predicate kinds in v1.0 (extensible):
  - `{field, change_within: <delta>}` — proposed change to <field> stays within <delta> of the current value.
  - `{field, requires_min_observations: <N>}` — evidence's `observation_count` ≥ N.
  - `{field, requires_p_value: <p>}` — evidence's `p_value` ≤ p (lower is more significant).
  - Unknown predicate kinds fail closed (don't grant approval) so authorizations with extension predicates from a future block can't accidentally pre-grant in v1.0.

**Existing v0.2 fields:**

- `authorizes: {bridge, for_ir, scope_of_authority, cost_ceiling}` — preserved as optional (was effectively required in v0.2's vendored body). Present for `bridge-cross` authorizations (the v0.2 shape); absent for `supersede-calibration-policy` (the v1.0 shape).

**Backward compatibility:**

- Existing v0.2 bridge-cross authorization records (carrying `authorizes` block, no `authorized_action` field) remain valid v1.0 records. The kernel applies `authorized_action: bridge-cross` as default when absent.
- The `authorize_op.py` op continues to write the v0.2 shape; new `supersede-calibration-policy` standing authorizations are authored through `kernel.ir.new` with `projection_types: ["_kernel.authorization"]` and `frontmatter_extensions` carrying the new fields.

### Why "Block 2.8's Piece 3 list grows from three projection types to four"

Q2's sharpened framing: extending `_kernel.authorization` is exactly the case the prompt authorizes ("if implementation surfaces a contradiction with any v1.0 spec text, name it explicitly and surface it as a question before drafting around it"). v1.0 §3.4 references functionality that v0.2's `_kernel.authorization` does not declare; the principled response is to extend the projection per option (a) of Q2 rather than work around the gap.

The prompt's Piece 3 enumeration is incomplete in retrospect — Block 2.8's actual Piece 3 list is:

1. `_kernel.resolver` — `cost_model`, `cost_per_depth_unit`, `depth_grid`
2. `_kernel.scope` — `stakes_defaults`
3. Base 8OS frontmatter (intentions) — `stakes`
4. **`_kernel.authorization`** — `authorized_action`, `authorized_subject`, `conditions` (this amendment)

### Implementation

Block 2.8 implementation applies the extension in:

- Vendored body schema at `.8os/projections/_kernel/_kernel.authorization.yml` (init_op.py): `authorizes` becomes optional; `authorized_action`, `authorized_subject`, `conditions` join `optional_frontmatter`.
- Projection-definition (I, R) at `ir/_kernel/projection/_kernel.authorization.md` body documents both shape variants and links to this amendments file.
- `find_matching_authorization` in `src/eightos/calibration.py` evaluates the three predicate kinds; unknown predicates fail closed.
- The proposal auto-dispatch path (`_dispatch_proposal_approval` in `ir_ops.py`) calls `find_matching_authorization` and dispatches the approval supersession + policy supersession when a match is found.
- Tests in `tests/test_v1_prediction_economics.py` exercise both shapes: bridge-cross authorizations via the existing `kernel.authorize` op (v0.2 path, no behavioral change), and `supersede-calibration-policy` authorizations via `kernel.ir.new` (v1.0 path, exercising the auto-dispatch).

### v1.0.1 fold-back action

Apply this extension to v1.0 spec §3.4's projection-extension declarations. The implementation is already aligned; the canonical spec text catches up at v1.0.1 housekeeping. Optional-fields list on `_kernel.authorization` should explicitly include the four fields with their semantics; the §3.4 example body should be paired with a note that the new fields formally extend the projection rather than being illustrative.

### Log entry

Logged as **OPEN-Q-018-RESOLVED** in `docs/open-questions.md` with reference to this amendments file.

---

## Part 2 — Other findings during Block 2.8 implementation (no spec amendment needed)

These were surfaced during implementation but resolve through implementation choice rather than spec amendment. Documented here for audit completeness.

### `proposal_status` lifecycle under append-only (Q3 resolution)

v1.0 §3.3 specifies `proposal_status` transitions (`pending → approved | rejected | superseded`). The kernel is append-only; frontmatter is not rewritten in place. Per Q3 resolution, transitions are recorded as supersession chains: each transition authors a new `_kernel.calibration-policy-proposal` (I, R) with `supersedes: <prior-proposal-id>` and the new `proposal_status`. The "current" status is the latest record in the supersession chain. Composes with v0.2's `kernel.ir.supersede` mechanics; no new operation introduced.

This is implementation discretion — the spec does not lock the lifecycle representation. v1.0.1 may consider adding a sentence to §3.3 explicitly noting "transitions are recorded by supersession chain per v0.2's existing discipline; the latest record in the chain is the current state". Not blocking.

### VOI's expected-value math (Q4 resolution)

v1.0 §4.1 specifies VOI's inputs, output shape, and stakes-unknown behavior, but not the formula for computing the three expected_value numbers. Per Q4 resolution, this is implementation discretion. Block 2.8 implements a documented reference formulation (probability widening by predictor calibration error, reversibility/consequence-scope multipliers, argmax(EV) recommendation) in `src/eightos/voi.py`'s module docstring. Future versions may supersede the resolver definition (I, R) for `kernel.voi` with refined math; the calibrator may also empirically refine `kernel.voi`'s `rho` capability if recommendations diverge from sovereign judgment.

The cost-vector aggregation defaults to `coin_usd` only — flagged in the docstring as a v1.0 default, not a permanent commitment. Future versions may introduce CCC weighting policies.

No spec amendment. The discretion is appropriate: VOI is a vendored kernel-internal resolver; its definition is its implementation; future versions can refine without spec churn.

---

## Part 3 — Summary of action items applied during Block 2.8

In execution order:

1. **Verified v1.0 spec freshness** — confirmed `docs/spec/8OS-BLOCK-1-SPEC-v1.0.md` was the version vendored at the start of Block 2.8 (2026-04-27).

2. **Surfaced the four-question batch** before coding — three real spec gaps (Q1, Q2 above; Q3 lifecycle representation), one implementation discretion (Q4 VOI math). Pattern matches Block 2.7's seven-question batch discipline: surfacing questions before implementation catches errata cheaply that would be expensive to fix after.

3. **Applied two amendments** described above. Documented inline in the Block 2.8 implementation; persisted durably in this file for v1.0.1 fold-back.

4. **Logged resolutions** in `docs/open-questions.md`:
   - OPEN-Q-017-RESOLVED: `proposal_status` rename (Amendment 1).
   - OPEN-Q-018-RESOLVED: `_kernel.authorization` extension (Amendment 2).

5. **Block 2.8 acceptance criteria**: 87/87 tests passing (61 v0.2 surviving + 26 new v1.0); ruff clean; reindex deterministic; twelve regenerable indexes (v0.2's eleven + calibration-corpus); v1.0 spec amendments tracked here; VOI math documented in module docstring.

---

## Part 4 — Process note

Block 2.7's closing process note observed that "implementation surfaces gaps that conversation alone misses". Block 2.8 confirms it applied to v1.0 drafting too. Two real gaps in a v1.0 spec drafted with the v0.2 lessons fresh — both caught by Mr Code's pre-implementation question batch, not by a separate spec review.

The discipline of "ask before defaulting" remains load-bearing across blocks. Block 2.7 gathered seven questions; Block 2.8 gathered four. Both rounds caught errata that would have been expensive to fix post-implementation. The cost of asking is one round-trip per block; the cost of catching after is rework on every callsite the gap touches.

Future spec rounds: continue the pattern. Drafting → vendoring → pre-implementation question batch → amendments captured durably → implementation → report. The amendments file is the durable receipt that makes the catch auditable.

---

*End of Block 2.8 spec amendments. Authored 2026-04-27. Folds into 8OS-BLOCK-1-SPEC-v1.0.md at v1.0.1 housekeeping.*
