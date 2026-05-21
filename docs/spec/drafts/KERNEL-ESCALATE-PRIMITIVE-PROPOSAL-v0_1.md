---
id: KERNEL-ESCALATE-PRIMITIVE-PROPOSAL
version: 0.1.0
status: proposal
kind: kernel-primitive-proposal
scope: project
domain: 8os/sdk
authored_by: Dave Eichler + Claude
authored_on: 2026-04-30
supersedes: null
superseded_by: null
depends_on: 8OS-KERNEL-SPEC-v0.1.0; AXIOM-8-AMENDMENT-PROPOSAL-v0_1; 8OS-BLOCK-1-SPEC-v1_1
revisit_when: a Block 5+ planning cycle opens, or when federation-of-kernels work begins to require concrete arbitration machinery
provenance: derived in 8OS - Chat 13 from the meta-authority gap that axiom 8 alone does not close, with Fibonacci escalation proposed as the recursive sovereign-recruitment protocol that makes federation arbitration first-class kernel machinery rather than treaty convention
---

# `kernel.escalate` — Federation Escalation Primitive (Proposal)

## Status of this proposal

This is a **v0.1.0 proposal**. It seeds a Block 5+ kernel-primitive addition. The proposal depends on the axiom 8 amendment landing first (see `AXIOM-8-AMENDMENT-PROPOSAL-v0_1.md`); without reflexivity, the escalation records cannot be honestly inter-kernel-readable and the primitive degrades to a centralized arbitration mechanism in disguise.

## What this proposal adds

A first-class kernel primitive — `kernel.escalate` — that provides Fibonacci-shaped recursive sovereign-recruitment for cross-kernel conflicts in federated 8OS deployments. Plus one new projection type, two new typed outcomes, and a stakes-bounded termination rule.

## Why this is needed

Axiom 8 (proposed v1.2 amendment) makes kernel self-claims auditable, which is necessary for non-illusory multi-factory architectures. But axiom 8 alone does not answer **whose authority hierarchy governs cross-kernel conflicts.** When federation A's hard-constraint and federation B's hard-constraint say opposing things in an overlapping scope, axiom 6 establishes authority within a kernel and axiom 8 makes claims auditable, but neither resolves the cross-kernel disagreement.

The classical responses to this are all unsatisfactory:

- **Fixed quorum.** Picks an arbitrary number at design time; fails when intractability exceeds the quorum.
- **Hierarchical override.** Designates a meta-sovereign with authority over both; reintroduces the centralization pathology axiom 8 was meant to refuse.
- **Vote.** Treats sovereigns as commensurable units; loses the authority differentiation axiom 6 establishes.
- **Treaty.** Off-substrate agreement; not auditable, not (I, R)-formed, not enforceable from inside the kernel.

The proposal: **make sovereign-count a function of conflict intractability, recruited recursively via Fibonacci composition, with full (I, R) discipline at every tier.**

## The primitive

### Operation signature

```
kernel.escalate(
  contested_ir: <ir-id>,
  current_tier_sovereigns: list[<sovereign-id>],
  current_tier_records: list[<ir-id>],
  stakes: <stakes-level>
) -> {
  outcome: <typed-outcome>,
  next_tier_proposal: list[<sovereign-id>] | null,
  escalation_record_id: <ir-id>
}
```

### Behavior

1. The current tier of sovereigns has attempted to resolve `contested_ir` and produced a set of records (`current_tier_records`) that the tier members declare to be in irreconcilable disagreement. Each record is itself an (I, R) per axiom 8.

2. `kernel.escalate` examines the records, applies axiom 6's authority hierarchy within the tier, and determines whether the tier has converged or remains divergent.

3. If converged, the operation emits the converged resolution as an (I, R) and terminates.

4. If divergent, the operation:
   - Computes the next Fibonacci tier size: F(n+1) = F(n) + F(n-1), where current tier size is F(n).
   - Proposes the additional sovereigns to recruit (size F(n-1) — the tier-before-previous, per the composition-over-replacement principle).
   - Emits `ESCALATION_REQUIRED` with the proposed next-tier composition.
   - Creates an `_kernel.escalation-record` (I, R) capturing the tier history.

5. If the next tier would exceed the stakes-bounded ceiling (per termination rule below), the operation emits `ESCALATION_EXHAUSTED` instead, with the unresolved (I, R) preserved as such.

### Sovereign selection

**This is a deferred question.** The protocol needs to specify which additional sovereigns are recruited at each tier, and the obvious failure modes (existing tier picks a sympathetic third; deterministic registry becomes the locus of power and the question recurses) are not solved by this proposal.

The proposal punts to the Founders Republic / Tribunal-of-Judges patterns noted in the project state, which contain authority-arbitration machinery that may supply the answer. Specific resolution is **OPEN-Q-N4** for this proposal.

### Continuity of memory

Per the Fibonacci composition F(n+1) = F(n) + F(n-1), the sovereigns who participated at tier n are *still in the room* at tier n+1. Their reasoning, their dissents, their bridges-walked carry forward. The escalation does not reset; it accretes. New sovereigns join an existing conversation rather than replacing it.

This matches how human deliberative bodies actually work when they work — a hung jury does not dissolve and reform; it adds voices or accepts irresolution.

## The new projection type

### `_kernel.escalation-record`

**Purpose.** Capture the tier-by-tier history of an escalation: which sovereigns participated at each tier, what their positions were, what convergence (or lack of) was observed, what outcome was emitted.

**Authority.** `convention`. Escalation records are operation-output records.

**Projection-declared frontmatter extensions:**

- `escalation_id: <slug>` — must equal the (I, R)'s `id`.
- `contested_ir: <ir-id>` — the (I, R) under contest.
- `tier_history: list[<tier-record>]` — ordered list of tier records, each containing:
  - `tier_number: <int>` — Fibonacci index.
  - `tier_size: <int>` — F(tier_number).
  - `sovereigns: list[<sovereign-id>]` — participating sovereigns.
  - `position_records: list[<ir-id>]` — (I, R) records of each sovereign's position.
  - `convergence_assessment: converged` \| `divergent` \| `pending` — outcome at this tier.
  - `assessed_at: <iso8601>` — when convergence was assessed.
- `current_tier: <int>` — the tier currently active or last completed.
- `stakes: <stakes-level>` — inherited from the contested (I, R).
- `max_tier: <int>` — stakes-bounded ceiling per termination rule.
- `terminal_outcome: converged` \| `exhausted` \| `null` — null if escalation is ongoing.
- `terminal_resolution: <ir-id>` \| `null` — the converged resolution if `terminal_outcome = converged`.

**Body shape.** Prose narrative of the escalation history, optional but RECOMMENDED for high-stakes escalations.

**On-disk location.** `ir/_ops/escalation-record/<escalation-id>.md`. Filename suffix `.escalation.md`.

**Bootstrap.** `kernel.init` creates no escalation records.

## The typed outcomes

### `ESCALATION_REQUIRED`

Emitted when a tier has been assessed as divergent and the next tier is below the stakes-bounded ceiling. Carries the proposed next-tier sovereign composition. Callers act on this by recruiting the proposed sovereigns and re-invoking `kernel.escalate` at the next tier.

### `ESCALATION_EXHAUSTED`

Emitted when a tier has been assessed as divergent and the next tier would exceed the stakes-bounded ceiling. The contested (I, R) remains unresolved, with status `escalation-exhausted` recorded as part of its provenance.

This is **not a silent failure.** The exhausted state is itself an (I, R) per axiom 8 — recordable, supersedable, auditable. Callers can choose to re-attempt escalation if conditions change (new sovereigns become available, stakes are reassessed, a constituent sovereign updates its position), but the exhausted state is the kernel's honest record of "we recruited up to F(N) sovereigns and could not converge."

This is the typed-refusal pattern from the substrate contract applied to federation arbitration. The kernel does not pretend convergence; it records honest exhaustion.

## Stakes-bounded termination

Real systems need a ceiling. Without one, the protocol is theoretically generative but practically a denial-of-service vector — adversaries can force escalation forever by refusing to converge.

The termination rule: **each stakes level declares its maximum tier.** Higher stakes admit more tiers; lower stakes admit fewer.

Suggested defaults (subject to amendment at ratification):

- `stakes: low` — max tier 3 (F(3) = 2 sovereigns).
- `stakes: medium` — max tier 5 (F(5) = 5 sovereigns).
- `stakes: high` — max tier 7 (F(7) = 13 sovereigns).
- `stakes: critical` — max tier 8 (F(8) = 21 sovereigns).

Beyond max tier, `ESCALATION_EXHAUSTED` is emitted regardless of remaining divergence. The (I, R) under contest stays unresolved and decays per axiom 4 normal mechanisms.

## How this composes with existing axioms

- **Axiom 0.** Each sovereign is, from the perspective of the others, partially "outside." Escalation is the protocol by which federations of kernels expand each other's inside.
- **Axiom 2.** The escalation record is itself an (I, R) graph; tier records decompose into sovereign positions, which decompose into resolution attempts, which decompose normally per axiom 2.
- **Axiom 4.** Escalation outcomes decay. An `ESCALATION_EXHAUSTED` outcome at time T may be re-attempted at time T+Δ; the prior exhaustion does not bind.
- **Axiom 5.** The sovereigns themselves are characterized by cost and capability vectors. Escalation tier composition can in principle be informed by capability characterization, though this proposal does not specify the mechanism.
- **Axiom 6.** Authority within a tier follows axiom 6's hierarchy; cross-tier authority is the question this primitive answers.
- **Axiom 7.** Surrogates for past escalations may be trained — the kernel can learn from "escalations of this shape with these sovereigns at these stakes converged at tier N" and propose tier-1 escalations that pre-empt the recruitment recursion. This is a future block.
- **Axiom 8.** Every escalation event, every tier record, every sovereign position is on the graph. The escalation protocol does not have a privileged voice. **The federation is on its own graph.**

## The same shape as axiom 8, applied one level up

Axiom 8 makes the kernel itself accountable on the same terms as user content. `kernel.escalate` makes the federation itself accountable on the same terms as a single kernel. Both are anti-greedy-aggregator moves. Both refuse a privileged register. Both work by saying "this thing that wants to be exempt from the discipline must instead participate in the discipline." See `TURTLES-PRINCIPLE-v0_1.md` for the unifying observation.

## Honest caveats

1. **Sovereign selection is unsolved.** Without a principled rule for which sovereigns are recruited at each tier, the protocol is gameable. This is the most significant open question for this proposal (`OPEN-Q-N4`).

2. **Collusion at scale.** At small N, sovereign collusion is detectable because the conspirators' axiom-8 records are inspectable by the rest. At large N, collusion can hide in the *selection* of which sovereigns participate — adversarial selection becomes statistically invisible. The protocol may need scale-dependent hardening that this proposal does not specify.

3. **Federations of federations may need new primitives.** A meta-federation arbitrating between federations may have legitimate authority claims that do not reduce to the constituent federations' claims. Turtles-up may require new primitives at certain scales, not just recursive application of this one. See `OPEN-Q-004-substrate-topology.md` for the deeper question this gestures at.

4. **The Fibonacci choice is structural, not arbitrary.** The proposal claims Fibonacci specifically (not exponential, not linear, not arbitrary growing sequence) because of the composition-over-replacement property. This is a real claim, not aesthetic preference. If a future analysis shows another growth law has the same property at lower cost, the primitive should adopt it. The proposal commits to *the principle of recursive composition*, not to Fibonacci as such.

## Ratification track recommendation

Block 5+ kernel work, after axiom 8 lands in v1.2. Specifically:

1. **v1.2** ratifies axiom 8.
2. **A subsequent block** (numbering TBD) ratifies `kernel.escalate` as a kernel primitive, the `_kernel.escalation-record` projection, and the typed outcomes. This is plausibly v1.3 if additive, v2.0 if breaking.
3. **Sovereign selection (`OPEN-Q-N4`)** is resolved separately, possibly through a Founders Republic / Tribunal pattern; that resolution may itself land in a separate amendment.

The primitive should not be ratified ahead of axiom 8. Without reflexivity, the escalation records are not honestly inter-kernel-readable, and the primitive degrades to centralized arbitration.

## Open questions introduced

- **OPEN-Q-N4.** Sovereign selection rule for `kernel.escalate`. Unsolved as of this proposal.
- **OPEN-Q-N5.** Adversarial-selection hardening at large N. May require scale-dependent machinery this proposal does not specify.
- **OPEN-Q-N6.** Whether federations-of-federations need new primitives beyond recursive application of `kernel.escalate`. Cross-references `OPEN-Q-004-substrate-topology.md`.

These should be assigned `OPEN-Q-` numbers from the project's open-questions register at ratification time.

## Cross-reference

- The axiom this primitive depends on is in `AXIOM-8-AMENDMENT-PROPOSAL-v0_1.md`.
- The unifying observation that this primitive expresses at federation scale is in `TURTLES-PRINCIPLE-v0_1.md`.
- The deeper question of how far up the recursion goes is in `OPEN-Q-004-substrate-topology.md`.
- The full derivation is in `CHAT-13-CONVERSATION-LINEAGE.md`.

---

*End of `kernel.escalate` primitive proposal.*
