---
prism-ir-spec-version: 1.1.0
status: Public
supersedes: PRISM-IR v1.0.0
breaking_changes: none
published_by: DEIA Solutions
repository: github.com/deiasolutions/prism-ir
license: Apache-2.0 (spec) / CC BY 4.0 (documentation)
authored_on: 2026-04-26
revisit_when: 8OS kernel ABI changes in a way that affects projection contracts, or a domain need surfaces that requires breaking changes (which would be v2.0.0, not v1.2)
---

# PRISM-IR Specification v1.1

**PRISM** = Process Representation, Intent Simulation & Manifestation
**PRISM-IR** = the Intermediate Representation of the PRISM spec

**Version:** 1.1.0
**Status:** Public
**Supersedes:** v1.0.0 (additively — no breaking changes)
**Published by:** DEIA Solutions / deiasolutions.com
**Repository:** github.com/deiasolutions/prism-ir

---

## What Changed in v1.1

v1.1 is **additive and clarifying**. Every PRISM-IR file valid under v1.0.0 is valid under v1.1 without modification. Breaking changes will not appear until v2.0.0.

The amendments fall into four areas:

1. **8OS compatibility.** PRISM-IR can now be hosted as an 8OS projection type — a specific shape of (Intention, Resolution) pair within the 8OS kernel — without modifying its core schema. This is captured through optional frontmatter extensions and three named conformance levels.

2. **Round-trip framing.** v1.0.0 stated the round-trip exists "not for human readability." That framing is corrected. The round-trip is a mechanical correctness test that produces an artifact LLMs use for fidelity verification; the same artifact is *available* for human intent confirmation when a runtime or process chooses to use it that way. The mechanical contract is unchanged; the framing no longer excludes uses that have proven valuable in practice.

3. **Alterverse storage clarification.** v1.0.0 described the Alterverse as the tree of all timelines. v1.1 clarifies that the Alterverse is a *projection* over an underlying append-only event store. When PRISM-IR is hosted on 8OS, that store is the kernel's tier 3 event ledger filtered by flow identity. Standalone runtimes may implement the store however they choose; conforming runtimes must guarantee that no branch is ever deleted.

4. **Identity discipline.** When a PRISM-IR file is hosted as an 8OS projection, the PRISM-IR top-level `id` field and the 8OS frontmatter `id` field MUST match. This prevents identity drift between the two views of the same artifact.

Everything else in v1.0.0 is preserved verbatim.

---

## What Is PRISM-IR?

PRISM-IR is a domain-agnostic intermediate representation for describing any process — simulated, executed, or hybrid. It is the contract between human intent and machine execution, written and read by LLMs.

Humans describe processes in plain English. LLMs translate that English into PRISM-IR. Runtimes execute the IR. LLMs can reconstruct the English from the IR at any time. Humans never need to read or write YAML.

An **Intermediate Representation (IR)** is a normalized internal form that sits between input (English, BPMN, L-systems, etc.) and execution. It is the translation layer that lets one spec run four different ways.

> "If a thing can be described in words, we can simulate it with an LLM, and operationalize it with Operators."

PRISM-IR is not a programming language. It is not a workflow engine. It is a specification format authored by LLMs, executed by conforming runtimes, and readable by any LLM at any time.

---

## Conformance Levels

v1.1 introduces three named conformance levels. Each level is a strict superset of the level below it. A runtime declares which level it implements; a PRISM-IR file declares which level it requires.

### Level 0 — Standalone PRISM-IR

The full v1.0.0 contract. A runtime at Level 0 reads `.prism.md` files with `prism: my-flow / version: 1.x.0` frontmatter, executes the body schema, supports the four execution modes (simulation, production, hybrid, optimization), and emits results to whatever event store the runtime provides.

Level 0 runtimes do not require 8OS. They do not require the kernel. They do not require any specific event-store implementation. They are free to layer their own provenance, identity, and authority disciplines on top.

**A Level 0 runtime is a complete, standards-conforming PRISM-IR runtime.** Nothing in v1.1 obligates a Level 0 runtime to adopt 8OS.

### Level 1 — 8OS-hosted PRISM-IR

A Level 1 runtime hosts PRISM-IR files as 8OS projection types. The PRISM-IR file becomes one (Intention, Resolution) record inside an 8OS kernel-managed graph. The Intention is the process flow expressed in PRISM-IR. The Resolution is the simulation trace, execution trace, or both.

Level 1 adds:

- **Required frontmatter extensions** (see "8OS-Compatible Frontmatter" below).
- **Identity discipline.** The PRISM-IR `id` and the 8OS `id` MUST match.
- **Tier-3 event emission.** Every node execution, branch creation, phase boundary crossing, and metric update is emitted as a tier 3 event in the 8OS kernel. The Alterverse is then a query over those events filtered by flow identity.
- **Provenance and authority** per 8OS axiom 6. Operators are 8OS resolvers, characterized by cost (Clock, Coin, Carbon) and capability (σ, π, α, ρ) vectors.
- **Bridge declarations.** External calls (LLM APIs, simulation engines, optimization solvers, human reviewers) are declared as bridges per 8OS axiom 0.

Level 1 runtimes are also Level 0 runtimes. Any Level 0 PRISM-IR file is a valid Level 1 file once the additional frontmatter is supplied.

### Level 2 — 8OS with surrogate substitution

A Level 2 runtime additionally implements 8OS axiom 7: surrogate substitution. Resolvers used during execution can be replaced over time with learned surrogates trained on the tier 3 event corpus. PRISM-IR's `surrogates` block, present since v1.0.0, becomes operationally meaningful at this level — a surrogate registered through the kernel's surrogate lineage tracking can substitute for the resolver it approximates with full provenance.

Level 2 runtimes are also Level 1 runtimes. Level 2 is the level at which the kernel's "boundary moves inward over time" property becomes visible to PRISM-IR users.

---

## 8OS-Compatible Frontmatter (Level 1 and above)

A v1.0.0 PRISM-IR file uses minimal frontmatter:

```yaml
---
prism: my-flow
version: 1.0.0
---
```

This remains valid at Level 0.

A Level 1 PRISM-IR file adds the 8OS-required frontmatter fields. The minimal Level 1 frontmatter is:

```yaml
---
# v1.0.0 fields (preserved)
prism: my-flow
version: 1.1.0

# 8OS Block 1 frontmatter (axiom 1)
id: my-flow                          # MUST match the top-level `id` in the PRISM-IR body
kind: ir-node                        # constant for all 8OS-hosted (I, R) records
tier: 1                              # 1 = user-authored content
projection_types: [prism-ir]         # declares this (I, R) as a PRISM-IR projection

# 8OS Block 1 frontmatter (axiom 2)
collapsed_summary: "Approve loans through risk + parallel review"  # one sentence
expanded_into: null
parent: null

# 8OS Block 1 frontmatter (axiom 3)
scope: lending                       # references ir/<scope>/_scope.yml
depends_on: []
visible_to: [lending]

# 8OS Block 1 frontmatter (axiom 4)
resolved_at: null
valid_through: null
revalidate_trigger: null
status: open                         # open | resolved | superseded | stale

# 8OS Block 1 frontmatter (axiom 5)
resolver: null                       # populated when resolved
resolution_event: null

# 8OS Block 1 frontmatter (axiom 6)
authored_by: q88n
authored_on: 2026-04-26T10:30:00Z
authority_level: convention          # hard | convention | uncalibrated
bridge_type: null
supersedes: null
superseded_by: null

# 8OS Block 1 frontmatter (axiom 7, optional)
surrogate_of: null
---
```

The body of the file remains the v1.0.0 PRISM-IR YAML schema, unchanged.

### Identity discipline

When hosted at Level 1 or above:

- The 8OS frontmatter `id` field and the PRISM-IR top-level `id` field MUST match exactly.
- Renaming requires a supersession event in the kernel — a new (I, R) is created with the new ID and `supersedes: <old-id>`. The old (I, R) gets `superseded_by: <new-id>`. Both records are preserved.
- Forking (creating an Alterverse branch with structural divergence) creates a new (I, R) with a new ID and `parent: <original-id>`. The original is unchanged.

### Authority levels

PRISM-IR processes hosted on 8OS inherit the kernel's three-tier authority model per axiom 6:

- **`authority_level: hard`** — regulatory or foundational processes that override conflicting resolutions in their scope. Example: a compliance-mandated approval flow.
- **`authority_level: convention`** — default for most authored processes. Defaults that may be overridden with documented reason.
- **`authority_level: uncalibrated`** — LLM-generated processes pending human or empirical validation.

### Operators as resolvers

PRISM-IR's `op:` field declares the operator type for a node (`human`, `llm`, `api`, `script`). At Level 1, each operator binding resolves through the 8OS resolver registry:

```yaml
# Level 0 / v1.0.0 — operator declared inline
nodes:
  - id: risk_assessment
    t: task
    o: { op: llm, model: claude-sonnet-4-7 }

# Level 1 — operator references registered 8OS resolver
nodes:
  - id: risk_assessment
    t: task
    o: { op: llm, resolver: claude-sonnet-4-7 }
```

The two forms are equivalent in intent. The Level 1 form requires that `claude-sonnet-4-7` exists as a registered resolver in `.8os/resolvers/` with declared cost and capability vectors. This makes resolver selection, fitness scoring, and surrogate substitution possible at runtime.

### Tier 3 event emission

A Level 1 runtime emits an 8OS tier 3 event for every consequential PRISM-IR runtime occurrence. The minimum event set:

- **Token created** (entity arrival)
- **Node entered**
- **Node exited** (with outcome: completed / failed / timed out)
- **Edge taken** (which branch on a decision)
- **Branch forked** (Alterverse branch creation)
- **Phase boundary crossed** (metamorphosis event)
- **Metric updated**

Each event carries the cost vector for that step (Clock, Coin, Carbon) so the kernel can aggregate costs across the flow. Events are written through the kernel's standard `kernel.ir.resolve` and equivalent operations. The PRISM-IR runtime does not need to know the on-disk event format; it calls the kernel and the kernel persists.

---

## The Round-Trip Guarantee (clarified)

English → IR → English. If the round-trip loses meaning, the IR is wrong.

The round-trip is a **mechanical correctness test for the IR**. An LLM receiving a PRISM-IR file MUST be able to reconstruct the original intent accurately, without hallucination or drift. This is the spec-level requirement and it is unchanged from v1.0.0.

The artifact produced by the round-trip — the regenerated English — has two consumers:

1. **LLMs** use it to verify fidelity, typically through embedding similarity or LLM-as-judge comparison against the original English. This is the v1.0.0 use.

2. **Humans** may optionally read it to confirm that the IR captures their intent. Runtimes and processes may use this regenerated English as an intent-confirmation gate before allowing a flow to proceed to execution. This is **not required by the spec**; it is a discipline that runtimes layer on top.

The v1.0.0 statement "this guarantee exists not for human readability" is corrected. The guarantee exists for mechanical fidelity. The artifact it produces is available for whatever verification a runtime or process chooses to perform — LLM-driven, human-driven, or both.

The mechanical contract is unchanged: the round-trip MUST preserve meaning. How the result is used to verify that is a runtime concern, not a spec concern.

---

## The Alterverse (clarified)

The Alterverse is the tree of all timelines: every simulation branch, every production run, every counterfactual. Nothing is deleted. Every path is queryable.

v1.1 clarifies the storage relationship:

The Alterverse is a **projection over an append-only event store**. It is not itself a storage system. The event store is the source of truth; the Alterverse is the user-facing view that organizes events into a navigable tree of timelines.

- **At Level 0** (standalone), the event store is whatever the runtime provides. Conforming runtimes guarantee append-only semantics and that no branch is ever deleted.
- **At Level 1** (8OS-hosted), the event store is the 8OS tier 3 event ledger filtered by flow identity. The Alterverse for a flow is the set of tier 3 events whose `flow_id` matches the flow, organized into a branch tree by their `branch_id` and `parent_branch_id` fields.
- **At Level 2** (8OS with surrogates), the same Alterverse query operates over events from both real-resolver runs and surrogate-resolver runs. Surrogate provenance is preserved per axiom 7, so a query can filter to "real branches only" or include surrogate-generated branches with their lineage clearly marked.

This consolidates what could have been two storage stories into one. Standalone PRISM-IR runtimes implement their own store; 8OS-hosted PRISM-IR runtimes inherit the kernel's store. The Alterverse semantics are identical at both levels.

---

## What Is Preserved Verbatim From v1.0.0

The following sections of v1.0.0 are unchanged in v1.1 and SHOULD be considered the canonical text. They are referenced here rather than reproduced to keep this document focused on what changed:

- **Who Writes PRISM-IR** — humans write English, LLMs write IR, runtimes execute, LLMs reconstruct English on demand.
- **Core Thesis** — one PRISM-IR file, four execution modes (Simulation, Production, Hybrid, Optimization).
- **Key Concepts (other than the Round-Trip Guarantee, which is amended above)** — Intention, Intermediate Representation, Alterverse (now clarified above as a projection).
- **File Format** — `.prism.md` extension, YAML frontmatter, YAML body.
- **Top-Level Schema** — `v`, `id`, `name`, `domain`, `intention`, `failure_tolerance`, `constraints`, `vocabulary`, `entities`, `events`, `generators`, `queues`, `resources`, `groups`, `surrogates`, `nodes`, `edges`, `phase_boundaries`, `metrics`, `params`.
- **Intention and Constraints** — single-sentence intention; constraints with sla/fail/priority; failure_tolerance grammar; CSS-style cascade through flow → groups → nodes.
- **Expression Language** — dot notation, single-quoted strings, YAML-native booleans/null, native time literals; collection functions (`where`, `count`, `sum`, etc.); time-series functions (`rate`, `moving_avg`, etc.).
- **Phase Boundaries (Metamorphosis)** — first-class construct in the Alterverse; `from` / `to` / `persist` / `migration` semantics.
- **Node Types and Edge Schema** — `start`, `end`, `task`, `decision`, `parallel_fork`, `join`, etc., with the full edge schema (`s`, `t`, `c`, `fork`, etc.).
- **Operator Schemas** — human (with tier), llm (with model), api (with endpoint), script (with code reference).
- **Resource Dispatch Modes** — pool, exclusive, shared, the dispatch semantics.
- **Surrogate Bindings Schema** — the `surrogates:` block and how surrogate models replace simulation at distance.
- **Key Principles** — all nine principles from v1.0.0, with one amendment: principle 7 ("English → IR → English. If the round-trip loses meaning, the IR is wrong. This is LLM-to-LLM fidelity, not human readability.") — the second sentence is removed; the first remains. The full corrected framing lives in the "Round-Trip Guarantee (clarified)" section above.

Implementers may reference v1.0.0 directly for the verbatim text of the preserved sections. v1.1 does not republish content it does not change.

---

## Migration From v1.0.0

A PRISM-IR file or runtime moving from v1.0.0 to v1.1:

1. **No mandatory action at Level 0.** v1.0.0 files remain valid Level 0 v1.1 files. Update the `version: 1.0.0` field to `version: 1.1.0` if and when convenient; this is informational, not required.

2. **To adopt Level 1**, add the 8OS frontmatter block to existing files. The PRISM-IR `id` becomes the 8OS `id`. Required fields (`tier`, `scope`, `authored_by`, `authored_on`, `authority_level`, etc.) must be supplied. The body remains untouched.

3. **To adopt Level 2**, register surrogate resolvers through 8OS per axiom 7 and reference them in the existing `surrogates:` block. The format of the block is unchanged; the registration discipline is added.

The discipline is: pick the conformance level that matches your runtime's needs, declare it explicitly in the file, and supply the required frontmatter for that level.

---

## Conformance Declaration

A PRISM-IR file at v1.1 may declare its required conformance level explicitly:

```yaml
---
prism: my-flow
version: 1.1.0
conformance: level-1
# ... rest of frontmatter
---
```

Valid values: `level-0`, `level-1`, `level-2`. If absent, the level is inferred from frontmatter shape: minimal frontmatter implies Level 0, presence of 8OS frontmatter fields implies Level 1, presence of registered surrogates implies Level 2.

A runtime SHOULD refuse to execute a file whose declared conformance level exceeds the runtime's supported level. A runtime MAY execute a file whose declared level is lower than the runtime's supported level (a Level 2 runtime can run Level 0 files).

---

## References

- PRISM-IR v1.0.0 (the base spec this document amends)
- 8OS Kernel Specification v0.1 — the eight-axiom kernel ABI that Level 1 and above conformance targets
- 8OS Block 1 Specification v0.1 — the on-disk representation and SDK contract
- Van der Aalst Workflow Patterns: https://www.workflowpatterns.com/
- BPMN 2.0: OMG standard
- Erlang OTP Supervision Trees: failure policy foundations
- Petri Net formalism: token/place semantics
- SimPy: generator and arrival pattern conventions
- L-Systems: grammar-based growth (biological domain foundation)

---

*PRISM-IR v1.1 — DEIA Solutions — deiasolutions.com*
*"Describe your process once. Simulate your intent. Manifest it."*
*v1.1 amendments: 8OS compatibility, round-trip framing, Alterverse storage clarification, identity discipline. No breaking changes.*
