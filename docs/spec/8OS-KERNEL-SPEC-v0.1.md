---
id: 8OS-KERNEL-SPEC
version: 0.1.0
status: accepted
kind: foundational
scope: project
domain: 8os/kernel
codename: ZORTZI
authored_by: Q88N + Claude (Block 0 derivation)
authored_on: 2026-04-26
supersedes: null
superseded_by: null
depends_on: null
revisit_when: implementation surfaces a contradiction with any axiom
provenance: derivation captured in conversation "8OS - Block 0"
---

# 8OS Kernel Specification v0.1

## What this document is

This is the foundational specification for **8OS** (codename **ZORTZI**), the kernel of an
intention-driven operating system for software product development. It defines the eight
axioms that constitute the kernel ABI. Everything built on 8OS — ADR formats, spec templates,
agent contracts, slash commands, project scaffolding — must respect these axioms. Anything
that respects them targets the stable kernel; anything that violates them breaks the
contract and should be rejected.

This is not a tool. It is not a documentation system. It is a substrate that hosts software
product development as a first-class executable workload. FBB (Family Bond Bot, including
the Counsel Edition layer) is the first user-space program targeted at this kernel. The next
project is the second. Both inherit the kernel's properties without rewriting them.

The kernel is named **8OS** because there are eight axioms and because ZORTZI is Basque for
"eight" — the symbol of infinity upright. The eight axioms are numbered 0 through 7. Axiom 0
is foundational cosmology. Axioms 1 through 7 describe the kernel's internal physics.
Together they form a complete, finite, implementable substrate that lives inside an infinite
world.

## Glossary of primitive terms

- **(I, R) pair**: An (Intention, Resolution) pair. The atomic unit of the kernel.
- **Resolver**: A mechanism that produces a Resolution for a given Intention. May be a
  deterministic computation, a human, an LLM, an empirical test, a simulation, a retrieval,
  a learned surrogate, or any other mechanism that can answer.
- **Inside / Outside**: Inside is recursive (every (I, R) decomposes into more (I, R)).
  Outside is opaque (the kernel observes it through bridges but cannot decompose it).
- **Bridge**: A resolver that crosses the inside/outside boundary.
- **Surrogate**: A resolver that lives entirely inside, learned from operational history of
  another resolver — typically one that previously bridged outside.
- **Scope**: A frame of consequential reach within the (I, R) graph. Resolutions propagate
  within their scope; outside their scope they are invisible.
- **Cost vector**: The 3Cs — Clock, Coin, Carbon — describing what a resolver consumes.
- **Capability vector**: The 4-vector — σ (Quality), π (Preference), α (Autonomy), ρ
  (Reliability) — describing what a resolver brings, per domain.
- **Provenance**: The record of who or what produced a resolution and with what standing.
- **ABCDEFG**: Always Be Collecting Data Everywhere For GenAI. The discipline that makes
  axiom 7 possible.

---

## Axiom 0 — Inside and Outside

**Statement**

The kernel exists within a larger reality it cannot fully contain. Inside the kernel is
recursive: every (I, R) decomposes into more (I, R). Outside the kernel is not: there is
something there that the kernel observes through bridges but cannot decompose. Resolvers are
the bridges between inside and outside. The kernel's growth over time is the inward movement
of the boundary as outside-calls are progressively internalized through surrogate training,
captured decisions, and accreted patterns.

**Why it is axiomatic**

Without this axiom, the recursion in axiom 2 has no terminator and the kernel describes a
closed mathematical system with no contact with reality. Axiom 0 names where the recursion
stops and what it stops at: the boundary to a world the kernel observes but does not own.

**Implications for the kernel**

- The kernel must distinguish between (I, R) nodes that resolve through internal recursion
  and (I, R) nodes that resolve through bridges to the outside.
- The kernel must explicitly type and track its bridges. A bridge to the Anthropic API is a
  different thing from a bridge to a user, which is different from a bridge to a physics
  simulation, which is different from a bridge to a CPU instruction.
- The kernel's value compounds because it eats its own boundary. Day one, the boundary is
  everywhere. As the project runs, more accumulates inside. Mature kernels have small
  boundaries; new kernels have huge boundaries.
- The kernel is metabolic, not static. It ingests the outside through bridges, processes
  internally, and excretes new internal capabilities through surrogates and captured
  decisions.

---

## Axiom 1 — Primitive

**Statement**

The atomic unit of 8OS is an (Intention, Resolution) pair. Every artifact the kernel
manages — ADRs, specs, code modules, tests, research notes, prompts, training datasets,
configuration values — is either an (I, R) pair or a structured collection of (I, R) pairs.

**Why it is axiomatic**

Without a single primitive, the kernel is forced to handle each artifact type as a special
case. With a single primitive, all artifacts share the same instruction set: create,
resolve, query, supersede, propagate. Higher-level artifact types (ADRs, specs, etc.) are
syntactic sugar over (I, R) pairs.

**Implications for the kernel**

- The kernel's storage layer is uniform: every artifact is stored as an (I, R) record with
  consistent metadata (provenance, scope, cost, capability, temporal validity, status).
- Higher-level constructs (ADRs, specs, tests) are *projections* of (I, R) pairs, not
  separate types. An ADR is an (I, R) where the resolver is "human + thread" and the
  resolution is a written decision. A test is an (I, R) where the resolver is "automated
  execution" and the resolution is pass/fail.
- New artifact types can be added by defining new projections without changing the kernel.

---

## Axiom 2 — Fractal

**Statement**

Every (I, R) is itself a graph of (I, R) pairs. The graph can be collapsed to treat the
node as opaque or expanded to reveal its constituent structure. Recursion continues until
the graph bottoms out at a resolver call to the outside (per axiom 0).

**Why it is axiomatic**

Real systems span many scales. An atom is opaque in chemistry and structured in nuclear
physics. An LLM call is opaque to a feature spec and structured to the prompt engineer. The
kernel must support depth-shifting as a first-class operation so that a single (I, R) can be
opaque or transparent depending on the observer's need.

**Implications for the kernel**

- The kernel must support `collapse(node)` and `expand(node)` as efficient operations,
  ideally O(1) from the perspective of the querying agent.
- Every (I, R) carries metadata sufficient to support both treatments — a summary suitable
  for opaque use and a sub-graph reference suitable for expansion.
- The kernel's queries must be depth-aware: an agent can request resolutions at a chosen
  depth and the kernel returns the appropriate slice.

---

## Axiom 3 — Bounded Propagation

**Statement**

Consequential reach is finite and locally computable. From any (I, R) node, the kernel can
determine the set of nodes whose validity depends on this node's resolution without
enumerating the entire graph. Scope-bounded propagation with explicit visibility rules
governs how resolutions affect the graph.

**Why it is axiomatic**

Without bounded propagation, every change to any node would require revalidating the entire
graph. With it, changes propagate only to their actual blast radius, making the kernel
computationally tractable on graphs of arbitrary size. This is the property that makes
incremental compilation, dependency analysis, and selective revalidation possible.

**Implications for the kernel**

- Every (I, R) declares its scope: which subgraph of the kernel can see and depend on it.
- Every (I, R) has explicit dependencies: which other (I, R)s its resolution rests on.
- The kernel computes consequential reach as a graph traversal bounded by scope and
  dependency edges, not by enumeration of all nodes.
- Scope is hierarchical: project > domain > module > feature. Resolutions at higher scopes
  apply to all subscopes; resolutions at lower scopes apply only locally.

---

## Axiom 4 — Temporal Validity

**Statement**

Resolutions decay through three mechanisms: upstream change (a dependency resolved
differently), environment drift (the outside reality changed without the graph noticing),
or explicit expiration (a `revisit_when` clause fired). Surrogates have a special form of
decay: the outside reality they approximate may drift while their internal logic stays
frozen. The kernel tracks `resolved_at`, `valid_through`, and `revalidate_trigger` for
every (I, R).

**Why it is axiomatic**

A static graph implicitly assumes resolutions are timeless. Reality is not. The kernel that
lives for a year without modeling time will rot — every stale resolution becomes a silent
trap for downstream reasoning. Time must be a first-class kernel concern, not a property
projects layer on top.

**Implications for the kernel**

- Every resolution carries `resolved_at` (when it was produced).
- Resolutions may carry `valid_through` (a time horizon after which they should be
  revalidated) and/or `revalidate_trigger` (an event or condition that re-opens the
  question).
- The kernel can answer queries with a `valid_at` filter — "what bound this scope as of
  date X" — and can surface stale resolutions proactively.
- Surrogate resolvers carry an additional metadata field: the resolver they were trained
  to approximate, and the `outside_drift_estimate` that flags them as potentially stale
  when the underlying reality is known to have changed.

---

## Axiom 5 — Resolver Characterization

**Statement**

Every resolver has two vectors:

- **Cost vector** measured in **Clock, Coin, Carbon** — what the resolver consumes per
  invocation.
- **Capability vector** measured in **σ (Quality), π (Preference), α (Autonomy), ρ
  (Reliability)** — what the resolver brings to a given domain.

Both vectors are domain-specific. A given resolver may have different (σ, π, α, ρ) for code
generation vs. legal reasoning vs. emotional support. Resolver selection is a fitness
function over both vectors, weighted by intention demands. Both vectors are measured
empirically through the resolver's actual operation and refined continuously.

**Why it is axiomatic**

Without explicit resolver characterization, the kernel cannot make principled choices about
which resolver to invoke. It would either lock to a single resolver (wasting capacity on
trivial questions, failing on hard ones) or pick randomly (producing unreliable outputs).
With explicit characterization, the kernel can match resolvers to intentions deterministically
and improve the matching over time as it learns each resolver's actual behavior.

**Implications for the kernel**

- Every resolver is registered with declared cost and capability vectors per domain.
- Every resolution event captures the actual cost consumed and (where measurable) a
  retrospective capability assessment.
- The kernel maintains a learned model of each resolver's vectors that updates as new
  evidence arrives.
- Resolver selection is itself an (I, R) that the kernel resolves — meaning the kernel can
  apply axioms 1–4 to its own selection logic recursively.

---

## Axiom 6 — Provenance and Authority

**Statement**

Every (I, R) has explicit provenance: the record of who or what produced this resolution
and with what standing. Provenance includes whether the resolution came from inside (a
recursive (I, R) graph) or from outside (a bridge), and if outside, what the bridge was.
Authority — derived from provenance — determines override behavior, conflict resolution,
and trust weighting.

The kernel recognizes a hierarchy of authority:

- **Hard constraints** from authoritative sources (regulatory frameworks, foundational
  decisions, community-consensus invariants) override all other resolutions in their scope.
- **Convention parameters** from contributors are defaults that may be overridden with
  documented reason.
- **Uncalibrated outputs** from agents have lowest authority and require validation before
  binding downstream resolutions.

**Why it is axiomatic**

Resolutions have no value if their source is unknown. Two resolutions that say the same
thing have very different weight if one came from a regulator and the other from an LLM
hallucination. Without provenance, the kernel cannot correctly resolve conflicts, cannot
honor regulatory boundaries, and cannot distinguish "we decided this carefully" from
"someone wrote this once." Provenance is the foundation of trust in the kernel.

**Implications for the kernel**

- Every (I, R) record includes `authored_by`, `authored_on`, `authority_level`, and
  `bridge_type` (if applicable).
- Conflict resolution between two competing resolutions in the same scope is governed by
  authority level first, then by recency, then by other rules the kernel may define.
- Surrogates carry the provenance of the resolver they replaced *and* the provenance of
  the surrogate's own training process. Both are required for downstream auditing.
- The kernel can answer queries with a provenance filter — "show me only resolutions
  authored by humans" or "show me only hard constraints" — to support auditing and
  compliance.

---

## Axiom 7 — Surrogate Substitution

**Statement**

Resolvers continuously generate training data through normal operation, per the empirical
refinement clause of axiom 5 and the ABCDEFG discipline. When sufficient operational
history exists, the kernel can manufacture surrogate resolvers — typically learned models —
that approximate an original resolver's input-output behavior at substantially lower cost.
Surrogates enter the resolver pool as new options, characterized by their own (cost,
capability) vectors and provenance, and subject to all the same selection mechanics as
native resolvers.

Surrogate creation is the operation that moves the boundary inward (per axiom 0). What was
previously an outside-call becomes an internal computation. The kernel's resolver inventory
is therefore *generative* over time, not fixed at design.

**Why it is axiomatic**

Without surrogate substitution, the kernel can only get smarter — better at choosing among
fixed resolvers. With surrogate substitution, the kernel can also get *cheaper and faster*
at executing the same resolutions over time. Today's expensive Sonnet call becomes
tomorrow's cheap learned approximation. The economics of long-running projects shifts
fundamentally when resolvers compound rather than remain static.

This axiom also acknowledges what the other seven do not: that there is an outside (per
axiom 0), and that the kernel's relationship to it is not just observational but
*progressive*. The kernel internalizes the outside over time. This is the mechanism.

**Implications for the kernel**

- The kernel must store every resolution event in a form usable as ML training data:
  consistent input/output schema, context, model identity, prompt shape, evaluation if
  available, full cost vector.
- A surrogate is a new resolver registered with the kernel, with its own vectors. Its
  cost vector is typically much lower than the resolver it replaces; its capability vector
  is initially uncertain and must be measured empirically.
- The kernel must track surrogate lineage: which resolver was approximated, when training
  occurred, what corpus was used, and what the validation results were.
- The kernel can apply surrogate substitution recursively: a surrogate's outputs can
  themselves train further surrogates as the boundary continues to move inward.

---

## How the eight axioms compose

The axioms are not a flat list. They have a structural relationship:

- **Axiom 0** is foundational cosmology — there is an inside and an outside.
- **Axioms 1–3** are structural — what an (I, R) is, how it nests, how it propagates.
- **Axiom 4** is dynamic — how (I, R)s age.
- **Axioms 5–6** are operational — who picks resolvers, who authorizes resolutions.
- **Axiom 7** is generative — how the kernel grows its own resolver pool.

Together they describe a complete lifecycle for a unit of knowledge in 8OS: it comes into
being (1, 6), it nests with other knowledge (2, 3), it ages and may decay (4), it is
resolved by mechanisms with measurable cost and capability (5), it has provenance that
governs its standing (6), and the mechanisms that resolve it can themselves be replaced by
learned approximations over time (7) — all within a kernel that recognizes its own
boundary with an outside reality (0).

## What 8OS is not

To prevent scope creep and over-claiming:

- 8OS is not a programming language. It is the substrate that programming languages can
  target.
- 8OS is not a documentation tool. It manages knowledge of which documentation is one
  projection.
- 8OS is not an LLM framework. LLMs are one type of resolver among many.
- 8OS is not opinionated about cloud architecture, deployment targets, programming
  language choice, database technology, or any other project-level architectural decision.
  Those are values bound to categories at the project level, not properties of the kernel.
- 8OS does not specify file formats, folder structures, or on-disk representation. Those
  are Block 1 derivations from these axioms, not part of the kernel itself.

## Status of this specification

This is **v0.1**. It locks the eight axioms as the kernel ABI. Future versions may refine
the wording but should not add, remove, or reinterpret axioms without an explicit
supersession event. Anything built on top of these axioms — file formats, agent contracts,
templates, slash commands, specific project scaffolding — is downstream of this spec and
may evolve independently.

The next derivation block (Block 1) will specify the **on-disk representation**: the
concrete syntax of the kernel as folders, files, frontmatter schemas, and naming
conventions. Block 1 is constrained by these axioms — it must produce a representation
that supports all eight, and any failure to do so indicates either a flaw in the axioms or
a flaw in the representation, to be resolved by amendment.

## Codename and naming

- **8OS** — the kernel of eight axioms
- **ZORTZI** — Basque for eight; the locked vocabulary term in the DEIA ecosystem
- **Founder OS** — informal descriptor of the broader system 8OS sits inside
- **PRISM-IR** — the related, co-resident IR for simulation; 8OS and PRISM-IR share the
  (I, R) primitive and may be implemented as co-residents on the same substrate

---

*End of specification v0.1. Authored in Block 0. Feeds Block 1.*
