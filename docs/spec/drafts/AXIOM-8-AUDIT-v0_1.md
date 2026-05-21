---
id: AXIOM-8-AUDIT-v0_1
version: 0.1.0
status: audit-findings
kind: audit-report
scope: project
domain: 8os/foundations
authored_by: Dave Eichler + Claude
authored_on: 2026-04-30
supersedes: null
superseded_by: null
depends_on: AXIOM-8-AMENDMENT-PROPOSAL-v0_1; 8OS-BLOCK-1-SPEC-v1_1
revisit_when: code-side confirmation is performed against the eightos repo, or when v1.2 amendment cycle opens
provenance: produced in 8OS - Chat 13 immediately after the axiom 8 amendment proposal, executing the consequent-corrections survey at the spec level against 8OS-BLOCK-1-SPEC-v1_1 to determine whether axiom 8 lands additively (v1.2) or surfaces breaking changes (v2.0)
---

# Axiom 8 — Consequent-Corrections Audit (Spec-Level)

## Scope of this audit

The axiom 8 amendment proposal listed five places where v1.0/v1.1 might currently treat kernel state as privileged (i.e., not (I, R)-formed). This audit examines each at the spec level, against `8OS-BLOCK-1-SPEC-v1_1`, to determine the v1.2-vs-v2.0 disposition.

**This is a spec-level audit only.** Code-side confirmation against the `eightos` repo is required before ratification. Each finding flags whether the code-side check is likely to confirm the spec-side reading or surface unexpected divergence.

## Headline finding

**Axiom 8 lands additively in v1.2.** Four of the five audit targets are spec-side compliant by construction. One target (γ index-regeneration) requires a minor tightening of `kernel.reindex` rebuild-mode behavior that is itself additive (mandate an existing optional emission). No breaking changes are surfaced. The amendment can ratify in v1.2 alongside this single tightening.

## Findings by audit target

### Target 1 — The calibrator's capability-update path

**Spec reference:** v1.1 §3 (calibrator), v1.0 §3.5–§3.6, §5.2; `_kernel.capability-update` projection (v0.2 origin).

**Spec text examined:**
- v1.1 line 1046: capability-update reads `resolver_cost` only.
- v1.1 line 1087: `_kernel.capability-update` listed as v1.1 projection type.
- v1.0 lines 159, 175, 201, 262, 264, 357, 359: capability-update is consistently authored as an (I, R) projection through the calibrator.

**Finding:** Clean. Capability updates are (I, R)-formed by construction since v0.2. v1.0 extended the projection additively to cost-vector updates. The calibrator authors `_kernel.capability-update` records; it does not write capability state through a privileged path.

**Code-side confirmation needed:** That `kernel.calibrator` actually invokes `kernel.ir.new` (or equivalent in-process call path) to author capability-update records, rather than writing them via a direct filesystem operation that bypasses validation. Likely fine — the spec discipline is too explicit to be silently violated — but the audit cannot certify what it cannot read.

**Disposition:** No correction required at v1.2. Code-side verification recommended at ratification time.

---

### Target 2 — Bootstrap vendoring of kernel-internal resolvers

**Spec reference:** v1.1 §3.1 (`kernel.init`), §4.6 (kernel sovereignty), §4.5 (vendored bodies).

**Spec text examined:**
- v1.1 line 263: `kernel.init` "Vendors kernel-internal (I, R)s on first init, refreshes vendored bodies on version transitions."
- v1.1 line 283: `kernel.init` "authors records into the `_kernel` scope on the kernel's own behalf. Internal-origin records carry `authored_via: kernel.self` per the v1.0.1-partial discipline."
- v1.1 line 285: `kernel.init` "writes vendored kernel-internal (I, R)s under `ir/_kernel/`."
- v1.1 line 935: "Internal kernel operations — `kernel.init`, `kernel.reindex`, migration scripts, kernel-authored cancellation cascade events — explicitly pass `authored_via: kernel.self`."

**Finding:** Clean. Vendored kernel-internal records are (I, R)-formed at bootstrap with explicit `authored_via: kernel.self` provenance. The v1.0.1-partial Amendment 2 (mandatory `authored_via`) made this requirement universal. The spec discipline is stronger than the audit anticipated.

**Code-side confirmation needed:** That `kernel.init` actually goes through `kernel.ir.new` semantics (validation, schema check, index update) for vendored records, rather than a direct filesystem write that produces (I, R)-shaped files but bypasses the standard write path. The risk is *not* that vendored records lack provenance fields (the spec mandates them); the risk is that the bootstrap path skips validation or index-update steps that are part of the (I, R) discipline.

**Disposition:** No spec correction required at v1.2. Code-side verification should be a named acceptance criterion at ratification.

---

### Target 3 — The surrogate-readiness signal

**Spec reference:** v1.1 §3 (op roster), §10 (bridges-as-PRISM-IR transition).

**Spec text examined:**
- v1.1 line 259: "The `kernel.surrogate.train` interface stub from v0.1 is **removed** in v1.1. Surrogate training is userspace; v1.1 does not commit the kernel to hosting a training pipeline."
- v1.1 line 1081: `_kernel.surrogate-lineage` projection retained for substitution lineage.
- v1.1 line 1460: surrogateability discussion treats surrogates as PRISM-IR programs subject to standard substitution machinery.

**Finding:** Clean by deferral. The kernel does not perform surrogate-readiness assessment in v1.1 — surrogate training is userspace. The kernel hosts `_kernel.surrogate-lineage` records (which are (I, R)-formed by construction) for substitution but makes no readiness *claim* of its own. Axiom 8 does not bite here because the kernel is not the asserting party.

**Code-side confirmation needed:** None for axiom 8 purposes. The deferral is principled.

**Disposition:** No correction required. The concern dissolves under v1.1's deferral posture.

**Forward note:** When OPEN-Q-002 (surrogate training stack interface) eventually resolves and a training pipeline lands, axiom 8 will require the readiness assertion to be (I, R)-formed at that time. This is a future-block concern, not a v1.2 concern. The amendment proposal should note this as `OPEN-Q-N3` per its existing list.

---

### Target 4 — γ index-regeneration discipline

**Spec reference:** v1.1 §3.17 (`kernel.reindex`).

**Spec text examined:**
- v1.1 line 808: `kernel.reindex` regenerates indexes from records on disk.
- v1.1 lines 821–824: output schema includes `tier3_event_id` as a **nullable** field.
- v1.1 line 935: `kernel.reindex` is named as an internal kernel operation passing `authored_via: kernel.self`.

**Finding:** **Partial compliance.** This is the audit's only real hit.

The spec confirms that when `kernel.reindex` does emit a tier-3 event, it does so with proper provenance. But the output schema makes the tier-3 emission *optional* (`null` is a valid value). Under axiom 8, an index rebuild is a kernel claim ("the indexes are now consistent with the underlying records"). Optional emission means some rebuilds produce no (I, R) record of the kernel's claim.

The spec's design rationale here is plausibly cache-economy: trivial reindex passes that find no drift may not warrant an event. But axiom 8's discipline is that *the act of asserting consistency* is the kernel claim, not the discovery of divergence. Even a no-drift rebuild is an assertion about kernel state.

**Recommended correction at v1.2:**

> Tighten `kernel.reindex` rebuild mode (mode = "rebuild") to require a tier-3 event recording the regeneration with `authored_via: kernel.self`. The event records the indexes rebuilt, the records examined, and the validation outcome. Check mode (mode = "check") remains read-only — no claim made, nothing to record.

The change is additive at the spec level: no existing record format changes; one optional field becomes required for one mode. The change is plausibly additive at the code level too: the binary either emits the event or it doesn't, and tightening to "always emit" doesn't break existing records.

**Code-side confirmation needed:** That the current binary emits the tier-3 event consistently (in which case the spec-tightening is documenting existing behavior) or inconsistently (in which case a small implementation change is needed).

**Disposition:** Spec amendment required at v1.2 ratification. The amendment is additive. If code-side check shows the binary already emits unconditionally, the change is documentation-only.

---

### Target 5 — Policy-evaluation records

**Spec reference:** v1.1 §7.4 (`_kernel.policy-evaluation` projection), §8 (policy machinery).

**Spec text examined:**
- v1.1 line 1175: "The kernel writes one policy-evaluation record per op-signature it evaluates."
- v1.1 line 1321: "The accumulated decision is recorded as a `_kernel.policy-evaluation` (I, R), keyed by a hash of the op name and input parameters."
- v1.1 line 1192: on-disk location specified for evaluation records.

**Finding:** Clean. Policy evaluations are explicitly (I, R)-formed via the `_kernel.policy-evaluation` projection. Cache invalidation is via TTL (axiom 4 compliance) and supersession events. The discipline is correct by construction.

**Code-side confirmation needed:** That cache writes go through standard (I, R) write semantics (validation, indexing, provenance) rather than a sidecar fast path. The policy-evaluation cache is performance-sensitive and a fast path would be a tempting optimization that bypasses (I, R) discipline.

**Disposition:** No correction required at v1.2. Code-side verification should be a named acceptance criterion at ratification.

---

## Summary table

| # | Target | Finding | Spec correction | Code-check |
|---|--------|---------|-----------------|------------|
| 1 | Capability-update path | Clean | None | Recommended |
| 2 | Bootstrap vendoring | Clean | None | Recommended |
| 3 | Surrogate-readiness | Clean by deferral | None | Not needed for v1.2 |
| 4 | γ index-regeneration | **Partial** | Tighten rebuild mode to require tier-3 event | Recommended |
| 5 | Policy-evaluation records | Clean | None | Recommended |

## Why this is good news

The audit anticipated more findings than it surfaced. Four of five targets pass spec-level inspection because the project's existing discipline — particularly the v0.2 establishment of `_kernel.capability-update`, the v1.0.1-partial Amendment 2 mandating `authored_via`, and the v1.1 §10 bridges-as-PRISM-IR commitment — has been *implicitly honoring axiom 8 all along*. The chat-13 derivation made the principle explicit, but the practice was already in place. This is the strongest possible position for ratification: the amendment formalizes existing discipline rather than imposing new constraints.

The single hit on target 4 is real but minor. Tightening `kernel.reindex` to mandate the tier-3 event is the kind of correction that gets accepted in a v1.2 cycle without controversy.

## Recommended ratification path

**v1.2 amendment package:**

1. Axiom 8 ratified per `AXIOM-8-AMENDMENT-PROPOSAL-v0_1`.
2. Plain-language register added to `8OS-AXIOMS-PLAIN-LANGUAGE`.
3. `kernel.reindex` §3.17 tightened: rebuild mode mandates tier-3 event emission with `authored_via: kernel.self`. Output schema updated: `tier3_event_id` becomes required (non-null) in rebuild mode, remains null in check mode.
4. Acceptance criteria include code-side verification of targets 1, 2, 5: that the relevant kernel operations go through standard (I, R) write semantics, not bypass paths.
5. Open questions registered: `OPEN-Q-N1` (bootstrap path verification), `OPEN-Q-N2` (γ event emission verification), `OPEN-Q-N3` (future surrogate-training axiom-8 compliance).

**Not in v1.2:**

- The `kernel.escalate` primitive — separate proposal, separate ratification block, depends on v1.2 axiom 8 landing first.
- OPEN-Q-004 (substrate topology) — held provisionally; not on the v1.2 path.
- Substrate-contract gap reconciliation — separate work, can run in parallel or follow.

## Open questions introduced by this audit

- **OPEN-Q-A1.** Does `kernel.calibrator` author capability-update records via standard `kernel.ir.new` semantics, or via a direct write path? Code-side check.
- **OPEN-Q-A2.** Does `kernel.init` author vendored records via standard validation/index-update path, or via direct filesystem write? Code-side check.
- **OPEN-Q-A3.** Does `kernel.reindex` rebuild mode currently emit the tier-3 event unconditionally, conditionally on drift, or never? Code-side check.
- **OPEN-Q-A4.** Does the policy-evaluation cache write through standard (I, R) semantics, or is there a sidecar fast path? Code-side check.

These should be assigned `OPEN-Q-` numbers from the project's open-questions register at ratification time, alongside the `OPEN-Q-N1/N2/N3` from the amendment proposal.

## Cross-reference

- `AXIOM-8-AMENDMENT-PROPOSAL-v0_1.md` — the proposal this audit supports.
- `KERNEL-ESCALATE-PRIMITIVE-PROPOSAL-v0_1.md` — depends on v1.2 axiom 8 ratification.
- `8OS-BLOCK-1-SPEC-v1_1.md` — the spec text examined.
- `CHAT-13-CONVERSATION-LINEAGE.md` — the derivation that produced the amendment.

---

*End of consequent-corrections audit.*
