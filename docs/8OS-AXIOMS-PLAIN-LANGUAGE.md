---
id: 8OS-AXIOMS-PLAIN-LANGUAGE
version: 0.3.0
status: capture
kind: language-reference
scope: project
domain: 8os/communication
authored_by: Q88N + Claude
authored_on: 2026-05-02
supersedes: null
superseded_by: null
depends_on: 8OS-KERNEL-SPEC v0.2.0
revisit_when: a public-facing artifact (overview, article, README) is being drafted
provenance: rediscovered during 8OS - Chat 11; sourced from Block 0 derivation, the chat-3 review, and the ELI5 distillation. v0.2 (2026-04-29) added the reach framing section and seventeen publish-track glossary entries (PRISM-IR, factory, decomposer slot, tier 1/2/3, domain, data classification, visible-when, role, policy, policy evaluation, skill, lease, frame, branch, Alterverse, three-cost decomposition, DuckDB), ratified during the Overview v3 surface-back. v0.3 (2026-05-02, Block 5.0) adds axiom 8 (Reflexivity) per kernel spec v0.2 ratification, updates the compositional structure to nine axioms, and adds the *reflexivity* glossary entry.
---

# 8OS — Axioms in Plain Language

## What this document is

A capture of the plain-language register for the (I, R) primitive and the eight axioms, alongside the formal statements from the v0.1 spec. The plain-language versions exist because they were produced during early derivation and ELI5 work, but they live scattered across chat history and risk being lost.

This document holds them together so public-facing artifacts (Overview v3, LinkedIn pieces, READMEs) can draw from a single source rather than re-derive them.

Three registers per concept:

- **Plain English.** The version a reader who has never heard of 8OS understands without context.
- **Formal statement.** The version the spec text uses. Precise, technical, complete.
- **Compositional role.** Where this piece sits in the structure of the whole.

---

## The (I, R) primitive — plain language

> Every decision in a software project is really two things stuck together: what we want (the intention) and what we did about it (the resolution). That pair — call it (I, R) — is the smallest building block.

That sentence is the doorway. A reader who only ever reads that one sentence understands what 8OS is built on.

---

## The reach framing

> The structural framing — what 8OS *is* — is (I, R). The public framing — what 8OS is *for* — is reach. A system can only resolve what it has bridges to reach into the world. No amount of additional reasoning substitutes for an absent bridge.

The two framings are complementary, not competing. (I, R) gives the unit; reach gives the binding constraint. Public-facing artifacts open with reach because it lands without prerequisites; the spec opens with (I, R) because that is what is actually under construction.

---

## Supporting terms

The axioms below use a small set of named concepts. Plain-English definitions, in the order a reader will encounter them:

- **Resolver.** A mechanism that produces a resolution for a given intention. May be a deterministic computation, a human, an LLM, an empirical test, a simulation, a retrieval, a learned surrogate, or any other mechanism that can answer.
- **Bridge.** A resolver that crosses the inside/outside boundary. Bridges are how the kernel reaches things it cannot host as (I, R) directly — calendars, codebases, humans, APIs, sensors, the Anthropic API, a CPU instruction.
- **Surrogate.** A resolver that lives entirely inside, learned from operational history of another resolver — typically one that previously bridged outside. Surrogates are how the boundary moves inward over time.
- **Reflexivity.** The kernel's claims about its own state — what resolvers it has, what capability scores it has measured, what policies are active, what indexes it has regenerated — are themselves (I, R) records on the kernel's graph, not assertions in a privileged register. The kernel does not exempt itself. Named in axiom 8.
- **PRISM-IR.** The projection language that runs on 8OS. The program; the source language in which (I, R) graphs are written. Where 8OS is the substrate, PRISM-IR is what gets written on it.
- **Factory.** The runtime layer that walks (I, R) graphs and dispatches resolvers. Distinct from the kernel: the kernel hosts records and enforces structure; the factory decides what to work on next and how to fan out execution. Different factories can compose different policies on the same kernel.
- **Decomposer slot.** The slot in the substrate that takes an intention and produces a smaller graph of intentions resolving it. Can be filled by a deterministic function, an LLM, a human, or any mechanism that can break a problem down. Generality of the slot is what makes the substrate composable across paradigms.
- **Scope.** A frame of consequential reach within the (I, R) graph. Resolutions propagate within their scope; outside their scope they are invisible. Scope is hierarchical: project > domain > module > feature.
- **Tier 1 / Tier 2 / Tier 3.** The three kinds of (I, R) record the kernel manages. Tier 1 is substantive content — the specs, decisions, ADRs, and other knowledge the project produces. Tier 2 is operational records the kernel authors itself when it makes a choice — which resolver it selected, which authorization it granted, which capability assessment it recorded. Tier 3 is the event ledger — an append-only stream capturing every resolution event in a form usable as future training data. Authority levels (hard, convention, uncalibrated) are separate from tiers and describe the standing of a resolution.
- **Domain.** A named topical area within a scope. Lets the kernel route policies, calibrations, and resolver selection to the right subset of records when scope alone is too coarse.
- **Data classification.** A label on a record governing how its content may be handled — what may be sent to an outside resolver, what must stay inside, what is shareable. The kernel enforces classification gates at bridge boundaries.
- **Visible-when.** A predicate that conditions a field's relevance on other field values, so a record's shape adapts to context without proliferating projection types. Fields whose `visible_when` evaluates false are absent from validation, not merely empty.
- **Role.** A named bundle of authority a contributor or bridge can hold within a scope. The role is what the kernel checks when authorizing a write — not the contributor's identity directly.
- **Policy.** A rule the kernel evaluates when a record is created, modified, or referenced. Policies decide whether an operation proceeds and what authority level it carries. Each evaluation produces an audit record (see policy evaluation).
- **Policy evaluation.** The record left behind when a policy is applied — the audit trail showing which policy fired, against what input, with what outcome. Lets later resolvers reason about why an authorization decision went the way it did.
- **Skill.** A named capability a resolver advertises. Lets the kernel route an intention to a resolver based on what the resolver has declared it can handle, with install-time policy gating and revocation through cancellation.
- **Lease.** A time-bounded grant of authority to act on a scope. Authority that doesn't expire accumulates indefinitely; leases force authority to be renewed or it lapses.
- **Frame.** A coherent slice of the (I, R) graph at a point in time. The kernel uses frames to reason about state as of a moment — what was true, what was resolved, what was pending — without confusing it with the present state.
- **Branch.** A divergent line of resolution from a frame, where the kernel explores an alternative without committing to it. Branches let the kernel reason about counterfactuals before deciding.
- **Alterverse.** The tree of all branches the kernel has explored or could explore — every counterfactual line of resolution preserved as a navigable structure. Lets the kernel ask "what if" questions across coherent sets of divergent resolutions without polluting the canonical graph.
- **ADR.** Architecture Decision Record. A standard format in software engineering for capturing a decision and its rationale. In 8OS, an ADR is one projection of an (I, R) pair.
- **σ, π, α, ρ.** The four capability dimensions, named by Greek-letter convention: σ (Quality), π (Preference), α (Autonomy), ρ (Reliability). They describe what a resolver brings to a given domain.
- **Clock, Coin, Carbon.** The three components of the cost vector: time consumed, money consumed, carbon consumed. The kernel tracks all three for every resolution event.
- **Three-cost decomposition.** A sharpening of the Clock/Coin/Carbon cost vector that splits each cost into three components by where it was incurred — `resolver_cost` (the resolver's own consumption), `kernel_cost` (the kernel's coordination overhead), and `factory_cost` (the runtime substrate's overhead). Lets the kernel attribute cost to the right layer when deciding which to optimize.
- **ABCDEFG.** *Always Be Collecting Data Everywhere For GenAI.* The discipline that every resolution event is captured in a form usable as future training data. This is what makes axiom 7 (surrogate substitution) possible.
- **DuckDB.** The columnar storage engine 8OS commits to for kernel state in v1.1. Chosen for speed on analytical queries over (I, R) records and for embedding without a server.

---

## The eight axioms

### Axiom 0 — Inside and Outside

**Plain English.** There is an inside, which is recursive. There is an outside, which is not.

**Formal statement.** The kernel exists within a larger reality it cannot fully contain. Inside the kernel is recursive: every (I, R) decomposes into more (I, R). Outside the kernel is not: there is something there that the kernel observes through bridges but cannot decompose. Resolvers are the bridges between inside and outside. The kernel's growth over time is the inward movement of the boundary as outside-calls are progressively internalized through surrogate training, captured decisions, and accreted patterns.

**Compositional role.** Foundational cosmology. Names where the recursion stops.

---

### Axiom 1 — Primitive

**Plain English.** (I, R) is the atom. Everything 8OS manages — specs, code, tests, decisions, prompts, training data — is either an (I, R) pair or a structured collection of them.

**Formal statement.** The atomic unit of 8OS is an (Intention, Resolution) pair. Every artifact the kernel manages — ADRs, specs, code modules, tests, research notes, prompts, training datasets, configuration values — is either an (I, R) pair or a structured collection of (I, R) pairs.

**Compositional role.** Structural. Says what the unit is.

---

### Axiom 2 — Fractal

**Plain English.** Every (I, R) decomposes into more (I, R) until it bottoms out at a bridge to the outside.

**Formal statement.** Every (I, R) is itself a graph of (I, R) pairs. The graph can be collapsed to treat the node as opaque or expanded to reveal its constituent structure. Recursion continues until the graph bottoms out at a resolver call to the outside (per axiom 0).

**Compositional role.** Structural. Says how units nest.

---

### Axiom 3 — Bounded Propagation

**Plain English.** Resolutions affect a finite, scope-bounded reach. A change here doesn't ripple everywhere; it ripples to its actual blast radius.

**Formal statement.** Consequential reach is finite and locally computable. From any (I, R) node, the kernel can determine the set of nodes whose validity depends on this node's resolution without enumerating the entire graph. Scope-bounded propagation with explicit visibility rules governs how resolutions affect the graph.

**Compositional role.** Structural. Says how units propagate.

---

### Axiom 4 — Temporal Validity

**Plain English.** Resolutions decay. Time is a first-class kernel concern, not something layered on top.

**Formal statement.** Resolutions decay through three mechanisms: upstream change (a dependency resolved differently), environment drift (the outside reality changed without the graph noticing), or explicit expiration (a `revisit_when` clause fired). Surrogates have a special form of decay: the outside reality they approximate may drift while their internal logic stays frozen. The kernel tracks `resolved_at`, `valid_through`, and `revalidate_trigger` for every (I, R).

**Compositional role.** Dynamic. Says how units age.

---

### Axiom 5 — Resolver Characterization

**Plain English.** Every resolver has a cost (Clock, Coin, Carbon) and a capability (σ, π, α, ρ), per domain. Picking a resolver is a fitness function over both, measured empirically and refined as we learn what resolvers actually do.

**Formal statement.** Every resolver has two vectors:

- **Cost vector** measured in Clock, Coin, Carbon — what the resolver consumes per invocation.
- **Capability vector** measured in σ (Quality), π (Preference), α (Autonomy), ρ (Reliability) — what the resolver brings to a given domain.

Both vectors are domain-specific. Resolver selection is a fitness function over both vectors, weighted by intention demands. Both vectors are measured empirically through the resolver's actual operation and refined continuously.

**Compositional role.** Operational. Says who picks resolvers.

---

### Axiom 6 — Provenance and Authority

**Plain English.** Every (I, R) records who produced it and with what standing. Authority comes from provenance and decides override behavior, conflict resolution, and trust.

**Formal statement.** Every (I, R) has explicit provenance: the record of who or what produced this resolution and with what standing. Provenance includes whether the resolution came from inside (a recursive (I, R) graph) or from outside (a bridge), and if outside, what the bridge was. Authority — derived from provenance — determines override behavior, conflict resolution, and trust weighting.

The kernel recognizes a hierarchy of authority:

- **Hard constraints** from authoritative sources (regulatory frameworks, foundational decisions, community-consensus invariants) override all other resolutions in their scope.
- **Convention parameters** from contributors are defaults that may be overridden with documented reason.
- **Uncalibrated outputs** from agents have lowest authority and require validation before binding downstream resolutions.

**Compositional role.** Operational. Says who authorizes resolutions.

---

### Axiom 7 — Surrogate Substitution

**Plain English.** The kernel can manufacture learned approximations of resolvers from operational history. What was outside becomes inside. The boundary moves inward over time. Mature kernels have small boundaries; new kernels have huge ones.

**Formal statement.** Resolvers continuously generate training data through normal operation, per the empirical refinement clause of axiom 5 and the ABCDEFG discipline. When sufficient operational history exists, the kernel can manufacture surrogate resolvers — typically learned models — that approximate an original resolver's input-output behavior at substantially lower cost. Surrogates enter the resolver pool as new options, characterized by their own (cost, capability) vectors and provenance, and subject to all the same selection mechanics as native resolvers.

Surrogate creation is the operation that moves the boundary inward (per axiom 0). What was previously an outside-call becomes an internal computation. The kernel's resolver inventory is therefore *generative* over time, not fixed at design.

**Compositional role.** Generative. Says how the kernel grows.

---

### Axiom 8 — Reflexivity

**Plain English.** The kernel does not exempt itself. Every claim the kernel makes about its own state — what it knows, what it has measured, what policies are active, what indexes it has regenerated — is an (I, R) on its own graph, subject to provenance, decay, propagation, and authority on the same terms as user content.

**Formal statement.** Every claim the kernel makes about its own state is itself an (I, R) record, subject to all the other axioms. The kernel's self-description — its inventory of resolvers, its capability characterizations, its policy declarations, its surrogate validations, its index regenerations, its bootstrap vendoring — is on the kernel's own graph, not in a privileged register exempt from kernel discipline. Authority over kernel self-claims follows axiom 6's hierarchy. Decay of kernel self-claims follows axiom 4. Propagation of kernel self-claims follows axiom 3. Provenance of kernel self-claims follows axiom 6.

**Compositional role.** Reflexive. Says how the kernel relates to itself.

**Two structural carve-outs** (per kernel spec v0.2 §"Axiom 8 — Reflexivity"): bootstrap (`kernel.init`) and policy-evaluation cache (`op_pipeline._author_policy_evaluation`). Both bypass `kernel.ir.new`'s validation pipeline for principled reasons (validation cannot precede the records that define the rules; recursion-avoidance for the policy-evaluation phase) while preserving (I, R) shape, hard authority, `authored_via: kernel.self`, atomic commit, and tier-3 event emission. Carve-outs are extensions of axiom 8's discipline, not exceptions to it.

---

## How the nine compose

Six-bucket distillation, locked language from the v0.2 spec:

- **Axiom 0** is foundational cosmology — there is an inside and an outside.
- **Axioms 1–3** are structural — what an (I, R) is, how it nests, how it propagates.
- **Axiom 4** is dynamic — how (I, R)s age.
- **Axioms 5–6** are operational — who picks resolvers, who authorizes resolutions.
- **Axiom 7** is generative — how the kernel grows its own resolver pool.
- **Axiom 8** is reflexive — how the kernel relates to itself.

---

## The lifecycle in one sentence

The whole architecture, condensed to a single sentence (extended from the v0.1 spec's "How the eight axioms compose" section to include axiom 8):

> A unit of knowledge in 8OS comes into being (1, 6), nests with other knowledge (2, 3), ages and may decay (4), is resolved by mechanisms with measurable cost and capability (5), has provenance that governs its standing (6), and the mechanisms that resolve it can themselves be replaced by learned approximations over time (7) — all within a kernel that recognizes its own boundary with an outside reality (0) and applies its own axioms to itself (8).

---

## Usage discipline for public-facing writing

- Open with plain English. Name the formal term once for retrieval. Carry the concept forward, not the term.
- The lifecycle sentence is publish-ready. Use it as the structural summary when one paragraph has to cover the whole.
- The six-bucket compositional distillation (cosmology / structural / dynamic / operational / generative / reflexive) is locked language. Don't paraphrase it.
- Plain-English versions are shorter than the formal versions on purpose. Don't expand them when transferring to public artifacts.
- Reach is the right public framing for what 8OS is *for*; (I, R) is the right structural framing for what 8OS *is*. They're complementary, not competing.

---

*End of capture. This document holds the rediscovered language so it doesn't disperse again. Source: 8OS-KERNEL-SPEC v0.1.0 (formal statements), 8OS - Block 0 conversation (derivation), 8OS - chat 3 (review register), 8OS conversation arc review (ELI5 register), 8OS - Chat 11 (this rediscovery).*
