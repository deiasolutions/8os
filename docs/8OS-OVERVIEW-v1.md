---
id: 8OS-OVERVIEW
version: 1.1
status: superseded
kind: entry-point
scope: project
domain: 8os
authored_by: Q88N + Claude
authored_on: 2026-04-28
superseded_by: 8OS-OVERVIEW v3.0
provenance: written to give a new reader a complete-but-honest picture of 8OS as it stands. Points at canonical specs; does not replace them. Cross-referenced against `docs/audits/RECON-8OS-CANONICAL.md`. Refreshed for v1.1 alignment as part of the publish-prep cleanup. Filename retained as `8OS-OVERVIEW-v1.md` (durable entry-point name); version-of-record is in frontmatter.
---

> **Superseded by [8OS-OVERVIEW v3.0](8OS-OVERVIEW-v3.md) on 2026-04-29.** Preserved for lineage. v3 reflects the architectural commitment for v1.1 plus the empirical-witness demo trio; this v1 captures the project state at 2026-04-28.

# What is 8OS

**8OS is a runtime that executes PRISM-IR programs.**

PRISM-IR is the program — the source language declaring intent and structure. 8OS is the kernel: the substrate the program runs on. The relationship is strictly that of language to runtime. PRISM-IR describes what; 8OS executes how.

This document is an entry point. It is not a spec. It points at the specs, summarizes what they say collectively, and is honest about what they don't yet say.

## The kernel

The kernel is defined by **eight axioms** (`docs/spec/8OS-KERNEL-SPEC-v0.1.md`), which lock the kernel ABI:

0. **Inside / Outside.** The kernel is recursive on the inside; bridges connect to an outside it observes but cannot decompose.
1. **Primitive.** Every artifact is an (Intention, Resolution) pair or a structured collection of them.
2. **Fractal.** Every (I, R) is itself a graph of (I, R)s, expandable or collapsible at any depth.
3. **Bounded propagation.** Consequential reach is finite and locally computable.
4. **Temporal validity.** Resolutions decay. Time is first-class.
5. **Resolver characterization.** Every resolver carries a cost vector (Clock, Coin, Carbon) and a capability vector (σ Quality, π Preference, α Autonomy, ρ Reliability), per domain.
6. **Provenance and authority.** Every (I, R) records who/what produced it and with what standing.
7. **Surrogate substitution.** Resolvers' operational history can train surrogates that progressively internalize the outside.

The kernel's instruction set is **17 operations** at v1.1 (`docs/spec/8OS-SDK-REFERENCE-v1.md` indexes them). v1.0.1-partial's sixteen operations are preserved verbatim; v1.1 adds `kernel.ir.cancel` and removes the v0.1 `kernel.surrogate.train` interface stub. Wire format is JSON-in, JSON-out subprocess calls. No in-process SDK exists by design; conformance lives at the wire boundary, not in any host language.

The active on-disk representation is **v1.1** (`docs/spec/8OS-BLOCK-1-SPEC-v1_1.md`), the architectural commitment that consolidates v1.0.0 + v1.0.1-partial + the Block 2.7/2.8 patches, adds the seventeenth operation, and resolves OPEN-Q-019 (`domain` lifted to optional base frontmatter, closed in Block 4.1). Earlier representations are preserved on disk for lineage but superseded.

The kernel binary is at v1.1.0-dev.2: Block 4.1 closed `domain`, Block 4.2 closed `kernel.ir.cancel` and the `cancelled` status enum value (and removed the `kernel.surrogate.train` stub from the registry). v1.1's "Implementation gap, named honestly" section names what is specified but not yet implemented (multi-factory machinery, leases, roles/policies, skills, three-cost decomposition, DuckDB storage, bridges-as-PRISM-IR programs, several base-frontmatter fields).

## Factories are userspace PRISM-IR programs

The substrate hosts programs. The program that walks the (I, R) graph, decides what to dispatch, and orchestrates resolver invocations is called a **factory**. Factories are not part of the kernel. They are userspace programs written against the SDK.

This cleavage matters:

- The kernel guarantees axioms 0–7 and the SDK contract. It hosts the (I, R) graph, indexes it, enforces bounded propagation, records authority, and emits cost-tracked tier 3 events when bridges are crossed.
- Factories *choose* dispatch policy, walking strategy, queue shape, retry/escalation rules, scheduler behavior. Different factories are possible without touching the kernel.

v1.1 §0.1 commits to a four-layer model — **kernel / PRISM-IR / factory / application** — that names this cleavage explicitly: anything mutually-distrusting factories cannot safely re-implement is kernel; anything declarative about a process is PRISM-IR; anything about how to execute is factory; anything domain-specific is application. v1.0 left this implicit; v1.1 makes it structural.

## What the kernel guarantees vs. what factories choose

| Concern | Kernel guarantees | Factory chooses |
|---|---|---|
| (I, R) primitive and graph hosting | Yes (axioms 1–3, v1.1 representation) | — |
| 17-op SDK contract | Yes (preserved across v0.1 → v0.2 → v1.0 → v1.0.1-partial → v1.1) | — |
| Bridge mechanics, gatekeeper, authorization | Yes (axiom 6, `_kernel.bridge`, `_kernel.authorization`) | — |
| Resolver characterization (cost + capability vectors) | Yes (axiom 5, `_kernel.resolver`) | Which resolvers to register |
| Three Currencies data model (Clock, Coin, Carbon) | Yes (axiom 5, tier 3 events with `escalation_purpose`, calibration corpus index) | The user-facing framing of "Three Currencies" as a launch story |
| Selector + calibrator + VOI | Kernel-internal resolvers; selection mechanics (v1.0 §5) | Calibration policy, standing authorizations |
| Round-trip oracle for PRISM-IR | Specified in `PRISM-IR-SPEC-v1.1.md`; not asserted as a kernel-level property | Whether to host one as a resolver (Block 3 did) |
| Dispatch loop, walker, decomposer/recomposer protocols | — | Yes — entirely factory concerns |
| Queue layout (`backlog/`, `_active/`, `_done/`, …) | — | Yes — see `docs/audits/AUDIT-FACTORY-QUEUE-001-OUTLINE.md` for one factory's actual layout |

When a future factory spec (SPEC-FACTORY-SPEC-001, see roadmap) lands, this table extends downward into the factory column.

## A demonstration: Block 3 SCAN run

Block 3 manifested the first end-to-end run on the substrate. The program: a small SCAN of `simdecisions/server.py` for hygiene findings, expressed as PRISM-IR. The kernel hosted the (I, R) graph; a hand-written factory walked it; the Anthropic bridge crossed to outside resolvers; results recomposed back to PRISM-IR for round-trip verification.

The full bundle — input PRISM-IR, kernel state, factory dispatch log, recomposed output — is at `docs/scan-block-3-bundle.md`. It is a demo writeup, not a spec.

What Block 3 demonstrated, in one line: the substrate can host and run a PRISM-IR program end-to-end with round-trip-verified output. What Block 3 did not produce: a canonical spec for the factory it built. The factory exists as code under `src/eightos/factory/` and as prose in `docs/block-3-report.md`. See *Honest gaps*.

## Discipline

The first reference factory — the queue runner and scheduler/dispatcher/triage daemons in the SimDecisions repo — is being audited deliberately rather than ratified by use. The audit (`docs/audits/AUDIT-FACTORY-QUEUE-001-OUTLINE.md`) examines what the daemons actually do against what they were assumed to do, names every conflict and gap, and produces a decision list (ratify / rename / retire / fix / rebuild / defer) before any factory spec is written.

This is the discipline the project is committing to: the kernel ABI is locked at v0.1; the representation is the source of truth at v1.1; everything above the kernel is examined deliberately before being made canonical. Reference factories are not assumed; they are characterized.

## Honest gaps (roadmap, not omissions)

The recon at `docs/audits/RECON-8OS-CANONICAL.md` inventoried what is and isn't canonically specified as of pre-v1.1. v1.1 closes several of those gaps in spec form (the four-layer model, the kernel/factory cleavage, bridges-as-PRISM-IR, three-cost decomposition, leases, roles/policies, skills) while explicitly naming each as not-yet-implemented in its "Implementation gap, named honestly" section.

The remaining gaps as of 2026-04-28 — items not specified in v1.1 either:

- **No factory spec.** v1.1 §0.1 names factories as a layer and §1 specifies the cleavage rules, but the factory's own spec — walker, dispatcher, decomposer protocol, queue surface — has no canonical document. SPEC-FACTORY-SPEC-001 is the planned home; the chat-6 reframe (factories as userspace PRISM-IR programs) is articulated in `docs/notes/NOTE-substrate-is-self-composing-runtime.md`.
- **No kernel-level round-trip oracle statement.** PRISM-IR v1.1 specifies round-trip as a property of PRISM-IR documents. The 8OS canonical specs do not assert that the kernel hosts a round-trip oracle as a guarantee of its own. Block 3 implemented one as a resolver; whether it should be a kernel-level property is open.
- **Resolver function-call contract.** Axiom 5 covers characterization; v0.2's `_kernel.resolver` covers registration. The runtime invocation contract — what a resolver function gets, what it returns, where bridge implementations live — is in code (`src/eightos/bridges/anthropic.py`) and in the Block 3 report, not in canonical spec form. v1.1's bridges-as-PRISM-IR direction will fold this in once implemented.
- **No autonomous-dispatch spec.** A draft outline lives at `docs/spec/drafts/SPEC-AUTONOMOUS-DISPATCH-001-OUTLINE.md`, superseded in framing by the factory-as-userspace reframe; will be folded into the eventual factory spec rather than dispatched standalone.
- **Three Currencies framing not canonical.** The data model is specified (axiom 5; tier 3 `escalation_purpose`; calibration corpus). v1.1 §11 specifies three-cost decomposition (resolver/kernel/factory). The user-facing framing — the phrase "Three Currencies" itself — appears in notes and outlines but not in `docs/spec/`.

The v1.1 implementation gap is *specified, not yet implemented* — distinct from the *not yet specified* gaps above:

- **Cancel op + `cancelled` enum landed in Block 4.2.** Reversibility (supersede-with-replacement of cancelled records) and the `include_cancelled` filter on `kernel.ir.list` are spec'd but not yet implemented — see Block 4.2 report frictions F3/F5.
- **v1.1 §3.8 / §18.1 vs §5.2 contradiction.** Error description contradicts the transition table on whether `stale → cancelled` is permitted. Block 4.2 implemented §5.2 (the transition table) as binding; §3.8 and §18.1 error descriptions need a reconciliation amendment. See Block 4.2 report's "Spec contradiction surfaced" section.
- **Other v1.1 architecture not yet implemented:** `kernel.outside.http`, leases (`_kernel.lease`), roles/policies (`_kernel.role`, `_kernel.policy`), skills (`_kernel.skill`), three-cost decomposition (`resolver_cost`/`kernel_cost`/`factory_cost`), `data_classification` and `visible_when` as base frontmatter, DuckDB storage, bridges-as-PRISM-IR programs. v1.1's own "Implementation gap, named honestly" section is the authoritative list.

## Where to read next

In order, depending on what you want:

| Want | Read |
|---|---|
| The eight axioms (kernel ABI) | `docs/spec/8OS-KERNEL-SPEC-v0.1.md` |
| The 17 ops, indexed | `docs/spec/8OS-SDK-REFERENCE-v1.md` |
| The active on-disk representation | `docs/spec/8OS-BLOCK-1-SPEC-v1_1.md` |
| The PRISM-IR side | `docs/spec/PRISM-IR-SPEC-v1.1.md` |
| Block 3's end-to-end demonstration | `docs/scan-block-3-bundle.md` |
| The reference-factory audit | `docs/audits/AUDIT-FACTORY-QUEUE-001-OUTLINE.md` |
| The canonical-corpus recon (what is and isn't specced) | `docs/audits/RECON-8OS-CANONICAL.md` |
| The longer-form articulation of the substrate-as-self-composing-runtime frame | `docs/notes/NOTE-substrate-is-self-composing-runtime.md` |
| The lineage of v1.1 (predecessor specs, kept on disk) | `8OS-BLOCK-1-SPEC-v1.0.1-PARTIAL.md`, `8OS-BLOCK-1-SPEC-v1.0.md`, plus the 2.7/2.8 patches |

The note in `docs/notes/` is the older and longer companion to this overview. This overview supersedes it as the entry point for outside readers; the note remains as the depth-articulation and historical record.

---

*End of 8OS Overview v1.1. Updates when the answer to "what is 8OS" changes.*
