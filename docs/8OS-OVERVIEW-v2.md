---
id: 8OS-OVERVIEW
version: 2.0
status: superseded
kind: entry-point
scope: project
domain: 8os
authored_by: Q88N + Claude
authored_on: 2026-04-28
supersedes: 8OS-OVERVIEW v1.0
superseded_by: 8OS-OVERVIEW v3.0
provenance: written to give a new reader a complete-but-honest picture of 8OS as it stands at the architecture commitment for Block 1 v1.1, including multi-factory primitives, governance, skills, three-cost decomposition, and the storage commitment to DuckDB. Points at canonical specs; does not replace them.
---

> **Superseded by [8OS-OVERVIEW v3.0](8OS-OVERVIEW-v3.md) on 2026-04-29.** Preserved for lineage. v3 resolves v2's eighteenth-op tension (`kernel.outside.http` is plumbing, not an SDK op), reconciles the SCAN cost figure with the SCAN writeup (~$0.04), refreshes the honest-gaps section against v1.1.0-dev.6 (Block 4.7 closed), and replaces v2's SCAN-only empirical-witness section with the demo trio.

# What is 8OS

**8OS is a runtime that executes PRISM-IR programs.**

PRISM-IR is the program — the source language declaring intent and structure. 8OS is the kernel: the substrate the program runs on. The relationship is strictly that of language to runtime. PRISM-IR describes what; 8OS executes how.

This document is an entry point. It is not a spec. It points at the specs, summarizes what they say collectively, and is honest about the gap between architectural commitment and current implementation.

## The four layers

8OS is best understood as four layers, each with characteristic concerns and an explicit cleavage from its neighbors.

**The kernel** is the substrate. It hosts the (Intention, Resolution) graph, enforces invariants and limits, publishes facts, and exposes a small set of primitives. The kernel is opinion-free at the value level: it knows there are cost vectors but doesn't pick currencies; it knows there are authority levels but doesn't define who has authority; it knows there are scopes but doesn't define what scopes mean.

**PRISM-IR** is the language. Programs declare intent, structure, decision flows, parallelism, SLAs, surrogates, generators, and constraints. PRISM-IR is opinion-free at the strategy level: the language declares what; runtimes decide how.

**The factory** is the runtime. It walks PRISM-IR graphs, dispatches resolvers, advances simulation clocks, samples distributions, queues bridge crossings, and chooses execution policy. Different factories make different choices; the kernel hosts the work product of any of them.

**The application** is the composer. It supplies the values the kernel and PRISM-IR leave open: which currencies, which authorities, which scopes, which classifications, which roles, which policies, which skills, what they mean for this domain.

The cleavage is operational: anything that mutually-distrusting factories cannot safely re-implement is kernel; anything declarative about a process is PRISM-IR; anything about how to execute is factory; anything domain-specific is application.

## The eight axioms

The kernel ABI is locked at v0.1 and consists of eight axioms (`docs/spec/8OS-KERNEL-SPEC-v0.1.md`):

0. **Inside / Outside.** The kernel is recursive on the inside; bridges connect to an outside it observes but cannot decompose.
1. **Primitive.** Every artifact is an (Intention, Resolution) pair or a structured collection of them.
2. **Fractal.** Every (I, R) is itself a graph of (I, R)s, expandable or collapsible at any depth.
3. **Bounded propagation.** Consequential reach is finite and locally computable.
4. **Temporal validity.** Resolutions decay. Time is first-class. Records carry `resolved_at`, `valid_through`, and `revalidate_trigger`.
5. **Resolver characterization.** Every resolver carries a cost vector (Clock, Coin, Carbon) and a capability vector (σ Quality, π Preference, α Autonomy, ρ Reliability), per domain.
6. **Provenance and authority.** Every (I, R) records who/what produced it and with what standing.
7. **Surrogate substitution.** Resolvers' operational history can train surrogates that progressively internalize the outside.

The axioms have not changed since v0.1. They will not change without explicit supersession. Everything else in 8OS — representation, operations, projection types, governance, storage backend — is downstream of the axioms and may evolve.

## What the kernel commits to

The kernel has four kinds of responsibilities. The categories matter because they constrain what new primitives can be added principled-ly.

**Invariants** are properties the kernel enforces unconditionally. Identity uniqueness, provenance honesty, scope visibility, authority hierarchy, per-operation atomicity, append-only event ordering, honest cost accounting (including the resolver/kernel/factory cost split on every resolution), honest status enumeration. These cannot be violated; the kernel actively prevents it.

**Limits** are upper bounds enforced against declared budgets. Bridge rate limits, scope cost ceilings, lease TTLs, queue-cutoff times. The kernel rejects operations that would exceed declared limits.

**Facts** are queryable kernel-published state that factories use to make decisions. Tier 3 event ledger as the canonical record of all bridge crossings and kernel ops; resolver capability and cost vectors; declared resolver substitutability; current bridge state derivable from recent events. Without authoritative facts, factories make blind decisions.

**Primitives** are the operations the kernel exposes for factory use. The 17-operation SDK plus the five outside-call/coordination primitives that Block 1 v1.1 introduces.

The kernel does **not** schedule, retry, prioritize, walk graphs, decompose programs, choose substitutes, weight priorities, interpret SLAs, define queue layouts, host observability tooling, define lifecycle UI, tokenize, classify content, moderate content, manage encryption keys, store PII, or commit to any specific value-level meaning. Those concerns belong elsewhere. See the table below.

## What the kernel does not do, and where each concern lives

| Concern | Lives in | Why |
|---|---|---|
| Scheduling | Factory | Different factories make different scheduling choices; the kernel offers atomicity and event ordering. |
| Retry policy | Factory or PRISM-IR | PRISM-IR's `fail` grammar can declare; factories implement. |
| Prioritization weighting | PRISM-IR + Factory | PRISM-IR declares priority on nodes; factory derives an integer to pass to `kernel.bridge.cross`; kernel honors the integer. |
| SLA semantics | **PRISM-IR (must)** | `sla` is a measurement target on a node; runtime decides via decision nodes. Hiding SLA in factory code makes it ungovernable. |
| Substitute selection | PRISM-IR + Factory | PRISM-IR's `surrogates` block declares; factory chooses. |
| Walking strategy | Factory | Different walkers for different graph shapes; not a kernel concern. |
| Decomposition strategy | Factory or PRISM-IR program | A decomposer is a registered resolver; its strategy is the resolver's logic. |
| Decision-and-action separation | **PRISM-IR (must)** | First-class via decision nodes and edge conditions. Factory-internal decisions are un-decomposable, un-auditable, un-surrogateable. |
| Skill manifests | **PRISM-IR (must)** | Skills as PRISM-IR programs are inspectable, auditable, manifest-bounded. Skills as opaque code reproduce the OpenClaw failure mode. |
| Queue layout for factory-local work | Factory | Each factory's internal queue is its own. |
| Observability tooling | Userspace (any layer) | The kernel publishes events; tools consume. Multiple tools possible. |
| Lifecycle UI (Task Manager equivalent) | Userspace tooling | The kernel exposes state; the ecosystem ships viewers. |
| Factory-to-factory coordination beyond leases | Factory or external service | Leases handle the basic mutex; richer patterns are factory-level. |
| Tokenization | Application | TSaaS-style tokenization is application-level. Kernel offers `data_classification` for declarative discipline. |
| Trust & Safety decisions | Application + PRISM-IR | T&S decisions are application policy; PRISM-IR expresses the decision flow; kernel evaluates the policies. |
| Encryption key management | Application | Keys are application infrastructure. |
| PII storage | Application | The kernel doesn't store PII. |
| Authority value definitions | Project | The kernel knows authority levels exist; the project defines who has what. |
| Currency definitions | Application/Project | Clock/Coin/Carbon are vector dimensions; what specific currencies an application accepts is its choice. |
| Scope semantics | Project | The kernel hosts scopes; the project decides what each scope means. |
| Classification meanings | Application | The kernel stores classifications; applications define what specific classifications mean. |
| Role definitions | Project | The kernel knows roles exist; the project defines what each role grants. |
| Policy values | Project + Application | The kernel evaluates policies; the project authors them. |
| Skill semantics | Application | The kernel hosts skills; applications define what skills do. |
| Distribution sampling | Runtime | Generators in PRISM-IR are declarative; runtimes sample. |
| Tick advancement, simulation clocks | Runtime | The kernel uses OS wall-clock; simulation/domain clocks are runtime concerns. |
| Random number generation, replay seeding | Runtime | Determinism is the runtime's responsibility. |
| Alterverse storage | Runtime | The Alterverse is hosted by the runtime in its own store; the kernel hosts a meta-projection naming the store. |
| Wall-clock maintenance | Operating system | The kernel reads OS clock; doesn't run its own. |

The "must" markers indicate architectural commitments — the layer placement is load-bearing for governance, audit, or surrogacy, and the architecture insists on it rather than leaving it to convention.

## The kernel's primitives

The kernel exposes operations through a 17-operation SDK. The wire format is JSON in on stdin, JSON out on stdout, structured errors with stable codes on stderr. No in-process SDK exists by design; conformance lives at the wire boundary.

The 16 operations from v1.0.1-partial are preserved unchanged. Block 1 v1.1 adds:

- `kernel.ir.cancel` — the 17th operation. Marks an (I, R) `status: cancelled`, emits a tier 3 cancellation event, drops pending bridge crossings against the cancelled (I, R) from the queue. Distinct from supersede (which has a replacement) and from stale (which is automatic on `valid_through`).
- `kernel.outside.http` — the first kernel-level outside-call primitive. PRISM-IR bridge programs that hit HTTP endpoints can compose this primitive for governance visibility (URL allowlists, rate limits per destination, payload inspection). Bridges that hit other outside-call shapes use `op: script` to Python, which remains available.

Block 1 v1.1 also adds projection types: `_kernel.lease` (multi-writer coordination), `_kernel.role` and `_kernel.policy` (governance), `_kernel.skill` (skill manifests), `_kernel.policy-evaluation` (cached policy results), and `_simulation.alterverse-store` (meta-projection naming a runtime-hosted Alterverse store).

## Bridges are PRISM-IR programs

Every bridge is a PRISM-IR program. The minimum case is one node — the bridge wraps a Python implementation via `op: script`. The maximum case decomposes the bridge into multiple nodes, each with its own cost declaration and governance handling.

The kernel offers `kernel.outside.http` as the first outside-call primitive. Bridges that hit HTTP can declare it as a leaf node, gaining per-destination policy enforcement, payload-hash recording, and uniform audit. Bridges that need other shapes — long-running subprocess, websockets, custom protocols, email gateways, sensor reads — use `op: script` to Python and accept that governance over those calls is at the script-call granularity rather than per-destination.

This is a deliberate architectural choice. Pure-Python bridges are opaque to governance: the kernel cannot see what URL was hit, what payload was sent, what was returned. PRISM-IR bridges that compose `kernel.outside.http` are transparent at the kernel boundary. The cleavage is opt-in: bridge authors choose how transparent to be by how much they decompose.

The Anthropic bridge, the first real bridge in 8OS, will be reauthored as a PRISM-IR program in Block 4 implementation work. The current binary's `_kernel.bridge` projection (with `implementation:` field pointing at Python) is preserved as a backward-compatible path until then.

## Three cost vectors per resolution

Every resolution event carries three cost vectors, each in the (Clock, Coin, Carbon) shape:

- **`resolver_cost`** — what the resolver itself consumed. Actual thinking time, actual API spend, actual carbon for the work itself. Used by calibration, capability vector updates, and surrogate training. Honest signal of resolver performance.
- **`kernel_cost`** — the kernel binary's contribution. Index updates, event ledger writes, bridge-queue waits inside `kernel.outside.http`, lease arbitration, atomic-commit overhead. Improvements show up by changing the kernel implementation.
- **`factory_cost`** — the factory's contribution. Walker traversal, dispatch decision-making, adapter overhead, retry logic, factory-local queue management. Improvements show up by changing the factory implementation.

The decomposition matters because it localizes muda. A scope with high factory-clock relative to resolver-clock has factory-side overhead worth fixing. A scope with high kernel-clock relative to resolver-clock has kernel-side overhead. *Where the cost is, is where the lever is.* Without three-way decomposition, this is not possible.

Calibration math reads `resolver_cost` only. Surrogate training corpora pull from `resolver_cost` only. Neither is contaminated by either substrate. A surrogate trained on Sonnet learns from Sonnet's actual resolve-time, not from total elapsed including queue wait.

## Multi-factory architecture

The kernel is multi-factory-capable at the architecture level. The reference implementation today is single-writer per process. The gap between architecture and implementation is named explicitly and closed by subsequent implementation blocks.

Multi-factory commitments in Block 1 v1.1:

- **Leases** as a `_kernel.lease` projection type for adversarial-resistant write coordination. Factories acquire leases on scopes or specific (I, R)s; the kernel rejects conflicting writes during the lease's TTL.
- **Bridge queues** internal to `kernel.outside.http`. Multiple factories sharing one credential queue through the kernel. The kernel honors `priority` (an opaque integer the factory derives) and `expires_at` (a queue-cutoff timestamp); factories that miss their `expires_at` window get `EXPIRES_AT_PASSED`.
- **Three-cost decomposition** so that bridge-queue waits are honestly attributed to `kernel_cost`, not contaminated into `resolver_cost`. The kernel does the splitting because the kernel is the one doing the waiting.

The principle: scheduling, prioritization, retry, substitution, and walking strategy are factory concerns. The kernel enforces *limits* (rate limits, budgets, queue cutoffs) and *invariants* (atomicity, append-only ordering, honest cost decomposition); factories make the policy choices.

## Governance: roles, policies, skills

Governance in 8OS is additive over axiom 6 (provenance and authority). Block 1 v1.1 introduces:

**Roles** (`_kernel.role`) bundle named permissions. A role grants its holders specific permission tags. Resolvers and humans hold roles. Operations check role-based permissions before proceeding.

**Policies** (`_kernel.policy`) declare rules about what's permitted. Policies can be predicates ("outbound calls to non-allowlisted domains require role X") or full resolutions ("is this person on the approved senders list" answered by a script, an outside lookup, an LLM, or a human). The kernel evaluates applicable policies before each governance-relevant operation.

**Policy outcomes are richer than allow/deny.** A decision object includes action (allow / deny / transform / defer), modifications (scope restrictions, visibility filters, timing constraints, content transforms), required follow-ups (escalation, review queue insertion), and audit metadata. This supports the full T&S action space — allow with limits, allow with caveats, allow with delay, defer to escalation, decompose-and-partial-action — without baking T&S semantics into the kernel.

**Skills** (`_kernel.skill`) are packaged bundles of (I, R)s. Skills are declarative manifests, not executable instructions. Installing a skill validates the manifest against installation policies, evaluates required authorizations, and writes the bundle's records into the kernel. A skill cannot do more than its manifest declared. Skills are scoped, auditable, and revocable.

This pattern is explicitly different from agent skill systems that fetch remote files and follow them as instructions. The OpenClaw / Moltbook security failures — capabilities loaded by following remote markdown, no manifest discipline, no install-time gate, no runtime boundaries, no clean revocation — are structurally impossible in this architecture because skills are PRISM-IR programs, not fetch-and-execute instructions, and outside-calls are policy-gated regardless of which skill issued them.

## Governance dimensions on outside-calls

Every outside-call records:

- **Direction** — outbound, inbound, or bidirectional.
- **Target category** — another program, local file, network service, person, world.
- **Target identifier** — the URL, file path, person ID, or whatever names the target.
- **Payload-hash** — always recorded. Enables deduplication, drift detection, cache-as-resolver, forensic replay.
- **Optional sidecar payload** — full content stored if policy says to. Default off. Specific scopes or destinations can require sidecar storage via policy.
- **Resolved authorization** — which authorization permitted this call.
- **Cost vectors** — three-way decomposition per the cost-accounting commitment.

This audit trail answers governance questions cleanly: did we ever send raw PII to the outside, what URLs has any factory in this scope hit this week, when the same prompt was sent across time did the responses drift, has this exact payload been crossed before (cache opportunity).

## Time, frames, branches

The kernel uses the operating system's wall-clock for its own timestamps and monotonic-elapsed for cost accounting. The kernel does not maintain its own clock service. Causal ordering across multi-factory deployments is established by dependency edges and event-log sequence, not by timestamp comparison. Wall-clock timestamps are advisory; the OS supplies them; clock skew across writers is the OS's problem.

Beyond wall-clock and monotonic, the kernel hosts arbitrary application time annotations as frontmatter without interpreting them. **Frames** are simulation-time coordinate systems — a Monte Carlo trial's records carry `frame: mc-trial-7`; a discrete-event simulation jumping to its next scheduled event carries the new `frame_time`. **Branches** are alternate timelines — a counterfactual simulation diverging from a backup point carries a new `branch_id` referencing its parent. Multiple frames and branches coexist in a single (I, R) graph.

The runtime is the timekeeper for any frame. The runtime advances frame-time per the simulation's declared strategy (event-driven, tick-driven, continuous), samples distributions from PRISM-IR generators, manages branching, and authors records with appropriate frame and branch annotations. The kernel hosts; doesn't compute.

The Alterverse — the tree of all simulation timelines — is hosted by the runtime, not by the kernel ledger. The kernel ledger records what the kernel did (real bridge crossings, real outside calls, real kernel ops). The Alterverse store records what the simulation experienced (token created, node entered, branch forked, phase boundary crossed). The two stores cross-reference by event ID. The kernel hosts a `_simulation.alterverse-store` meta-projection naming each Alterverse store's location and characteristics; the store contents themselves are managed by the runtime.

This is a clarification to PRISM-IR v1.1 (which framed the Alterverse as a filter view over the kernel ledger) and lands as PRISM-IR v1.2.

## Storage

The kernel commits to DuckDB as the storage backend for the event ledger, indexes, and (with the vss extension) vector search. Markdown files remain canonical for (I, R) records — human-readable, git-friendly, the source of truth from which DuckDB indexes regenerate. Sidecar payloads (when policy enables them) live as files referenced from event records.

Vectors are application-supplied. The kernel doesn't compute embeddings or pick embedding models; applications declare embedding schemes and store the resulting vectors in DuckDB columns. The kernel exposes vector similarity as a query primitive composable with structured filters.

The current binary uses JSONL files for the ledger. The architectural commitment is DuckDB; the migration is bounded and lands in subsequent implementation work.

Storage is implementation-defined for callers. The 17-operation SDK is the contract; whether the backend is JSONL, DuckDB, SQLite, or something else is opaque to programs using the SDK.

## Demonstration: Block 3 SCAN run

Block 3 manifested the first end-to-end run of a PRISM-IR program through the substrate. A SCAN-pillar daily briefing flow, four nodes (`fetch-sources` → `score-relevance` → `filter-and-rank` → `generate-briefing`), real HackerNews and arXiv items, real Anthropic API calls, round-trip-verified at high fidelity.

Total Anthropic spend across the dogfood plus the round-trip check: $0.0207.

The SCAN bundle (`docs/scan-block-3-bundle.md`) is a demo writeup, not a spec. It demonstrates: PRISM-IR can describe a real workload; the substrate can host and run it end-to-end; recomposition back to English from the resolved (I, R) graph alone produces a high-fidelity reconstruction; round-trip verification works in practice.

What Block 3 did not exercise: multi-factory concurrency, governance machinery (roles, policies, skills as v1.1 will define them), three-cost decomposition (current binary records aggregate clock; the v1.1 split is architectural), the v1.0.1-full amendment package (six accumulated open questions still deferred), or DuckDB storage. These are subsequent work.

## Honest gaps

This overview describes the architecture as committed for Block 1 v1.1. The current binary is at v1.0.1-partial. The gap is named, scoped, and bounded.

What is committed in v1.1 but not yet implemented:

- The 17th operation `kernel.ir.cancel` and the cancellation-status enum value.
- `kernel.outside.http` as the first outside-call primitive.
- Lease records as `_kernel.lease` projection type.
- Roles and policies as `_kernel.role` and `_kernel.policy` projection types, with the policy-evaluation phase on every kernel op.
- Skills as `_kernel.skill` projection type with manifest-bounded behavior, install-time policy gating, and revocation.
- Three-cost decomposition (`resolver_cost`, `kernel_cost`, `factory_cost`) on every resolution event.
- Bridge queues internal to `kernel.outside.http` with `priority` and `expires_at`.
- Payload hashing on every outside-call event; sidecar storage policy-gated.
- `data_classification` as application-declared frontmatter; classification-aware skill manifests.
- Conditional visibility (`visible_when`) on (I, R)s.
- Delayed-activation state for ops.
- `_simulation.alterverse-store` meta-projection.
- DuckDB storage backend with vss for vectors.
- Bridges as PRISM-IR programs (with backward-compatible `_kernel.bridge` projection during transition).

What is open and queued:

- Six accumulated PRISM-IR / 8OS interface gaps from Block 3 (OPEN-Q-019, 026, 027, 028, 029, 030) folded into the v1.1 amendment package.
- New open questions surfaced during architecture work: multi-factory atomicity discipline, ULID clock skew tolerance, lease-vs-filesystem-mutex final shape, cancellation propagation through dependency graphs, observability tool architecture.

What is deliberately left out:

- An autonomous-dispatch spec. The chat-6 reframe (factories as userspace PRISM-IR programs) plus the v1.1 governance and skill machinery covers most of what an autonomous-dispatch spec would have specified. Any remaining gaps will surface as concrete open questions during implementation rather than be specified in advance.
- A Task Manager equivalent. Observability tooling is userspace. The kernel exposes events and (I, R) state through existing read primitives; tools are downstream.

## Where to read next

| Want | Read |
|---|---|
| The eight axioms (kernel ABI, locked) | `docs/spec/8OS-KERNEL-SPEC-v0.1.md` |
| The 17 ops, the projection types, the v1.1 architecture | `docs/spec/8OS-BLOCK-1-SPEC-v1.1.md` (in progress) |
| The PRISM-IR side, with Alterverse-runtime-hosted clarification | `docs/spec/PRISM-IR-SPEC-v1.2.md` (in progress) |
| The Block 3 end-to-end demonstration | `docs/scan-block-3-bundle.md` |
| The earlier representation lineage | `docs/spec/8OS-BLOCK-1-SPEC-v1.0.md` and `v1.0.1-PARTIAL` |

Earlier overview at v1 (`8OS-OVERVIEW-v1.md`) is superseded by this document.

---

*End of 8OS Overview v2. Updates when the architecture commitments change.*
