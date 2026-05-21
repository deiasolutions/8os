---
id: 8OS-OVERVIEW
version: 3.0.0
status: published
kind: overview
scope: project
domain: 8os/communication
authored_by: Q88N + Claude
authored_on: 2026-04-29
supersedes: 8OS-OVERVIEW v2.0
superseded_by: null
depends_on:
  - 8OS-AXIOMS-PLAIN-LANGUAGE v0.2.0
  - 8OS-KERNEL-SPEC v0.1.0
  - 8OS-BLOCK-1-SPEC v1.1
  - PRISM-IR-SPEC v1.1
revisit_when: a major architectural commitment ships (kernel.outside.http; skills/leases; surrogate manufacturing; first non-trivial multi-factory deployment) or external framing of the project shifts
provenance: drafted during the 2026-04-29 publish track; succeeds v2.0 (which had a stale honest-gaps section, a SCAN cost figure inconsistent with the SCAN writeup, and an eighteen-op tension this draft resolves) and v1.0; structural framing drawn from 8OS-AXIOMS-PLAIN-LANGUAGE v0.2.0; public framing drawn from "The Ceiling Isn't Intelligence. It's Reach." by Dave Eichler (2026-04-29)
---

# 8OS — Overview

## What this document is

The canonical overview of 8OS as of 2026-04-29. Pairs with three other artifacts: the kernel spec for the technical contract (`docs/spec/8OS-KERNEL-SPEC-v0.1.md`), the axioms-in-plain-language doc for vocabulary (`docs/8OS-AXIOMS-PLAIN-LANGUAGE.md`), and the demo trio for empirical evidence the substrate carries load.

This overview is not a tutorial and not a manifesto. It is the orienting document for someone deciding whether to read further.

---

## 1. Reach

The dominant story about AI capability is that it scales with intelligence. Bigger models, more context, better reasoning, longer chains of thought. Throw enough cognition at a problem and the system gets to an answer.

That story is incomplete in a way that matters. The actual ceiling on what an AI system can do isn't how smart it is. It's what it can reach into the world to actually touch.

**A system can only resolve what it has bridges to reach.**

No amount of additional cognition substitutes for an absent bridge. If your agent has no bridge to your calendar, no chain-of-thought reasoning will book your meeting. If it has no bridge to your codebase, it cannot ship code regardless of how cleverly it can describe what should be shipped. The bridge inventory is the hard ceiling. Everything else is decoration on top of that ceiling.

8OS is a runtime kernel built around taking that seriously.

---

## 2. The (I, R) primitive

Reach names what 8OS is *for*. (I, R) names what 8OS *is*.

Every decision in a software project is two things stuck together: an intention (what we want) and a resolution (what we did about it). The pair — (I, R) — is the atomic unit of 8OS. Every artifact the kernel manages — specs, code, tests, ADRs, prompts, policies, training datasets, configuration values — is either an (I, R) pair or a structured collection of (I, R) pairs.

The two framings are complementary, not competing. Reach is the binding constraint; (I, R) is the unit. Public-facing artifacts open with reach because it lands without prerequisites. The spec opens with (I, R) because that is what is actually under construction.

---

## 3. The eight axioms

The kernel ABI is locked at eight axioms (numbered 0–7). In plain English:

- **Axiom 0 — Inside / Outside.** There is an inside, which is recursive. There is an outside, which is not.
- **Axiom 1 — Primitive.** (I, R) is the atom.
- **Axiom 2 — Fractal.** Every (I, R) decomposes into more (I, R) until it bottoms out at a bridge.
- **Axiom 3 — Bounded propagation.** Resolutions affect a finite, scope-bounded reach.
- **Axiom 4 — Temporal validity.** Resolutions decay; time is a first-class kernel concern.
- **Axiom 5 — Resolver characterization.** Every resolver has a cost vector and a capability vector, per domain.
- **Axiom 6 — Provenance and authority.** Every (I, R) records who produced it and with what standing.
- **Axiom 7 — Surrogate substitution.** The kernel can manufacture learned approximations of resolvers from operational history; the inside / outside boundary moves inward over time.

The lifecycle, in one sentence: a unit of knowledge in 8OS comes into being, nests with other knowledge, ages and may decay, is resolved by mechanisms with measurable cost and capability, has provenance that governs its standing, and the mechanisms that resolve it can themselves be replaced by learned approximations over time — all within a kernel that recognizes its own boundary with an outside reality.

Five-bucket distillation: axiom 0 is foundational cosmology; 1–3 are structural; 4 is dynamic; 5–6 are operational; 7 is generative.

Full plain-English and formal registers for each axiom live in `docs/8OS-AXIOMS-PLAIN-LANGUAGE.md`.

---

## 4. The four layers

8OS has four layers. Keeping them distinct is load-bearing.

- **Kernel.** What 8OS is. The substrate primitives — the (I, R) atom, the eight axioms, regeneration discipline, scope/projection/authority machinery. ABI locked at v0.1; binary at v1.1.0-dev.6.
- **PRISM-IR.** The projection language that runs on 8OS. The program; the source language for (I, R) graphs. Currently at v1.1; covers 43/43 of the Workflow Patterns.
- **Factory.** The runtime layer that walks (I, R) graphs and dispatches resolvers. Different factories can compose different policies on the same kernel — this is what makes the multi-factory roadmap a real architectural option rather than a slogan.
- **Application.** Whatever the user composes on top — domain programs, governance systems, agent-coordination patterns. The kernel hosts; it does not impose.

This separation is the difference between an ontology and a framework. A framework tells you how to build. An ontology tells you what the pieces are. Frameworks come and go with their decade. Ontologies, when they're right, persist through several frameworks. 8OS is built as an ontology.

---

## 5. The SDK

The kernel exposes a **fixed SDK operation set**. Wire format: JSON in on stdin, JSON out on stdout, structured errors on stderr with stable error codes.

The SDK operations divide into four functional groups:

- **Graph operations** — `kernel.ir.new`, `kernel.ir.list`, `kernel.ir.get`, `kernel.ir.supersede`, `kernel.ir.cancel`. The operations through which all (I, R) records enter, leave, or transform. (I, R) records include user content, kernel-state records, projection definitions, and resolver/bridge declarations — there are no typed configuration ops; everything goes through `kernel.ir.new`.
- **Kernel-state inspection** — `kernel.init`, `kernel.reindex`, plus listings for scopes, projection types, resolvers, and bridges.
- **Capability machinery** — resolver selection, capability updates, authorization, policy evaluation.
- **Event-log operations** — query and append against the tier-3 event ledger.

Outside-call mechanics — `kernel.outside.http` per spec §11 — are *not* SDK operations. They are the kernel's primitive for crossing the inside/outside boundary that bridges use under the hood. Counting outside-call mechanics as an SDK op is a category error: the SDK is the surface user programs touch; outside-call mechanics are the kernel's plumbing.

The boundary between SDK and plumbing is itself part of the design.

---

## 6. Resolver characterization

Every resolver carries two vectors:

- **Cost vector** measured in Clock, Coin, Carbon — what the resolver consumes per invocation.
- **Capability vector** measured in σ (Quality), π (Preference), α (Autonomy), ρ (Reliability) — what the resolver brings to a given domain.

Both vectors are domain-specific. Resolver selection is a fitness function over both, weighted by intention demands. Both are measured empirically through actual operation and refined continuously — this is the property that makes axiom 5 not an aspiration but a working contract.

v1.1 commits to a sharpening called **three-cost decomposition**: the Clock/Coin/Carbon cost is split into `resolver_cost` (the resolver's own consumption), `kernel_cost` (the kernel's coordination overhead), and `factory_cost` (the runtime substrate's overhead). This lets the kernel attribute cost to the right layer when deciding which to optimize. Three-cost is committed but not yet implemented; the cost vector currently lands entirely in the `resolver_cost` slot.

---

## 7. Bridges — reach in detail

A resolver becomes a bridge when it crosses the inside/outside boundary. Bridges are how the kernel reaches what it cannot host as (I, R) directly — calendars, codebases, humans, sensors, the Anthropic API, a CPU instruction.

Two bridges are vendored at every kernel init:

- `kernel.self` — the kernel binary's own existence claim, the *cogito*. Authors `_kernel`-scope foundational records.
- `human-<primary-operator-id>` — the human's authority over the user scope.

Both bridges are real with real provenance; neither is a magic exception. The kernel and the human are co-equal foundations of the project's authority graph.

When the kernel cannot reach something, axiom 0 lets it say no honestly. **Saying no honestly is structurally different from hallucinating a yes.** Systems that cannot refuse hallucinate their way into damage. Systems that can refuse have somewhere to put the refusal. This is one of the operational consequences of taking reach seriously: the substrate has a place for "I cannot do this because the bridge doesn't exist" as a first-class outcome.

---

## 8. Tiers and authority

Two orthogonal classifications. Easy to conflate, important to keep distinct.

**Tiers** describe the *kind* of (I, R) record. Every (I, R) is one of three:

- **Tier 1** — substantive content the project produces (specs, decisions, ADRs, knowledge artifacts).
- **Tier 2** — operational records the kernel authors itself when it makes a choice (resolver selections, authorizations, capability updates, policy evaluations).
- **Tier 3** — the event ledger; an append-only stream capturing every resolution event in a form usable as future training data (the ABCDEFG discipline that makes axiom 7 possible).

**Authority levels** describe the *standing* of a resolution:

- **Hard** — foundational, sealed, override only with documented justification through an authoritative bridge.
- **Convention** — defaults a contributor sets; another contributor may override with documented reason.
- **Uncalibrated** — outputs from agents needing validation before binding anything downstream.

The two classifications are independent. A tier-1 record can carry hard or convention authority. A tier-2 record always carries `kernel.self` authority because the kernel authored it. A tier-3 event inherits its authority from the operation that produced it.

---

## 9. Provenance and authority machinery

Every (I, R) records who produced it and with what standing. Provenance includes whether the resolution came from inside (a recursive (I, R) graph) or from outside (a bridge), and if outside, what the bridge was.

Authority is derived from provenance. The kernel manages it through a small set of named concepts:

- **Roles** — named bundles of authority a contributor or bridge can hold within a scope. The role is what the kernel checks when authorizing a write, not the contributor's identity directly.
- **Policies** — rules the kernel evaluates when a record is created, modified, or referenced. Policies decide whether an operation proceeds and what authority level it carries.
- **Policy evaluations** — audit records left behind by each policy application. The trail showing which policy fired, against what input, with what outcome.
- **Skills** — named capabilities a resolver advertises, with install-time policy gating and revocation through cancellation. Lets the kernel route an intention to a resolver based on what the resolver has declared it can handle.
- **Leases** — time-bounded grants of authority. Authority that doesn't expire accumulates indefinitely; leases force authority to be renewed or it lapses.

Roles, policies, and policy evaluations are implemented (Block 4.7, v1.1.0-dev.6). Skills and leases are committed in v1.1 but not yet implemented.

---

## 10. Surrogate substitution

The kernel's resolver inventory is *generative* over time, not fixed at design.

Every resolver continuously generates training data through normal operation — the ABCDEFG discipline (*Always Be Collecting Data Everywhere For GenAI*). When sufficient operational history exists, the kernel can manufacture **surrogate resolvers** — typically learned models — that approximate an original resolver's input-output behavior at substantially lower cost.

Surrogate creation is the operation that moves the inside / outside boundary inward. What was previously an outside-call becomes an internal computation. Mature kernels have small boundaries; new kernels have huge ones. The kernel's growth over time is the inward movement of that boundary.

Axiom 7 is committed in the kernel ABI. The corpus substrate is already in place — Block 2.8 shipped the calibration-corpus index that captures resolution events in a form usable as future training data. What remains unbuilt is the manufacturing pipeline: the machinery that takes the corpus and produces a surrogate. The pipeline is on its own track, downstream of tier-B and tier-C work.

---

## 11. The empirical witness — the demo trio

Architecture that only works in slides is a hobby. The substrate's claim is that the (I, R) primitive carries load across paradigms — that the **decomposer slot is general**.

Three structurally distinct uses of the same kernel back this claim:

**Demo #1 — L-system fractals.** A deterministic decomposer plus a browser-driven outside-call adapter renders Lindenmayer fractals end-to-end. Same kernel, same PRISM-IR program, two different fractals (Koch snowflake and bushy tree) drawn into a canvas adapter that knew nothing about either system. *Witnesses:* deterministic decomposition + outside-call adapter integration.

**Demo #2 — SCAN dogfood.** An LLM-mediated decomposer plus real HTTP fetches produces a daily-briefing artifact. The decomposer slot is now filled by an LLM rather than a deterministic function; the outside-calls touch real HTTP rather than an in-process adapter. SCAN's records replay clean against the current binary at v1.1.0-dev.6. *Witnesses:* LLM mediation + real-network bridges + durability across kernel revisions. Cost: ~$0.04 per run.

**Demo #3 — decomposition-strategy.** Programs producing programs at runtime, hosted by the same substrate. A PRISM-IR program whose resolution is more PRISM-IR programs that the same kernel then runs, with no kernel changes between phases and no distinguishing treatment for human-authored vs program-authored records. *Witnesses:* self-composition; the substrate's primitives suffice for the loop to close. Cost: $0.

Three different decomposers (deterministic / LLM / program-authored). Three different outside-call profiles (browser adapter / real HTTP / no outside calls). One kernel, one primitive. **The decomposer slot is general.** That is the property that distinguishes a real abstraction from a private vocabulary.

Writeups: `lsystem-demo/docs/koch-snowflake.md`, `8os/docs/demos/scan.md`, `decomposition-strategy-demo/docs/writeup.md`.

---

## 12. What this enables

Three implications, in increasing order of how much they cut against current practice.

**Spend more time on bridges, less on prompts.** The marginal hour invested in connecting the system to one more real-world capability buys more than the marginal hour spent making it slightly more articulate about capabilities it doesn't have.

**Separate the durable parts from the disposable parts.** Intentions are durable, declarative, inspectable. Resolvers are interchangeable. The same intention might be resolved by a human today, an LLM tomorrow, a learned surrogate next year, and the system can reason about which is appropriate at any given moment. If your architecture entangles intentions with specific models, you'll rewrite the architecture every time the model layer shifts — which is roughly every nine months at current cadence. If you don't entangle them, you won't.

**Stop treating intelligence as the scarce resource.** The scarce resource is **governed reach** — reach you can audit, reach with bounded authority, reach that records what it did and what it cost. The systems that will matter in five years are not the ones with the smartest model in the loop. They're the ones whose bridges are real, whose intentions are inspectable, and whose refusals are honest.

---

## 13. Honest gaps

What is and isn't built, as of 2026-04-29. Binary at v1.1.0-dev.6. 377 tests passing.

**Implemented:**

- The eight axioms as a working kernel ABI (locked at v0.1).
- The SDK operation contract.
- Tier-A v1.1 base frontmatter: `domain` (Block 4.1), `data_classification` (Block 4.3), `visible_when` predicate engine (Block 4.4).
- `kernel.ir.cancel` and the `cancelled` status enum (Block 4.2).
- v1.1 housekeeping (Block 4.5).
- Path A: `kernel.ir.new` with `supersedes:`, `kernel.ir.list include_cancelled` (Block 4.6).
- Policy machinery: `_kernel.role`, `_kernel.policy`, `_kernel.policy-evaluation`, `op_pipeline.py` (Block 4.7).
- The demo trio.

**Committed in v1.1 but not yet implemented:**

- `kernel.outside.http` — the in-kernel outside-call primitive.
- Skills and leases (the remaining authority machinery).
- Three-cost decomposition (`resolver_cost` / `kernel_cost` / `factory_cost` in the cost vector).
- Frame / Branch / Alterverse — the branched-resolution machinery.
- DuckDB as the storage engine.
- Bridges-as-PRISM-IR programs.
- Surrogate manufacturing (axiom 7's generative property).

The gap between "committed in v1.1" and "implemented in v1.1.0-dev.6" is named honestly so the substrate's actual capability isn't oversold. A kernel that pretends to do what it can't is the failure mode 8OS exists to avoid.

---

## 14. The sequence

What gets built next, in order. The publish-prep phase (this overview, the demo writeups, repo hygiene) was the immediate next step after Block 4.7. Implementation work resumes against the now-public artifact; the order is committed.

**Tier-B remainder.** The committed-but-unimplemented v1.1 features land in this order:

1. `kernel.outside.http` + `_kernel.lease` bundle — the in-kernel outside-call primitive together with time-bounded authority grants. Block 4.8.
2. `_kernel.skill` — the resolver-capability advertisement layer.
3. Three-cost decomposition — splits `resolver_cost` / `kernel_cost` / `factory_cost` in the cost vector.
4. Bridges-as-PRISM-IR — bridges expressed as PRISM-IR programs rather than vendored binary code.
5. `_simulation.alterverse-store` — Frame / Branch / Alterverse machinery.

**Tier-C.** Post-tier-B infrastructure work:

6. DuckDB storage migration — replaces the current filesystem-backed kernel state.
7. Multi-factory binary support — hardens the "different factories on the same kernel" architectural claim into shipping code.

**Surrogate work.** On its own track, downstream of tier-B and tier-C. The corpus substrate is already in place (Block 2.8 shipped the calibration-corpus index). What remains is the manufacturing pipeline that takes the corpus and produces a surrogate. This is the work that makes axiom 7's generative property observable in practice.

The committed sequence is what makes the gap between v1.1 architecture and v1.1.0-dev.6 implementation closeable rather than mysterious.

---

## 15. Where to read next

| If you want | Read |
|---|---|
| The vocabulary | `docs/8OS-AXIOMS-PLAIN-LANGUAGE.md` — plain-English register, axioms, full glossary |
| The kernel ABI | `docs/spec/8OS-KERNEL-SPEC-v0.1.md` — the eight axioms as locked contract |
| The active spec | `docs/spec/8OS-BLOCK-1-SPEC-v1_1.md` — v1.1 architectural commitment |
| The projection language | `docs/spec/PRISM-IR-SPEC-v1.1.md` — what gets written on the substrate |
| Demo #1 — deterministic + adapter | `lsystem-demo/docs/koch-snowflake.md` |
| Demo #2 — LLM + real HTTP | `8os/docs/demos/scan.md` |
| Demo #3 — self-composition | `decomposition-strategy-demo/docs/writeup.md` |
| The reach framing | "The Ceiling Isn't Intelligence. It's Reach." (Dave Eichler, 2026-04-29) |

---

## 16. Closing

8OS is a substrate. It is small. It is a kernel. It tries to do nothing it doesn't have to do. The thesis is that the small thing is the load-bearing thing, and that everything else — including the things the industry is currently treating as central — is downstream of it.

The ceiling isn't intelligence. It's reach. Build accordingly.

---

*8OS-OVERVIEW v3.0 — supersedes v2.0 (2026-04-28) and v1.0. Authored 2026-04-29 during the publish track. Pairs with `docs/8OS-AXIOMS-PLAIN-LANGUAGE.md` v0.2.0 (vocabulary), the v1.1 specs (technical contract), and the demo trio (empirical witness).*
