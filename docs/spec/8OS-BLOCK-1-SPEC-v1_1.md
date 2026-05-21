---
id: 8OS-BLOCK-1-SPEC
version: 1.1.0
status: accepted
kind: derivation
scope: project
domain: 8os/representation
authored_by: Q88N + Claude
authored_on: 2026-04-28
supersedes: 8OS-BLOCK-1-SPEC v1.0.1-partial
superseded_by: null
depends_on: 8OS-KERNEL-SPEC v0.1.0
revisit_when: implementation surfaces a contradiction with the eight axioms or with this representation, or a multi-factory deployment exposes a coordination need this representation cannot express
provenance: Block 4 architecture conversation between Q88N and Claude derived the v1.1 commitments captured in the decisions log dated 2026-04-28. v1.1 consolidates v1.0.0 + v1.0.1-partial + Block 2.7 corrections + Block 2.8 amendments, adds the architectural primitives the decisions log locks, and ends the preserve-by-reference chain.
---

# 8OS Block 1 Specification v1.1

## What this document is

This is the on-disk and SDK specification for 8OS at v1.1. It supersedes v1.0.1-partial and consolidates the lineage that preceded it: v1.0.0, the Block 2.7 spec corrections, the Block 2.8 spec amendments, and the v1.0.1-partial amendment file. A reader of this document does not need to chain through earlier versions to understand the current contract. The contract is here.

v1.1 is the architectural commitment that follows the SCAN dogfood (Block 3) and the conversations that surfaced the multi-factory, governance, skill, and three-cost machinery the substrate needs to host real workloads at scale. It introduces seventeen SDK operations (sixteen from v1.0.1-partial preserved verbatim plus one new operation `kernel.ir.cancel`); a parallel category of outside-call primitives specified separately from the SDK because axiom 0 distinguishes them; six new projection types for governance, coordination, skills, and simulation hosting; three-cost decomposition on every resolution event; conditional visibility, classification, and domain as base frontmatter; the status enum extension `cancelled`; the storage commitment to DuckDB; and the framing that bridges, factories, and skills are PRISM-IR programs running on the kernel.

This is a substantial spec. It is longer than its predecessors because it consolidates rather than amends. The length is the price of ending the preserve-by-reference chain that the recon flagged: the SDK contract assembled across four prior documents, three of which carried partial supersedence, is now in one place.

## Status of v1.0.1-partial

v1.0.1-partial is **superseded** by this document. The three amendments it carried — projection-declared `target_subdirectory`, mandatory `authored_via`, per-version body seal — are folded into the relevant sections of this spec. A v1.0.1-partial implementation upgrading to v1.1 follows the migration in §19.

The Block 2.7 spec corrections and Block 2.8 spec amendments are likewise folded in. They are no longer separate documents under `docs/spec/`; their content is in the relevant sections here, with a note in §19 mapping each prior patch to its current location for reader continuity.

v1.0.0 is preserved in `docs/spec/8OS-BLOCK-1-SPEC-v1.0.md` for historical reference. New work targets v1.1.

## Implementation gap, named honestly

The current binary is at v1.0.1-partial. v1.1 is the architectural commitment, not the implementation state. Specifically not yet implemented at the time this spec is published:

- The 17th operation `kernel.ir.cancel` and the `cancelled` status enum value
- `kernel.outside.http` as the outside-call primitive
- Lease records as `_kernel.lease` projection type
- Roles and policies as `_kernel.role` and `_kernel.policy` projection types, with the policy-evaluation phase on every kernel op
- Skills as `_kernel.skill` projection type with manifest-bounded behavior, install-time policy gating, and revocation
- Three-cost decomposition (`resolver_cost`, `kernel_cost`, `factory_cost`) on every resolution event
- Bridge queues internal to `kernel.outside.http` with `priority` and `expires_at`
- Payload hashing on every outside-call event; sidecar storage policy-gated
- `data_classification` as application-declared frontmatter
- Conditional visibility (`visible_when`) on (I, R)s
- Delayed-activation state for ops
- `_simulation.alterverse-store` meta-projection
- DuckDB storage backend with vss for vectors
- Bridges as PRISM-IR programs (with backward-compatible `_kernel.bridge` projection during transition)

What is implemented and shipping at v1.0.1-partial: the kernel ABI per the eight axioms, the sixteen operations from the v1.0.1-partial SDK contract, the factory + Anthropic Python bridge, the SCAN dogfood with round-trip recomposition, calibration policies and predictors, and the single-writer JSONL ledger.

This spec is the architectural contract. Subsequent implementation blocks land it. The gap is named, scoped, and bounded.

---

## Section 0 — Framing that precedes the mechanics

Three properties of the v1.1 design must be made explicit before the machinery is specified, so none of them is lost in the spec's mechanical framing.

### 0.0 Conventions

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** in this document are to be interpreted as described in RFC 2119, when they appear in all capitals. Lowercase usage of these words ("the kernel must enforce", "the factory should consider") carries ordinary English meaning, not the RFC 2119 contractual sense.

The kernel spec v0.1.0 does not establish RFC 2119 conventions. v1.1 of Block 1 introduces them for representation-level work; future kernel spec versions may absorb the convention upward.

### 0.1 Four layers, each with a specific concern

8OS is best understood as four layers, each with characteristic responsibilities and an explicit cleavage from its neighbors.

**The kernel** is the substrate. It hosts the (Intention, Resolution) graph, enforces invariants and limits, publishes facts, and exposes a small set of primitives. The kernel is opinion-free at the value level: it knows there are cost vectors but doesn't pick currencies; it knows there are authority levels but doesn't define who holds them; it knows there are scopes but doesn't define what scopes mean; it knows there are roles, policies, classifications, and freshness models but doesn't define their values. Mechanisms are kernel; values are application.

**PRISM-IR** is the language. Programs declare intent, structure, decision flows, parallelism, SLAs, surrogates, generators, and constraints. PRISM-IR is opinion-free at the strategy level: the language declares what; runtimes decide how. PRISM-IR is co-resident with 8OS and owned by DEIA Solutions; the kernel hosts PRISM-IR programs as one projection type among many. The PRISM-IR specification is independent of this one; v1.1 of Block 1 commits to hosting PRISM-IR v1.1 (and forward-compatibly v1.2 once published).

**The factory** is the runtime. It walks PRISM-IR graphs, dispatches resolvers, advances simulation clocks, samples distributions, queues bridge crossings, and chooses execution policy. Different factories make different choices; the kernel hosts the work product of any of them. v1.1 specifies the substrate factories run on; the factory itself is a userspace PRISM-IR program. Block 3 implemented one such factory; future factory specifications will land alongside subsequent implementation blocks.

**The application** is the composer. It supplies the values the kernel and PRISM-IR leave open: which currencies, which authorities, which scopes, which classifications, which roles, which policies, which skills, what they mean for this domain. Family Bond Bot is one application; SCAN is another; future projects on 8OS are more.

The cleavage is operational: anything that mutually-distrusting factories cannot safely re-implement is kernel; anything declarative about a process is PRISM-IR; anything about how to execute is factory; anything domain-specific is application. v1.1 sharpens the kernel/factory cleavage that v1.0 left implicit. The kernel is the smallest substrate that supports the eight axioms and the resulting invariants; everything else moves out.

### 0.2 The inside/outside split is structural, not stylistic

Axiom 0 divides the kernel's surface into two categories. **Inside ops** manipulate state the kernel owns: they create, resolve, expand, supersede, cancel, query (I, R) records that live in the kernel's graph. **Outside-call primitives** cross a boundary the kernel observes but does not contain: they reach to LLM APIs, network services, files, humans, simulators, and other reality the kernel cannot decompose.

The two categories share an SDK shape — both have inputs, outputs, atomicity discipline, error codes, and tier 3 event emission — but they are not the same surface. Treating them as one would flatten the inside/outside distinction the kernel was built around and would invite implementations that confuse "the kernel did something" with "the kernel observed something the outside did."

v1.1 makes the split structural. §3 specifies the seventeen SDK operations — all inside ops. §11 specifies `kernel.outside.http` and the outside-call governance machinery. The two sections are parallel in form (op contract, atomicity, error codes, event shape) but separate by intent. A reader counting "how many things does the kernel expose" gets seventeen for inside ops and a small number of outside-call primitives, with the count separation reflecting the underlying architecture, not just an editorial choice.

This is not new. v0.1 listed `kernel.bridge.cross` alongside the inside ops, which obscured the distinction. v0.2 trimmed the typed bridge/resolver wrappers, which began the cleanup. v1.1 finishes it: outside-call primitives are their own category. `kernel.bridge.cross` is preserved as a backward-compatible transition path during the move toward bridges-as-PRISM-IR programs, but new outside-call work targets `kernel.outside.http` and lives in §11's category.

### 0.3 Predictors, sovereignties, and the prediction-economics machinery from v1.0 are preserved

v1.0's framing of predictors as resolver-shaped (not LLM-shaped), of bridge sovereignties (every resolver is sovereign over its own outputs; the kernel records and reasons but does not adjudicate truth), and of the prediction-economics machinery (predictions, calibration policies, VOI consultation, proxy signals, depth-budgeted cost models, structured stakes with scope inheritance) is preserved verbatim in v1.1. Those mechanics are foundational and have proven sound through v1.0.1-partial dogfooding. v1.1 does not modify them; it adds adjacent machinery that the v1.0 predicates could not previously express (multi-factory coordination, governance, skills, three-cost decomposition).

The prediction-economics machinery is opt-in and degrades gracefully, as v1.0 §0.1 specified. A v1.1 scope without a calibration policy operates without VOI consultation and without prediction (I, R)s, exactly as in v1.0 and v1.0.1-partial.

---

## Section 1 — The four-layer architectural model

This section names the architecture v1.1 commits to. The layers are introduced in §0.1; this section specifies the cleavage rules that determine which layer hosts which concern.

### 1.1 The cleavage principle

The cleavage principle assigns concerns to layers:

- **Kernel** hosts anything that mutually-distrusting factories cannot safely re-implement. Identity uniqueness, provenance honesty, scope visibility, authority hierarchy, atomicity, append-only event ordering, honest cost accounting (the resolver/kernel/factory split), honest status enumeration, lease arbitration when leases are required, policy evaluation when policies gate ops. If two factories are running against the same (I, R) graph and one factory's correctness depends on the other not lying about something, that something is kernel work.
- **PRISM-IR** hosts anything declarative about a process: intent, node structure, decision flow, parallelism, SLA targets, fail policy, surrogate substitution, generator distributions, constraints. PRISM-IR is the language; programs target it. SLAs, retry semantics, decomposition strategy, and skill manifests are PRISM-IR concerns because they must be inspectable, auditable, and round-trip-verifiable. Hiding them in factory code makes them ungovernable.
- **Factory** hosts anything about how to execute a PRISM-IR program: walking strategy, dispatch order, queue layout for factory-local work, retry implementation, parallelism implementation, decomposition resolver invocation, prediction pre-phase, holdout sampling. Different factories make different choices. The kernel hosts the work product of any of them.
- **Application** hosts anything domain-specific: which currencies the cost vectors track in this project, which roles exist and who holds them, which scopes mean what, which classifications the application defines, which authorities the project recognizes, what policies the application enforces, what skills the application installs.

When a concern is unclear, the cleavage test is: "can two factories that don't trust each other safely re-implement this independently?" If yes, it's not kernel — it lives in the factory or above. If no, the kernel must enforce it.

### 1.2 Why the cleavage matters at v1.1 specifically

v0.1 through v1.0.1-partial were single-factory specs in practice. The reference implementation is single-writer-per-process; the multi-factory case was discussed but not exercised. v1.1 is the architectural commitment that the kernel must support multi-factory deployments — different factories running concurrently against the same (I, R) graph, possibly with mutually-distrusting authors. The cleavage matters because it determines what the kernel must do regardless of which factory is running, and what it can safely leave to factory choice.

Examples of v1.1 commitments that follow from the cleavage:

- The kernel must arbitrate leases when multiple factories contest the same (I, R) for write. Leases live in `_kernel.lease` records and `kernel.ir.new` enforces them. Factory-local concurrency control is the factory's problem; cross-factory concurrency control is the kernel's.
- The kernel must enforce policies declared as `_kernel.policy` records on every op a policy applies to. A factory cannot opt out of policy evaluation. Policies are kernel-evaluated because two factories that don't trust each other cannot both verify the other's policy enforcement.
- The kernel must record cost honestly — including its own kernel_cost and including the factory_cost the factory reports. Factories that lie about cost cannot be detected by other factories without the kernel maintaining the canonical record.
- Walking strategy, dispatch order, and decomposition logic stay in the factory because two factories with different strategies do not need to agree on each other's choices to share the same (I, R) graph safely.

### 1.3 PRISM-IR as the language layer

v1.1 commits to hosting PRISM-IR programs as the canonical declarative form for processes on the kernel. This includes user-authored workloads (SCAN, FBB workflows, future application processes), kernel-internal programs that v1.1 reframes as PRISM-IR (bridges per §10, skills per §9), and factories themselves once a future spec block lands the factory-as-PRISM-IR commitment.

PRISM-IR is not 8OS-internal. It is co-resident, owned by DEIA Solutions, and has its own version history. v1.1 of Block 1 hosts PRISM-IR v1.1; the alterverse-store machinery in §15 anticipates a PRISM-IR v1.2 amendment that lands alongside this spec. The interface between Block 1 and PRISM-IR is the projection-type mechanism: PRISM-IR programs are stored as (I, R) records with `projection_types: [prism-ir]`, and the kernel applies its standard validation, query, and event-emission machinery to them.

The kernel-side hook for runtime-hosted Alterverse stores is the `_simulation.alterverse-store` meta-projection (§7.6). The kernel hosts the meta-projection regardless of whether PRISM-IR v1.2 publishes on schedule; the v1.2 amendment, if and when it publishes, makes the runtime-hosted commitment explicit on the language side. v1.1 of Block 1 commits only to the kernel side.

### 1.4 Factories as userspace programs

Block 3 implemented a factory in `src/eightos/factory/` and validated end-to-end that a PRISM-IR program can be decomposed by a registered resolver, materialized as kernel-hosted (I, R) records, walked, dispatched, and recomposed back to English at high fidelity. The factory uses only the SDK; it is not part of the kernel.

v1.1 does not specify the factory as a separate spec block. The factory specification is a future block. v1.1's commitment is that the kernel is sufficient to host any factory that respects the SDK contract and the cleavage rules. Multiple factories may coexist on the same (I, R) graph; coordination among them uses the lease, role, policy, and event-ledger mechanisms specified here.

### 1.5 Applications as composers

The application layer supplies values the lower layers leave open. v1.1 does not specify any application; it specifies the hooks applications use to compose. The hooks are: scope declarations (which the application authors), authority levels (which the application defines and assigns to authors), classification taxonomies (which the application defines through `data_classification` values it uses and policies it writes), role definitions (`_kernel.role` records the application authors), policy definitions (`_kernel.policy` records the application authors), and skill definitions (`_kernel.skill` records the application authors and installs).

The application is sovereign over what these mean in its domain. The kernel enforces the mechanics; the application supplies the values; PRISM-IR programs declare how the application's values shape process flow.

---

## Section 2 — Kernel responsibilities

The kernel has four kinds of responsibilities. The categories matter because they constrain what new primitives can be added principled-ly: a proposed new kernel feature must fit in one of these four categories, and proposals that don't fit are evidence the feature belongs in the factory, in PRISM-IR, or in the application.

### 2.1 Invariants

Invariants are properties the kernel enforces unconditionally. They cannot be violated; the kernel actively prevents it.

- **Identity uniqueness.** Every (I, R) has a unique id. `kernel.ir.new` rejects duplicate ids with `ID_CONFLICT`.
- **Provenance honesty.** Every (I, R) carries `authored_by`, `authored_on`, `authored_via`, and `authority_level`. Records lacking these fields are rejected at write time and flagged by `kernel.reindex --check`.
- **Scope visibility.** Resolutions visible only within their scope (and subscopes) per axiom 3. Cross-scope queries that would expose private resolutions to scopes that should not see them are rejected.
- **Authority hierarchy.** Hard authority overrides convention; convention overrides uncalibrated. Conflict resolution among same-scope (I, R)s respects this hierarchy per axiom 6.
- **Atomicity.** Every kernel op is single-commit: the (I, R) write, the tier 3 event write, the index updates, and any cascading state changes complete together or none of them does. Op-by-op atomicity rules are specified in §3.
- **Append-only event ordering.** The tier 3 event ledger is append-only. Events are not edited or deleted. Causal ordering is established by `depends_on` edges and event-log sequence, not by timestamp comparison.
- **Honest cost decomposition.** Every resolution event records cost split into three components: `resolver_cost`, `kernel_cost`, `factory_cost`. The components sum to total cost without information loss. Calibration math reads `resolver_cost` only, so resolver characterization is not contaminated by kernel or factory overhead. Specified in §6.
- **Honest status enumeration.** The `status` field on every (I, R) takes one of five values: `open`, `resolved`, `superseded`, `stale`, `cancelled`. The kernel enforces lifecycle transitions per §5.

### 2.2 Limits

Limits are upper bounds enforced against declared budgets. The kernel rejects operations that would exceed declared limits.

- **Bridge rate limits.** Outside-call primitives may declare rate-limit budgets per scope, per resolver, or per bridge. `kernel.outside.http` rejects calls that would exceed declared rates with `RATE_LIMIT_EXHAUSTED`.
- **Scope cost ceilings.** Scopes may declare cost ceilings per currency. The kernel tracks running totals and rejects ops whose declared cost would push the scope over ceiling with `BUDGET_EXHAUSTED`.
- **Lease TTLs.** Leases have explicit expiration via the axiom-4 `valid_through` field. Operations against an expired lease fail with `LEASE_EXPIRED`. The kernel does not auto-renew; renewal is an explicit op.
- **Queue cutoffs.** Outside-call ops may carry `expires_at` indicating the latest acceptable service time. The kernel drops queued calls whose `expires_at` has passed with `EXPIRES_AT_PASSED`. Specified in §11.

### 2.3 Facts

Facts are queryable kernel-published state that factories use to make decisions. Without authoritative facts, factories make blind decisions or duplicate the kernel's bookkeeping inconsistently.

- **Tier 3 event ledger.** The canonical record of all bridge crossings, kernel ops, resolution events, cancellation events, lease arbitrations, and policy evaluations. Append-only. Queryable via `kernel.event.get`.
- **Resolver capability and cost vectors.** Every `_kernel.resolver` (I, R) carries declared cost and capability vectors per axiom 5. The calibrator updates them based on operational evidence. Factories read them when invoking the selector.
- **Resolver substitutability.** Surrogate lineage records (`_kernel.surrogate-lineage`) declare which resolver a surrogate approximates. Factories use this to discover replacement candidates per axiom 7.
- **Bridge state.** Current bridge state — recent latency, recent error rates, recent cost per call — is derivable from the tier 3 event ledger by query. The kernel does not maintain a denormalized "bridge state" record; factories that need it query the ledger.
- **Policy evaluations.** Cached policy decisions live in `_kernel.policy-evaluation` records, TTL'd via axiom 4. Factories that need to know whether a policy permits an op can read the cached result instead of re-evaluating.
- **Lease holders.** The current holder of any lease is queryable via `_kernel.lease` records. Factories check before writing.

### 2.4 Primitives

Primitives are the operations the kernel exposes for factory use. v1.1 splits primitives into two categories per §0.2:

- **Inside ops** — the seventeen SDK operations specified in §3. They manipulate state the kernel owns.
- **Outside-call primitives** — `kernel.outside.http` and the surrounding governance machinery, specified in §11. They cross to a reality the kernel observes but does not contain.

Both categories share the same SDK shape (op contract, atomicity, error codes, tier 3 event emission). They differ in what they touch. The seventeen SDK ops never reach outside the kernel's ownership; the outside-call primitives always do.

The inside/outside split is structural per axiom 0. v1.1 makes it visible in the spec organization. A reader counting operations gets seventeen for the inside SDK and a small number of outside-call primitives, with the separation reflecting the underlying architecture.

### 2.5 What the kernel does not do, and where each concern lives

The kernel does not schedule, retry, prioritize, walk graphs, decompose programs, choose substitutes, weight priorities, interpret SLAs, define queue layouts, host observability tooling, define lifecycle UI, tokenize, classify content semantically, moderate content, manage encryption keys, store PII, or commit to any specific value-level meaning. Those concerns live elsewhere. The placement is explicit:

| Concern | Lives in | Why |
|---|---|---|
| Scheduling | Factory | Different factories make different scheduling choices; the kernel offers atomicity and event ordering. |
| Retry policy | Factory or PRISM-IR | PRISM-IR's `fail` grammar can declare; factories implement. |
| Prioritization weighting | PRISM-IR + Factory | PRISM-IR declares priority on nodes; factory derives an integer to pass to outside-call primitives; kernel honors the integer. |
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
| Currency definitions | Application | The kernel knows there are cost vectors; the application names what each component measures in this domain. |
| Skill semantics | Application + PRISM-IR | The kernel hosts the skill manifest as a projection; PRISM-IR expresses the skill's program; the application supplies the skill's domain meaning. |

The "MUST" entries flag cases where placing the concern elsewhere would defeat its purpose. SLA semantics in factory code are ungovernable; decision-and-action separation collapsed into factory logic loses auditability; skills as opaque code recreate the security failure modes the architecture is built to avoid.

---

## Section 3 — The 17 SDK operations

This section specifies the seventeen inside operations that constitute the v1.1 SDK contract. The contract is self-contained here; a reader does not need to chain through earlier specs to assemble it.

The seventeen operations are sixteen preserved from v1.0.1-partial plus one new operation `kernel.ir.cancel`. Outside-call primitives (`kernel.outside.http` and related machinery) are specified separately in §11; they are not part of the seventeen-op count, by structural intent per §0.2.

### 3.0 The seventeen operations at a glance

| # | Operation | Category | Touches |
|---|---|---|---|
| 1 | `kernel.init` | Bootstrap | Repo state, vendored projections, kernel-internal (I, R)s |
| 2 | `kernel.ir.new` | Authoring | One new (I, R) record |
| 3 | `kernel.ir.resolve` | Authoring | One existing (I, R), staking its resolution |
| 4 | `kernel.ir.expand` | Structural | One (I, R)'s child graph |
| 5 | `kernel.ir.collapse` | Structural | One (I, R)'s collapsed-summary view |
| 6 | `kernel.ir.promote` | Authoring | Promotes a tier 3 event to tier 2 (I, R) |
| 7 | `kernel.ir.supersede` | Authoring | Supersedes one (I, R) with another |
| 8 | `kernel.ir.cancel` | Authoring | **NEW in v1.1.** Marks (I, R) cancelled, cascades |
| 9 | `kernel.ir.get` | Query | Reads one (I, R) |
| 10 | `kernel.ir.list` | Query | Lists (I, R)s by filter |
| 11 | `kernel.ir.deps` | Query | Returns dependency edges for one (I, R) |
| 12 | `kernel.bridge.cross` | Bridge (legacy) | Crosses a `_kernel.bridge`-defined bridge |
| 13 | `kernel.authorize` | Authorization | Authors an `_kernel.authorization` (I, R) |
| 14 | `kernel.gatekeeper.check` | Authorization | Checks whether an op is permitted |
| 15 | `kernel.selector.select` | Selection | Picks a resolver per axiom 5 |
| 16 | `kernel.event.get` | Query | Reads a tier 3 event |
| 17 | `kernel.reindex` | Maintenance | Regenerates indexes; with `--check` validates |

`kernel.bridge.cross` is preserved as a backward-compatibility path during the transition to bridges-as-PRISM-IR programs (§10). New outside-call work targets `kernel.outside.http` per §11. Both operations may coexist; bridges declared as `_kernel.bridge` (I, R)s remain crossable via `kernel.bridge.cross` for the duration of the transition.

The `kernel.surrogate.train` interface stub from v0.1 is **removed** in v1.1. Surrogate training is userspace; v1.1 does not commit the kernel to hosting a training pipeline. The decision is per the decisions log §4.4.

### 3.1 `kernel.init`

**Purpose**: Initialize an 8OS repository or upgrade an existing repo to the current kernel version. Vendors kernel-internal (I, R)s on first init, refreshes vendored bodies on version transitions, idempotent on repeat invocation.

**Input**:
```json
{ "repo_path": "<path>",
  "kernel_version": "<semver-string>",
  "mode": "init" | "upgrade" | "check" }
```

**Output**:
```json
{ "version_before": "<semver-string>"|null,
  "version_after": "<semver-string>",
  "vendored_bodies_refreshed": [<projection-type-string>, ...],
  "vendored_records_authored": [<id>, ...],
  "tier3_event_id": "<id>"|null }
```

**Atomicity**: single-commit. If any phase fails, the repo state is unchanged. Idempotent: running `kernel.init` twice with the same `kernel_version` against the same repo state is a no-op after the first.

**Authority**: hard. `kernel.init` authors records into the `_kernel` scope on the kernel's own behalf. Internal-origin records carry `authored_via: kernel.self` per the v1.0.1-partial discipline.

**Files**: writes the `.8os/` directory tree on first init; writes vendored projection bodies under `.8os/projections/_kernel/`; writes vendored kernel-internal (I, R)s under `ir/_kernel/`; writes one tier 3 event recording the init or upgrade.

**Errors**: `REPO_PATH_INVALID`, `VERSION_DOWNGRADE_REJECTED` (existing version is newer than requested), `VENDORED_BODY_INVALID` (binary's vendored body schema fails validation against itself).

**Axioms**: 1 (primitive), 6 (provenance), 4 (per-version body seal lifecycle).

### 3.2 `kernel.ir.new`

**Purpose**: Create a new (I, R) record. The atomic write op for tier 1 user content and tier 2 internal content authored through external bridges.

**Input**:
```json
{ "scope": "<scope-id>",
  "id": "<slug>",
  "projection_types": [<projection-type-string>, ...],
  "frontmatter": { ...base 8OS fields... },
  "frontmatter_extensions": { ...projection-declared fields... },
  "body": "<markdown-string>",
  "authored_via": "<bridge-string>",
  "supersedes": "<ir-id>"|null }
```

**Output**:
```json
{ "ir_id": "<id>",
  "path": "<path>",
  "tier3_event_id": "<id>" }
```

**Atomicity**: single-commit. The (I, R) file write, the tier 3 event write, and the index updates complete together. Validation failures on any projection-declared field reject before any file is staged.

**Authority**: caller-supplied `authority_level`, validated against the scope's authority requirements per §2.3 (kernel scope) and §4.

**Validation**: `frontmatter_extensions` is validated against the union of required fields from all listed `projection_types`. Conflicting required fields across multiple projection types reject with `CONFLICTING_PROJECTION_FIELDS`. Conflicting `target_subdirectory` values across multiple projection types reject with `CONFLICTING_PROJECTION_TARGETS` (per v1.0.1-partial Amendment 1, folded in here).

**Path resolution**: per v1.0.1-partial Amendment 1: if any of the record's `projection_types` declares `target_subdirectory:`, the target path is `ir/<scope>/<target_subdirectory>/<id><filename_suffix>`. Otherwise the target path is `ir/<scope>/<id><filename_suffix>`.

**Required field**: `authored_via` (per v1.0.1-partial Amendment 2, folded in here). Non-empty string. SDK boundary defaults to `outside` for callers who do not specify; internal kernel ops explicitly pass `kernel.self`.

**Supersede-with-replacement of cancelled records** (per BLOCK-4.5-SPEC-AMENDMENTS.md Amendment 4): when the optional `supersedes` input is non-null, the new (I, R) is authored as a replacement for a previously-cancelled target. The kernel validates that the target id exists (`IR_NOT_FOUND` if not) and that the target's status is `cancelled` (`IR_SUPERSEDES_TARGET_NOT_CANCELLED` otherwise). The new (I, R) carries `status: open` and a frontmatter `supersedes:` pointer to the cancelled target. The cancelled target is not mutated by this op; it remains terminally `cancelled` with no forward pointer to the new record. Discovery of "what replaced this cancelled record" is via index lookup on the new records' `supersedes:` field, not a property of the cancelled one. This is the canonical reversal path named in §3.8's reversibility clause; `kernel.ir.supersede` (§3.7) remains the path for living records and rejects cancelled targets. The target's scope is unconstrained — cross-scope reversal is permitted at v1.1.

**Lease check**: if a `_kernel.lease` record exists for this scope or this (I, R) path with a holder other than the caller, the op rejects with `LEASE_HELD`. Specified in §13.

**Policy evaluation**: if any `_kernel.policy` record applies to `kernel.ir.new` for this scope or projection type, the op evaluates the policy before commit. Policy decisions of `deny` reject the op with `POLICY_DENIED`. Specified in §8.

**Classification check**: if the record carries `data_classification` and any applicable policy gates writes by classification, the op enforces the classification. Specified in §4.2 and §8.

**Files**: writes one `ir/<scope>/[<target_subdirectory>/]<id><filename_suffix>` markdown file; writes one tier 3 event; updates indexes (`id-to-path`, `path-to-id`, `scope-to-ids`, `tier-to-ids`, `projection-to-ids`, `temporal`, `deps-forward`, `deps-reverse`, `_checksum`); when applicable, updates calibration-corpus index (per v1.0 §6.1).

**Errors**: `ID_CONFLICT`, `SCHEMA_INVALID`, `CONFLICTING_PROJECTION_FIELDS`, `CONFLICTING_PROJECTION_TARGETS`, `AUTHORITY_INSUFFICIENT`, `SCOPE_NOT_FOUND`, `LEASE_HELD`, `POLICY_DENIED`, `CLASSIFICATION_VIOLATION`, `IR_NOT_FOUND`, `IR_SUPERSEDES_TARGET_NOT_CANCELLED`.

**Axioms**: 1 (primitive), 3 (scope), 4 (temporal), 6 (provenance).

### 3.3 `kernel.ir.resolve`

**Purpose**: Stake a resolution against an open (I, R). Records the resolution, the resolver that produced it, the cost decomposition, and the resolution event.

**Input**:
```json
{ "ir_id": "<id>",
  "resolver_id": "<id>",
  "resolution_text": "<string>",
  "resolution_data": <opaque>|null,
  "cost_actual": {
    "resolver_cost": { "clock_ms": <num>, "coin_usd": <num>, "carbon_g": <num> },
    "kernel_cost": { "clock_ms": <num>, "coin_usd": <num>, "carbon_g": <num> },
    "factory_cost": { "clock_ms": <num>, "coin_usd": <num>, "carbon_g": <num> }
  },
  "evaluation": <opaque>|null,
  "valid_through": "<iso8601>"|null,
  "revalidate_trigger": <opaque>|null }
```

**Output**:
```json
{ "resolution_event_id": "<id>",
  "tier3_event_id": "<id>",
  "ir_status_after": "resolved" }
```

**Atomicity**: single-commit. The (I, R) status transition, the resolution payload write, the tier 3 event, and index updates complete together.

**Authority**: matches the resolver's declared authority. Hard-authored resolutions require a resolver registered with hard authority.

**Cost decomposition**: per §6, `cost_actual` carries three vectors. The kernel records each separately; the calibrator reads `resolver_cost` only when updating capability vectors. Callers MUST supply all three components; passing zero for components the caller did not measure is a discipline violation but not enforced by the kernel.

**Status transition**: the (I, R)'s `status` transitions from `open` to `resolved`. Resolving an (I, R) that is already `resolved`, `superseded`, `stale`, or `cancelled` rejects with `IR_NOT_RESOLVABLE`.

**Lease check**: same shape as `kernel.ir.new`. `LEASE_HELD` if contested.

**Policy evaluation**: same shape as `kernel.ir.new`. `POLICY_DENIED` if denied.

**Files**: updates the (I, R) markdown file with resolution payload; writes one tier 3 event; updates indexes.

**Errors**: `IR_NOT_FOUND`, `IR_NOT_RESOLVABLE`, `RESOLVER_NOT_FOUND`, `AUTHORITY_INSUFFICIENT`, `LEASE_HELD`, `POLICY_DENIED`, `COST_DECOMPOSITION_INVALID`.

**Axioms**: 1, 4, 5, 6.

### 3.4 `kernel.ir.expand`

**Purpose**: Author the child graph of an (I, R). Creates child (I, R) records and links them to the parent via `parent: <parent-id>` and the parent's `expanded_into: [<child-id>, ...]`.

**Input**:
```json
{ "ir_id": "<parent-id>",
  "children": [
    { "id": "<slug>",
      "projection_types": [<projection-type-string>, ...],
      "frontmatter": { ... },
      "frontmatter_extensions": { ... },
      "body": "<markdown-string>",
      "authored_via": "<bridge-string>" },
    ...
  ] }
```

**Output**:
```json
{ "parent_id": "<id>",
  "child_ids": [<id>, ...],
  "tier3_event_id": "<id>" }
```

**Atomicity**: single-commit. All children are authored together with the parent's `expanded_into` update, or none of them is. Partial expansion is not a valid state.

**Authority**: caller authority; each child carries its own `authority_level`.

**Lease check / policy evaluation / classification**: same shapes as `kernel.ir.new`, applied per child.

**Files**: writes one markdown file per child; updates parent's frontmatter to populate `expanded_into`; writes one tier 3 event covering the expansion; updates indexes.

**Errors**: `IR_NOT_FOUND`, `IR_ALREADY_EXPANDED`, plus all errors `kernel.ir.new` can return for any of the children.

**Axioms**: 1, 2 (fractal), 3, 6.

### 3.5 `kernel.ir.collapse`

**Purpose**: Mark an expanded (I, R)'s child graph as collapsed for the purposes of querying at the parent's level. The children remain authored; collapse is a view operation, not a deletion.

**Input**:
```json
{ "ir_id": "<id>",
  "collapsed_summary": "<string>"|null }
```

**Output**:
```json
{ "ir_id": "<id>",
  "collapsed_at": "<iso8601>",
  "tier3_event_id": "<id>" }
```

**Atomicity**: single-commit. The parent's frontmatter update and the tier 3 event complete together.

**Effect**: queries at the parent's depth return the parent's collapsed view; `kernel.ir.expand` on the same parent re-authors the existing children (or rejects with `ALREADY_EXPANDED` if the children are still present and unchanged). The kernel does not delete child records on collapse.

**Files**: updates the parent's frontmatter; writes one tier 3 event.

**Errors**: `IR_NOT_FOUND`, `IR_NOT_EXPANDED`.

**Axioms**: 2.

### 3.6 `kernel.ir.promote`

**Purpose**: Promote a tier 3 event to a tier 2 (I, R) record. Used when an event in the ledger represents work the kernel later treats as content (selector decisions, calibration updates, authorization grants).

**Input**:
```json
{ "tier3_event_id": "<id>",
  "promoted_projection_type": "<projection-type-string>",
  "frontmatter_extensions": { ... },
  "authored_via": "<bridge-string>" }
```

**Output**:
```json
{ "promoted_ir_id": "<id>",
  "path": "<path>",
  "tier3_event_id": "<id>" }
```

**Atomicity**: single-commit.

**Authority**: derived from the tier 3 event's source. Promoted records carry `authored_via` derived from the source event's `bridge_id`, defaulting to `outside` when the source event carried no bridge (per v1.0.1-partial Amendment 2's clarification).

**Files**: writes a markdown record under `ir/<scope>/[_<subdir>/]<id><filename_suffix>`; writes one tier 3 event recording the promotion; updates indexes.

**Errors**: `EVENT_NOT_FOUND`, `EVENT_ALREADY_PROMOTED`, `PROMOTION_NOT_PERMITTED` (when the tier 3 event is of a category not eligible for promotion to the requested projection type).

**Axioms**: 1, 6.

### 3.7 `kernel.ir.supersede`

**Purpose**: Supersede an existing (I, R) with a new one. The old (I, R) gets `superseded_by: <new-id>` and `status: superseded`; the new (I, R) gets `supersedes: <old-id>`.

**Input**:
```json
{ "supersedes_id": "<id>",
  "scope": "<scope-id>",
  "id": "<slug>",
  "projection_types": [<projection-type-string>, ...],
  "frontmatter": { ... },
  "frontmatter_extensions": { ... },
  "body": "<markdown-string>",
  "authored_via": "<bridge-string>" }
```

**Output**:
```json
{ "superseded_id": "<id>",
  "new_ir_id": "<id>",
  "tier3_event_id": "<id>" }
```

**Atomicity**: single-commit. The old record's status update, the new record's authoring, and the tier 3 event complete together.

**Authority**: the new (I, R)'s `authority_level` MUST be at least equal to the superseded record's. Hard-authored records can be superseded only by hard-authored records.

**Lease check / policy evaluation / classification**: same shapes as `kernel.ir.new`.

**Files**: writes the new record; updates the old record's frontmatter; writes one tier 3 event; updates indexes.

**Errors**: `IR_NOT_FOUND`, `IR_NOT_SUPERSEDABLE` (when the target is already `superseded`, `cancelled`, or `stale`), `AUTHORITY_INSUFFICIENT_FOR_SUPERSESSION`, plus all errors `kernel.ir.new` can return.

**Axioms**: 1, 4, 6.

### 3.8 `kernel.ir.cancel` — NEW in v1.1

**Purpose**: Mark an (I, R) `status: cancelled`. Cancellation is terminal: a cancelled (I, R) cannot be resolved, expanded, or superseded by edits; reversal requires authoring a new (I, R) with `supersedes: <cancelled-id>` (supersede-with-replacement). Cancellation cascades to dependents, marking them `status: stale`.

**Input**:
```json
{ "ir_id": "<id>",
  "cancelled_by": "<author-string>",
  "reason": "<string>"|null,
  "cascade": <bool>,
  "authored_via": "<bridge-string>" }
```

**Output** (per BLOCK-4.5-SPEC-AMENDMENTS.md Amendment 2 — `cancellation_event_id` dropped; `tier3_event_id` is canonical):
```json
{ "ir_status_after": "cancelled",
  "affected_dependents": <int>,
  "dropped_pending_ops": <int>,
  "tier3_event_id": "<id>" }
```

**Atomicity**: single-commit. The (I, R) status transition, the cascade to dependents (if `cascade: true`, default), the drop of pending bridge crossings against the cancelled (I, R), and the tier 3 cancellation event complete together.

**Authority**: author-or-higher by default. The caller's authority MUST be at least equal to the target's `authored_by` author's authority. Policies (§8) MAY override the default to permit broader cancellation rights (e.g., scope-admin can cancel any (I, R) in their scope) or narrower rights (e.g., only the original author can cancel).

**Cascade behavior**: when `cascade: true` (default), the kernel walks the `deps-reverse` index from the cancelled (I, R) and marks each direct dependent's `status: stale`, bounded by scope visibility per axiom 3. Dependents in scopes invisible to the cancelled (I, R)'s scope are not cascaded. The cascade respects the same lease and policy rules as direct status edits: a dependent under a held lease is marked stale through the cascade event but the cascade does not block on the lease.

**Cascade scope — direct dependents only at v1.1.** The cascade walks one hop in the `deps-reverse` index. Transitive cascade (dependents of dependents) is **not** specified in v1.1. A dependent marked `stale` that itself has dependents does not propagate the cascade further automatically; revalidation of the staled dependent is what triggers any further consequence. This is a deliberate v1.1 boundary; transitive cascade depth and termination conditions are flagged as **OPEN-Q-031** (§21) for resolution when the first workload exercises a multi-level dependency graph under cancellation.

**Already-stale or already-cancelled dependents**: when the cascade encounters a dependent whose status is already `stale` or `cancelled`, the kernel **skips it silently**. No status mutation, no tier 3 event for that dependent. The cancellation event records the count of dependents actually transitioned (not the count walked), so the `affected_dependents` output reflects honest state changes. The audit-completeness alternative — emitting a tier 3 event for every dependent the cascade walked, including no-op skips — is flagged as **OPEN-Q-032** (§21) for resolution when observability tooling exposes a need.

**Pending op drop**: if any outside-call ops are queued (per §11) against the cancelled (I, R), the kernel drops them with `IR_CANCELLED` and emits a tier 3 event for each drop. The `dropped_pending_ops` count is reported in the output.

**Lease check**: cancelling an (I, R) under a held lease MAY be permitted by policy. Default behavior: the op rejects with `LEASE_HELD`. Policies can permit override via standing authorization for cancellation specifically.

**Policy evaluation**: standard policy evaluation phase. Cancellation policies MAY require explicit authorization (e.g., user-confirmation gate before cascading cancellation).

**Reversibility** (per BLOCK-4.5-SPEC-AMENDMENTS.md Amendment 4): cancellation is terminal. There is no "uncancel" op. Going forward from a cancelled (I, R) requires authoring a new (I, R) via `kernel.ir.new` (§3.2) with the optional `supersedes: <cancelled-id>` input field. The new (I, R) carries `status: open` and a frontmatter `supersedes:` pointer to the cancelled target; the cancelled (I, R) remains `status: cancelled` permanently and is not mutated by the new authoring. Both records persist; the lineage is unidirectional (new record points back at the cancelled target; cancelled target carries no forward pointer to its replacement). This asymmetry is intentional: cancelled records are immutable, and discovery of replacements is via index lookup on the new records' `supersedes:` field rather than a forward-pointer on the cancelled one.

**Files**: updates the cancelled (I, R)'s frontmatter; updates each cascaded dependent's frontmatter; writes one tier 3 cancellation event; writes one tier 3 event per dropped pending op; updates indexes.

**Errors** (per BLOCK-4.5-SPEC-AMENDMENTS.md Amendment 3 — `stale` dropped from `IR_NOT_CANCELLABLE`): `IR_NOT_FOUND`, `IR_ALREADY_CANCELLED`, `IR_NOT_CANCELLABLE` (status is `superseded`; supersede the new content instead), `CANCELLATION_AUTHORITY_INSUFFICIENT`, `LEASE_HELD`, `POLICY_DENIED`.

**Axioms**: 1, 3, 4, 6.

### 3.9 `kernel.ir.get`

**Purpose**: Read one (I, R) by id.

**Input**:
```json
{ "ir_id": "<id>",
  "depth": <int>|null,
  "valid_at": "<iso8601>"|null }
```

**Output**:
```json
{ "ir_id": "<id>",
  "frontmatter": { ... },
  "body": "<markdown-string>",
  "expanded_view": <opaque>|null,
  "collapsed_view": <opaque>|null }
```

**Atomicity**: read-only; no commit.

**Visibility**: respects scope visibility per axiom 3 and `visible_when` predicates per §4.5. (I, R)s the caller's scope cannot see return `IR_NOT_VISIBLE`.

**Depth**: if `depth: 0`, returns the collapsed view. If `depth: N`, returns the expanded view down to N levels of recursion. If `depth: null`, returns the (I, R)'s default view.

**Temporal filter**: if `valid_at: <iso8601>`, returns the version of the (I, R) that was valid at that timestamp (per axiom 4 supersession history).

**Errors**: `IR_NOT_FOUND`, `IR_NOT_VISIBLE`, `INVALID_DEPTH`.

**Axioms**: 1, 2, 3, 4.

### 3.10 `kernel.ir.list`

**Purpose**: List (I, R)s by filter.

**Input**:
```json
{ "scope": "<scope-id>"|null,
  "projection": "<projection-type-string>"|null,
  "tier": <int>|null,
  "domain": "<domain-string>"|null,
  "status": "<status-enum>"|null,
  "authored_by": "<string>"|null,
  "valid_at": "<iso8601>"|null,
  "include_kernel": <bool>,
  "include_cancelled": <bool>,
  "limit": <int>|null,
  "offset": <int>|null }
```

**Output**:
```json
{ "results": [<ir-summary>, ...],
  "total": <int>,
  "next_offset": <int>|null }
```

**Atomicity**: read-only.

**Visibility**: respects scope visibility and `visible_when` predicates.

**Defaults**: `include_kernel: false` (results from `_kernel` scope are excluded by default per v0.2 §4.2). `include_cancelled: false` (cancelled (I, R)s are excluded by default to avoid surprising callers; explicit opt-in to see them).

**Errors**: `INVALID_FILTER`, `SCOPE_NOT_FOUND`.

**Axioms**: 1, 3, 4.

### 3.11 `kernel.ir.deps`

**Purpose**: Return dependency edges for one (I, R) — both forward (what this (I, R) depends on) and reverse (what depends on this (I, R)).

**Input**:
```json
{ "ir_id": "<id>",
  "direction": "forward" | "reverse" | "both",
  "transitive": <bool> }
```

**Output**:
```json
{ "ir_id": "<id>",
  "forward": [<id>, ...],
  "reverse": [<id>, ...],
  "transitive_closure": <bool> }
```

**Atomicity**: read-only.

**Bounded propagation**: per axiom 3, transitive closure is bounded by scope visibility. The kernel does not enumerate the entire graph; it walks dependency edges within scope.

**Errors**: `IR_NOT_FOUND`, `INVALID_DIRECTION`.

**Axioms**: 1, 3.

### 3.12 `kernel.bridge.cross` — preserved as backward-compat path

**Purpose**: Cross a `_kernel.bridge`-defined bridge to outside compute. Preserved from v1.0.1-partial as a transitional path during the move toward bridges-as-PRISM-IR programs (§10).

**Input**:
```json
{ "bridge_id": "<id>",
  "resolver_id": "<id>",
  "for_ir_id": "<id>",
  "authorization_id": "<id>"|null,
  "payload": <opaque> }
```

**Output**:
```json
{ "response": <opaque>,
  "cost_actual": {
    "resolver_cost": { ... },
    "kernel_cost": { ... },
    "factory_cost": { ... }
  },
  "raw_payload_ref": "<path>"|null,
  "tier3_event_id": "<id>" }
```

**Atomicity**: best-effort with documented failure mode. `BRIDGE_UNREACHABLE` = no event written, no state change. `EVENT_WRITE_FAILED_AFTER_CROSSING` = outside contacted, event record lost; response payload returned in error context so caller can retry the event write.

**Three-cost decomposition**: v1.1 extends the v1.0.1-partial cost shape from a single-vector `cost_actual` to the three-vector decomposition per §6. Existing v1.0.1-partial single-vector events are migrated per §19.

**Status**: this op MAY remain in use indefinitely for `_kernel.bridge`-declared bridges. New bridge work SHOULD target `kernel.outside.http` (§11) authored as PRISM-IR programs (§10).

**Files**: writes one tier 3 event; optionally writes a sidecar payload file when policy enables; updates indexes.

**Errors**: `BRIDGE_NOT_FOUND`, `RESOLVER_NOT_FOUND`, `AUTHORIZATION_REQUIRED`, `BRIDGE_UNREACHABLE`, `EVENT_WRITE_FAILED_AFTER_CROSSING`, `OUTSIDE_CALL_DENIED` (when policy denies), `BUDGET_EXHAUSTED`, `RATE_LIMIT_EXHAUSTED`.

**Axioms**: 0 (inside/outside), 5, 6.

### 3.13 `kernel.authorize`

**Purpose**: Author an `_kernel.authorization` (I, R) granting permission for some action on some subject.

**Input**:
```json
{ "authorized_action": "<action-string>",
  "authorized_subject": <opaque>,
  "scope_of_authority": "single" | "session" | "until",
  "valid_through": "<iso8601>"|null,
  "cost_ceiling": { "clock_ms": <num>|null, "coin_usd": <num>|null, "carbon_g": <num>|null }|null,
  "conditions": <opaque>|null,
  "authored_by": "<author-string>",
  "authored_via": "<bridge-string>" }
```

**Output**:
```json
{ "authorization_ir_id": "<id>",
  "path": "<path>",
  "valid_through": "<iso8601>"|null,
  "tier3_event_id": "<id>" }
```

**Atomicity**: single-commit.

**Authority**: the granting party's authority MUST be at least equal to what the authorization grants. Hard-authority authorizations require hard-authority granters.

**Files**: writes one `_kernel.authorization` (I, R) under `ir/_ops/authorization/`; writes one tier 3 event; updates indexes.

**Errors**: `AUTHORITY_INSUFFICIENT`, `INVALID_SCOPE_OF_AUTHORITY`.

**Axioms**: 1, 4, 6.

### 3.14 `kernel.gatekeeper.check`

**Purpose**: Check whether an op is permitted against an authorization or policy. Read-only; no event emission.

**Input**:
```json
{ "action": "<action-string>",
  "subject": <opaque>,
  "caller": "<author-string>",
  "caller_roles": [<role-id>, ...]|null,
  "authorization_id": "<id>"|null,
  "context": <opaque>|null }
```

**Output**:
```json
{ "permitted": <bool>,
  "reason": "<string>",
  "authorization_used": "<id>"|null,
  "policy_used": "<id>"|null,
  "valid_through": "<iso8601>"|null }
```

**Atomicity**: read-only. Idempotent. No tier 3 event (the calling operation is the auditable record).

**Evaluation order**: explicit authorization (when supplied) → applicable policies (per §8) → role-based defaults → caller-or-higher authority defaults. First match wins; first deny short-circuits.

**Errors**: `BRIDGE_NOT_FOUND`, `RESOLVER_NOT_FOUND`, `AUTHORIZATION_NOT_FOUND`, `INVALID_ACTION`.

**Axioms**: 6.

### 3.15 `kernel.selector.select`

**Purpose**: Pick a resolver for an intention per axiom 5. Reads resolver capability and cost vectors, applies fitness function, optionally consults VOI, optionally honors holdout sampling.

**Input**:
```json
{ "ir_id": "<id>",
  "candidate_resolvers": [<resolver-id>, ...]|null,
  "consult_voi": <bool>,
  "honor_holdout": <bool> }
```

**Output**:
```json
{ "selected_resolver_id": "<id>",
  "depth_budget": <int>|null,
  "voi_consultation": <opaque>|null,
  "holdout_sampled": <bool>,
  "rationale": "<string>",
  "tier3_event_id": "<id>" }
```

**Atomicity**: single-commit. The selector authors a tier 2 `_kernel.resolver-selection` (I, R) recording the choice, with the VOI consultation embedded as a structured field per v1.0 §4.4.

**Authority**: kernel-internal. Selector authority is `convention` by default; sovereign override via standing authorization may set it to `hard` for specific scopes.

**v1.0 mechanics preserved**: VOI consultation per v1.0 §4, depth-budget selection for `cost_model: linear-in-depth` resolvers per v1.0 §2.1, calibration-policy holdout sampling per v1.0 §5.1, stakes-unknown defaulting to escalate per v1.0 §3.7.

**Files**: writes one `_kernel.resolver-selection` tier 2 (I, R); writes one tier 3 event with `voi_consultation` field per v1.0 §6.2; updates indexes.

**Errors**: `IR_NOT_FOUND`, `NO_CANDIDATE_RESOLVERS`, `RESOLVER_VECTORS_MISSING`, `VOI_CONSULTATION_FAILED`.

**Axioms**: 5.

### 3.16 `kernel.event.get`

**Purpose**: Read a tier 3 event by id.

**Input**:
```json
{ "event_id": "<id>" }
```

**Output**:
```json
{ "event_id": "<id>",
  "event": { ... } }
```

**Atomicity**: read-only.

**Visibility**: respects scope visibility. Events in scopes the caller cannot see return `EVENT_NOT_VISIBLE`.

**Errors**: `EVENT_NOT_FOUND`, `EVENT_NOT_VISIBLE`.

**Axioms**: 1, 3.

### 3.17 `kernel.reindex`

**Purpose**: Regenerate indexes from (I, R) records on disk. With `--check`, validate that on-disk records are schema-conformant and that indexes are consistent.

**Input**:
```json
{ "mode": "rebuild" | "check",
  "scope": "<scope-id>"|null }
```

**Output**:
```json
{ "indexes_rebuilt": [<index-name>, ...],
  "validation_errors": [<error-detail>, ...]|null,
  "tier3_event_id": "<id>"|null }
```

**Atomicity**: rebuild mode is single-commit per index. Check mode is read-only.

**Validation**: per v1.0.1-partial, `kernel.reindex --check` enforces presence of `authored_via` on every record. v1.1 extends validation to include the new base fields specified in §4 (`data_classification` validity if present, `domain` inheritance correctness, `visible_when` predicate parseability) and the status enum values from §5.

**Indexes**: regenerates the kernel's regenerable index set. The v1.1 index roster is the twelve indexes preserved from v1.0.1-partial (`id-to-path`, `path-to-id`, `scope-to-ids`, `tier-to-ids`, `projection-to-ids`, `temporal`, `deps-forward`, `deps-reverse`, `_checksum`, `resolver-to-events`, `calibration-corpus`, plus the bridges-and-resolvers index per v0.2) plus three v1.1 additions (`policy-evaluations` for cached policy results, `lease-holders` for current lease state, `payload-hash-to-events` for outside-call deduplication). All indexes are regenerable from (I, R) records on disk.

**Errors**: `SCHEMA_INVALID`, `INDEX_DRIFT_DETECTED`, `RECORD_UNREADABLE`.

**Axioms**: 1, 3, 4, 6.

---

## Section 4 — (I, R) frontmatter schema

This section specifies the base frontmatter schema every (I, R) carries. Projection-specific extensions are declared by each projection type per §7. Conflicts between base fields and projection extensions reject at write time.

The schema is additive over v1.0.1-partial: every v1.0.1-partial record is a valid v1.1 record. v1.1 adds three new optional base fields (`data_classification`, `domain`, `visible_when`) and extends the `status` enum (§5).

### 4.1 Base fields preserved from v1.0.1-partial

The following fields are preserved verbatim from v1.0.1-partial. Their semantics are unchanged.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique identifier within the repo. Slug shape; URL-safe. |
| `version` | string | yes | Semver version of the (I, R) record itself. |
| `kind` | string | yes | One of: `ir-node`, `foundational`, `derivation`, `amendment`, `entry-point`, etc. Free-form per project convention. |
| `tier` | int | yes | 1 (user-authored), 2 (kernel-authored from operations), or 3 (event ledger entry, not an (I, R)). |
| `projection_types` | list[string] | yes | Projection types this (I, R) conforms to. Validated against vendored body schemas. |
| `scope` | string | yes | Scope id this (I, R) lives in. |
| `authored_by` | string | yes | Author identifier (human, agent, or `kernel.self` for internal). |
| `authored_on` | iso8601 | yes | When the (I, R) was authored. |
| `authored_via` | string | yes | The bridge through which authorship entered the kernel. Required per v1.0.1-partial Amendment 2. |
| `authority_level` | enum | yes | `hard` \| `convention` \| `uncalibrated` per axiom 6. |
| `status` | enum | yes | Lifecycle state. v1.1 extends the enum per §5. |
| `resolved_at` | iso8601 | conditional | Required when `status: resolved`. |
| `valid_through` | iso8601 \| null | optional | Time horizon for revalidation per axiom 4. |
| `revalidate_trigger` | opaque \| null | optional | Event or condition that re-opens the (I, R). |
| `resolver` | string \| null | conditional | Resolver id; populated on resolution. |
| `resolution_event` | string \| null | conditional | Tier 3 event id of the resolution; populated on resolution. |
| `bridge_type` | string \| null | optional | Legacy field; superseded by `authored_via` per Block 2.7 Patch 5. Retained for backward compat. |
| `supersedes` | string \| null | conditional | Id of the (I, R) this one supersedes. |
| `superseded_by` | string \| null | conditional | Id of the (I, R) that supersedes this one. |
| `parent` | string \| null | conditional | Parent (I, R) id when this is a child of an expanded node. |
| `expanded_into` | list[string] \| null | conditional | Child (I, R) ids when this node has been expanded. |
| `collapsed_summary` | string \| null | optional | One-sentence summary used when this (I, R) is treated opaquely per axiom 2. |
| `depends_on` | list[string] | optional | Forward dependencies per axiom 3. |
| `visible_to` | list[string] | optional | Scopes (in addition to own scope) where this (I, R) is visible. |
| `surrogate_of` | string \| null | optional | Resolver id this (I, R) is a surrogate for, per axiom 7. |

### 4.2 New base field: `data_classification`

**Type**: string \| null
**Required**: optional
**Description**: Application-declared classification of the data this (I, R) carries. The kernel does not interpret the value; policies and skills do.

The kernel stores `data_classification` as an opaque string. Applications define their own classification taxonomy. Examples (illustrative, not normative): `pii-tokenized-fbb-v1`, `pii-raw`, `pii-free`, `confidential-internal`, `public`, `classified-tier-3`. The kernel does not enforce any specific taxonomy; it enforces only that policies referring to classifications find consistent values.

Policies (§8) MAY gate operations based on `data_classification`. A policy declaring "no `pii-raw` content may be written to scope X" enforces at `kernel.ir.new` and `kernel.ir.resolve` time. Skills (§9) MAY declare in their manifests that they handle only specific classifications.

When a record's `data_classification` is null, no classification-based policy applies. Some applications MAY enforce non-null classification through a write-time policy.

### 4.3 New base field: `domain`

**Type**: string \| null
**Required**: optional
**Description**: Domain the (I, R) operates in. Lifted from projection-extension to base in v1.1, closing OPEN-Q-019 from v1.0.1-partial's deferred list.

v1.0 introduced `applies_to_domain` on calibration policies, but `domain` itself was not a base field; calibration matching had to fall back to scope-only matching. v1.1 lifts `domain` to base frontmatter, parallel to `stakes` per v1.0 §2.3, enabling `applies_to_domain` matching for calibration policies and any future domain-scoped machinery.

**Inheritance**: follows the same pattern as `stakes`. If an (I, R) declares no `domain`, the kernel resolves it from `_kernel.scope` defaults if any are declared. If neither is declared, `domain` is null and domain-scoped policies do not match.

**Backward compat**: existing v1.0.1-partial records lack `domain`. They remain valid; `domain` is optional. Calibration policies that previously matched by scope-only continue to match by scope-only when records lack `domain`.

### 4.4 New base field: `visible_when`

**Type**: opaque predicate \| null
**Required**: optional
**Description**: Conditional visibility predicate evaluated by the kernel at read time. When non-null, the (I, R) is visible only to callers and contexts satisfying the predicate.

**Predicate shape**: a small expression evaluable against the calling context. v1.1 specifies the following predicate primitives:

```yaml
visible_when:
  any:
    - role: <role-id>
    - authority_level: <level>
    - scope: <scope-id>
    - caller: <author-string>
  all:
    - data_classification_at_most: <classification>
    - role: <role-id>
  not:
    - role: <role-id>
```

Predicates compose `any` (logical OR), `all` (logical AND), and `not`. Leaf predicates check role membership, authority level, calling scope, caller identity, and classification ordering (when classifications carry an ordering — purely application-defined).

**`not` semantics for multi-element arrays** (per BLOCK-4.5-SPEC-AMENDMENTS.md Amendment 6): `not: [a, b, ...]` is logically `not (a or b or ...)` — the kernel evaluates the array as a disjunction and negates the result. The composite is true when every child evaluates false (none-of-array semantics). Equivalently, `not: [a, b]` is interchangeable with `all: [{not: [a]}, {not: [b]}]` for binary cases; the `not:` shape is the canonical compact form.

The kernel evaluates predicates at `kernel.ir.get` and `kernel.ir.list` time. Records whose predicate is false return `IR_NOT_VISIBLE`. The predicate is also evaluated during dependency walks (`kernel.ir.deps`) — invisible (I, R)s are not surfaced in transitive closures even when on the dependency path.

**Authority**: hard-authored records MAY carry `visible_when` predicates; convention-authored records MAY NOT (the kernel rejects with `VISIBILITY_PREDICATE_NOT_PERMITTED`). The rationale: visibility predicates encode access control, which is sovereignty-shaped per v1.0 §0.2.

**Default**: when `visible_when` is null or absent, the record is visible per axiom 3 scope rules without further restriction.

### 4.5 Authority enforcement on the kernel scope

v0.2 §2.3 requires (I, R)s into the `_kernel` scope to carry `authority_level: hard`. v1.1 preserves this requirement. Foundational `_kernel`-scope records (the `_kernel` scope declaration, vendored projection-type definitions, vendored kernel-internal resolvers) are authorable only through the `kernel.self` bridge at bootstrap. After bootstrap, they are read-only except via supersession events authored by humans with hard authority through their own identity bridge.

### 4.6 Cogito and the kernel's authorship of its own self-knowledge

v0.2 §2.4 grounded the kernel's foundational sovereignty: the kernel authors records about its own physics through `kernel.self`, the cogito bridge. v1.1 preserves this verbatim. Internal kernel operations — `kernel.init`, `kernel.reindex`, migration scripts, kernel-authored cancellation cascade events — explicitly pass `authored_via: kernel.self`. The SDK boundary's default of `outside` does not apply to internal ops.

### 4.7 Validation discipline

The kernel validates frontmatter at write time (`kernel.ir.new`, `kernel.ir.resolve`, `kernel.ir.expand`, `kernel.ir.supersede`, `kernel.ir.promote`) and at maintenance time (`kernel.reindex --check`). Validation rejects records that:

- Lack any required base field
- Carry an `authored_via` that is empty or not a string
- Carry an empty string for any optional string base field (e.g., `domain`, `data_classification`); use `null` or omit the field to indicate the absence of a value (per BLOCK-4.5-SPEC-AMENDMENTS.md Amendment 1)
- Carry a `status` value not in the v1.1 enum (§5)
- Carry projection-extension fields not declared by the listed `projection_types`
- Carry conflicting projection-extension fields across multiple `projection_types`
- Reference a `scope` that does not exist
- Reference a `parent`, `supersedes`, or `depends_on` id that does not exist (or is not yet authored at this point in the dependency order)
- Carry a `visible_when` predicate that fails to parse
- Carry a `data_classification` value that conflicts with an applicable policy

Validation failures reject with a specific error code per §3 and §18.

**Resolution-helper convention (reference implementation)** (per BLOCK-4.5-SPEC-AMENDMENTS.md Amendment 5): helpers that resolve base-field inheritance (record-level → scope-default → null) are public-scoped, parallel to `resolve_domain` (§4.3) and `resolve_data_classification` (§4.2) in the reference implementation. Future optional base fields with scope-default inheritance follow the same shape and naming. This is reference-implementation guidance, not a contractual obligation on alternative kernel implementations.

### 4.8 Vendored projection body seal

Vendored projection bodies — the `body_schema` content shipped at `.8os/projections/_kernel/<type>.yml` — are owned by the kernel binary. They are **sealed for the lifetime of a single kernel version**: within a version, the bodies do not change. This discipline is folded in from v1.0.1-partial Amendment 3, which superseded Block 2.7's earlier "sealed at kernel ship" wording with the per-version seal articulated here.

**Refresh on version transition.** Bodies refresh during `kernel.init` upgrade-mode when the binary's version is newer than `.8os/version`. The refresh writes the binary's current vendored bodies to disk, replacing prior versions. Records already authored against prior bodies remain valid as long as the new bodies are additive-compatible: new optional fields are permitted; removed required fields and semantic redefinition of existing fields are not.

**Body amendments require a kernel version bump.** A patch to a vendored body without a version bump is a discipline violation. Two kernel binaries with the same version string MUST ship identical vendored bodies.

**v1.1 vendored body changes.** v1.1 introduces six new vendored projection bodies (`_kernel.lease`, `_kernel.role`, `_kernel.policy`, `_kernel.policy-evaluation`, `_kernel.skill`, `_simulation.alterverse-store`) and may extend existing bodies with optional fields per §7.7 (specifically the three-vector cost decomposition on `_kernel.tier3-event`). The migration in §19 lands these via the standard upgrade-mode refresh.

**Pre-release version strings.** Versions carrying pre-release tags (`1.0.2-dev.1`, `1.1.0-rc.1`) parse via the standard semver tolerance: pre-release tags compare equal at the numeric component for upgrade-mode dispatch, but the per-version-identity invariant is enforced by string equality. A binary at `1.1.0-dev.1` against a repo at `1.1.0` triggers upgrade-mode (the strings are not equal); a binary at `1.1.0` against a repo at `1.1.0` is a no-op.

---

## Section 5 — Status enum

The `status` field on every (I, R) takes one of five values. v1.1 extends the v1.0.1-partial four-value enum with one new value: `cancelled`.

### 5.1 The five values

| Value | Meaning | Set by | Terminal? |
|---|---|---|---|
| `open` | (I, R) is authored, not yet resolved. | `kernel.ir.new`, `kernel.ir.expand` (children) | No |
| `resolved` | (I, R) carries a resolution. | `kernel.ir.resolve` | No (can be superseded) |
| `superseded` | A newer (I, R) supersedes this one. | `kernel.ir.supersede` (sets the predecessor) | Yes (terminal for the superseded record) |
| `stale` | A dependency changed; this (I, R) needs revalidation. | Cascade from upstream change; `kernel.ir.cancel` cascade | No (revalidation possible) |
| `cancelled` | (I, R) is terminally cancelled. **NEW in v1.1.** | `kernel.ir.cancel` | Yes |

### 5.2 Lifecycle transitions

Permitted transitions:

- `open` → `resolved` (via `kernel.ir.resolve`)
- `open` → `superseded` (via `kernel.ir.supersede` on the predecessor)
- `open` → `stale` (via cascade from upstream change)
- `open` → `cancelled` (via `kernel.ir.cancel`)
- `resolved` → `superseded` (via `kernel.ir.supersede`)
- `resolved` → `stale` (via cascade)
- `resolved` → `cancelled` (via `kernel.ir.cancel`)
- `stale` → `resolved` (via `kernel.ir.resolve` after revalidation)
- `stale` → `superseded` (via `kernel.ir.supersede`)
- `stale` → `cancelled` (via `kernel.ir.cancel`)

Forbidden transitions (the kernel rejects):

- Anything → `open` (status only opens at authoring time)
- `superseded` → anything (terminal; supersession is forward-only)
- `cancelled` → anything (terminal; reversal is supersede-with-replacement, which authors a new (I, R) at `open`)

### 5.3 Cancellation as terminal

`cancelled` is terminal. Reversal is via supersede-with-replacement: author a new (I, R) carrying `supersedes: <cancelled-id>`. The new (I, R) is `status: open`; the cancelled (I, R) remains `cancelled` permanently. Both records persist; the supersession links them per axiom 6.

This is deliberately different from `superseded`. A superseded record's content was replaced by a newer version. A cancelled record's content was deemed wrong-to-have-existed; the cancellation is recorded honestly, and any forward path requires a new authoring event with explicit linkage to the cancelled record. The distinction matters for audit: a chain of supersessions reads as "we kept improving our answer"; a chain involving cancellation reads as "we explicitly retracted, then authored a different answer."

### 5.4 Backward compat

v1.0.1-partial records carry one of the four prior values: `open`, `resolved`, `superseded`, `stale`. No v1.0.1-partial record carries `cancelled`. v1.1 reading a v1.0.1-partial repo finds zero cancelled records, which is correct. Migration is the no-op described in §19.

---

## Section 6 — Three-cost decomposition

This section specifies the cost-decomposition contract every resolution event obeys. v1.1 splits the v1.0.1-partial single `cost_actual` vector into three vectors: `resolver_cost`, `kernel_cost`, `factory_cost`.

### 6.1 Why three vectors

The single-vector `cost_actual` shape from v1.0.1-partial conflates three distinct contributions: what the resolver itself consumed, what the kernel consumed servicing the operation (index updates, ledger writes, atomic-commit overhead, queue waits inside outside-call primitives, lease arbitration), and what the factory consumed (walker traversal, dispatch, adapter overhead, retry logic, factory-local queue management).

When the calibrator updates a resolver's capability vector by reading `cost_actual`, conflated cost contaminates the calibration: a resolver that ran cheaply in fast factory conditions and expensively in slow factory conditions appears to have variable cost when only the factory varied. Surrogate training corpora hit the same problem.

Three vectors solve the problem. The calibrator reads `resolver_cost` only. Surrogate training corpora pull from `resolver_cost` only. Factories reasoning about their own efficiency read `factory_cost`. The kernel's binary reasoning about its own overhead reads `kernel_cost`. Each component is honest about its own boundaries because each is the only one that can timestamp them.

### 6.2 The three components

**`resolver_cost`**: what the resolver itself consumed. Three currencies (clock_ms, coin_usd, carbon_g). For inside resolvers (deterministic computations, learned surrogates, rule-based heuristics), this is the wall-clock and resources of the resolver's logic. For outside resolvers (LLM bridges, external APIs, simulators), this is the cost of the outside call itself — tokens, API charges, network IO time, simulator runtime — not including queue wait or kernel overhead.

**`kernel_cost`**: what the kernel binary consumed servicing this operation. Three currencies. Includes index updates, ledger writes, queue waits inside `kernel.outside.http`, lease arbitration, atomic-commit overhead, policy evaluation. The kernel honestly reports its own time and cost because it is the only component that can timestamp its own boundaries.

**`factory_cost`**: what the factory consumed. Three currencies. Includes walker traversal, dispatch logic, resolver-output adapter work, retry and fallback handling, factory-local queue management, predictor pre-phase work that does not invoke the predictor itself. The factory reports honestly because, like the kernel, it is the only component that can see its own boundaries.

### 6.3 Sum without information loss

The three vectors sum cleanly to total cost without double-counting:

```
total_cost = resolver_cost + kernel_cost + factory_cost
```

For each currency. No information is lost in the decomposition; aggregation back to a total is always available. Reports that need only total cost compute it; reports that need component analysis read the components.

### 6.4 Calibration reads resolver_cost only

The calibrator's update logic for resolver capability vectors reads `resolver_cost` only. v1.0's `_kernel.capability-update` mechanism (extended in v1.1 to include cost-vector updates per v1.0 §5.2) reads exclusively the resolver-cost component. This isolates resolver characterization from kernel and factory variability.

### 6.5 Surrogate training reads resolver_cost only

Per axiom 7, surrogate training corpora pull from operational history. v1.1 commits that surrogate training corpora include `resolver_cost` only when computing the cost-vector field for trained surrogates. Surrogates approximate their predecessor resolvers; the predecessor's resolver-cost is the relevant comparison, not the conflated total.

### 6.6 Cost on outside-call primitives

`kernel.outside.http` (§11) emits the same three-vector cost decomposition. `resolver_cost` covers the outside call's cost (the LLM API charge, the network IO, the external service's billable units). `kernel_cost` covers the kernel's queue management and event emission. `factory_cost` covers the factory's contribution (typically zero for direct outside calls, non-zero when the factory adds adapter or retry work).

### 6.7 Migration from single-vector cost_actual

v1.0.1-partial records carry single-vector `cost_actual`. v1.1 migration treats the v1.0.1-partial value as `resolver_cost` with `kernel_cost` and `factory_cost` set to zero. This is honest about what the v1.0.1-partial records measured (resolver cost, primarily, with kernel and factory overhead absorbed into the single number) without claiming retroactive decomposition the data does not support. New v1.1 records carry the three-vector shape.

Calibrators reading mixed v1.0.1-partial-shape and v1.1-shape records work consistently: both shapes expose `resolver_cost`, and the v1.0.1-partial shape's `kernel_cost` and `factory_cost` zero values do not bias the calibration math against newer records.

### 6.8 Discipline expectations

The kernel records what the components report. It does not enforce that components honestly attribute their work; that is a discipline matter, not an enforcement matter. A factory that reports `factory_cost: zero` when it actually consumed real time is making an honesty error; the kernel records what it was told. Detection of dishonest reporting is a userspace observability concern.

The kernel does enforce that the three components are present and well-formed (three currencies each, non-negative numeric values). Operations passing malformed cost decomposition reject with `COST_DECOMPOSITION_INVALID`.

---

## Section 7 — Projection types

This section specifies the eighteen projection types v1.1 ships. Twelve are preserved verbatim from v1.0.1-partial; six are new in v1.1.

The eighteen are:

**Five v0.2 configuration projections (preserved):**
- `_kernel.scope`
- `_kernel.projection`
- `_kernel.resolver`
- `_kernel.bridge` (preserved as backward-compat per §10)
- `_kernel.surrogate-lineage`

**Four v0.2 operation-output projections (preserved):**
- `_kernel.tier3-event`
- `_kernel.authorization`
- `_kernel.resolver-selection`
- `_kernel.capability-update`

**Three v1.0 prediction-economics projections (preserved):**
- `_kernel.prediction`
- `_kernel.calibration-policy`
- `_kernel.calibration-policy-proposal`

**Six v1.1 projections (new):**
- `_kernel.lease`
- `_kernel.role`
- `_kernel.policy`
- `_kernel.policy-evaluation`
- `_kernel.skill`
- `_simulation.alterverse-store`

Specifications for the twelve preserved projections from v1.0.1-partial are unchanged in v1.1; readers needing detail SHOULD consult v1.0 §3 (prediction-economics types) and the v0.2 spec §3 (configuration and operation-output types). v1.1's only modification to preserved types is that those that produce cost-bearing events use the three-vector decomposition per §6.

The six new projections are specified below in full.

### 7.1 `_kernel.lease`

**Purpose**: Represent multi-writer coordination claims. A lease declares that a specific holder (factory id, process id, human author) has acquired write rights against a specific scope or (I, R) for a bounded time window. Other writers respect the lease.

**Projection-declared frontmatter extensions**:

- `lease_id: <slug>` — must equal the (I, R)'s `id`.
- `lease_for: <scope-id>` \| `<ir-id>` — the scope or specific (I, R) the lease covers.
- `held_by: <holder-string>` — the lease holder's identifier. Format: `factory:<factory-id>`, `process:<process-id>`, `author:<author-string>`.
- `lease_purpose: write` \| `read` \| `exclusive` \| `shared` — what the lease grants. `write` and `exclusive` are mutually exclusive with concurrent leases on the same target; `read` and `shared` permit concurrent leases of the same purpose.
- `acquired_at: <iso8601>` — when the lease was acquired.
- `valid_through: <iso8601>` — base axiom-4 field; lease expires at this time. Operations against an expired lease fail with `LEASE_EXPIRED`.

**Body shape**: free-form prose describing the lease purpose, optional. Most leases will be ephemeral and carry minimal body.

**Authority**: `convention`. Leases are coordination state; they do not bind sovereignty-level decisions.

**On-disk location**: `ir/<scope>/_leases/<lease-id>.md`. Filename suffix `.lease.md`.

**Bootstrap**: `kernel.init` creates no leases. They emerge from factory activity.

**Lifecycle**: leases expire automatically at `valid_through`. Explicit release authoring a supersession with `status: superseded` is OPTIONAL — the kernel treats expired leases as released. There is no separate `kernel.lease.release` op; supersession or expiration suffices.

### 7.2 `_kernel.role`

**Purpose**: Represent a role-based access control role. A role grants a list of permissions to its holders. Roles are referenced by policies (§7.3) and by `visible_when` predicates (§4.4).

**Projection-declared frontmatter extensions**:

- `role_id: <slug>` — must equal the (I, R)'s `id`.
- `grants: [<permission-tag>, ...]` — list of permission tags the role confers. Permission-tag shape is application-defined; common patterns include `kernel.ir.cancel:scope=<scope-id>`, `policy.write:scope=<scope-id>`, `skill.install:scope=<scope-id>`.
- `holders: [<author-string>, ...]` — list of authors holding the role.

**Body shape**: prose describing the role's purpose, recommended for non-trivial roles.

**Authority**: `hard`. Role definitions bind access control across the project; they require hard authority for authoring and supersession.

**On-disk location**: `ir/<scope>/_roles/<role-id>.md`. Filename suffix `.role.md`.

**Bootstrap**: `kernel.init` creates no roles. Applications author them.

### 7.3 `_kernel.policy`

**Purpose**: Represent a policy that gates kernel operations. A policy declares which ops it applies to, under what conditions, and what decision (allow / deny / transform / defer / follow-up) it makes.

**Projection-declared frontmatter extensions**:

- `policy_id: <slug>` — must equal the (I, R)'s `id`.
- `applies_to_op: [<op-name>, ...]` — list of kernel operations the policy gates. Examples: `kernel.ir.new`, `kernel.ir.cancel`, `kernel.outside.http`.
- `applies_to_scope: <scope-id>` \| `null` — scope restriction. Null means all scopes.
- `applies_to_classification: <classification-string>` \| `null` — classification restriction. Null means all classifications.
- `condition: <predicate-or-resolver-id>` — a predicate evaluable by the kernel, or a resolver id whose evaluation produces the policy decision. Resolver-evaluated policies use the kernel's standard dispatch path; the resolver is itself an (I, R) and can be calibrated, surrogated, and superseded.
- `decision: allow` \| `deny` \| `transform` \| `defer` \| `follow-up` — the decision the policy enacts when its condition matches.
- `transform_action: <opaque>` \| `null` — when `decision: transform`, the modification applied to the op's input or output.
- `defer_to: <role-id>` \| `null` — when `decision: defer`, the role authorized to override.
- `follow_up_action: <opaque>` \| `null` — when `decision: follow-up`, the action the kernel queues after permitting the op (e.g., notify a human reviewer).

**Body shape**: prose describing the policy's purpose, recommended.

**Authority**: `hard`. Policies bind kernel behavior across many operations.

**On-disk location**: `ir/<scope>/_policies/<policy-id>.md`. Filename suffix `.policy.md`.

**Bootstrap**: `kernel.init` creates no policies. Applications author them.

**Evaluation order**: when multiple policies apply to a single op, the kernel evaluates in author order (oldest first), short-circuiting on the first `deny` and accumulating `transform` and `follow-up` actions. The evaluation produces a `_kernel.policy-evaluation` record (§7.4) cached against the op's signature.

### 7.4 `_kernel.policy-evaluation`

**Purpose**: Cache the result of a policy evaluation. The kernel writes one policy-evaluation record per op-signature it evaluates; subsequent identical ops can skip re-evaluation if the cached result is still valid.

**Projection-declared frontmatter extensions**:

- `evaluation_id: <slug>` — must equal the (I, R)'s `id`.
- `op_signature: <hash>` — hash of the op name + input parameters that triggered the evaluation. Cached results are keyed by this hash.
- `policies_consulted: [<policy-id>, ...]` — policies that were evaluated.
- `decision: allow` \| `deny` \| `transform` \| `defer` \| `follow-up` — combined decision.
- `transform_actions: [<opaque>, ...]` — accumulated transform actions if any.
- `follow_up_actions: [<opaque>, ...]` — accumulated follow-up actions if any.
- `evaluated_at: <iso8601>` — when the evaluation occurred.
- `valid_through: <iso8601>` \| `null` — base axiom-4 field. Cache TTL.

**Body shape**: prose with policy reasoning, optional.

**Authority**: `convention`. Policy evaluations are operation-output records.

**On-disk location**: `ir/_ops/policy-evaluation/<evaluation-id>.md`. Filename suffix `.evaluation.md`.

**Bootstrap**: `kernel.init` creates no evaluations.

### 7.5 `_kernel.skill`

**Purpose**: Represent an installed skill. Skills are declarative manifests; their behavior is bounded by what the manifest declares. Per §9, skills are PRISM-IR programs that compose the kernel's primitives; the `_kernel.skill` projection is the manifest record, not the program itself.

**Projection-declared frontmatter extensions**:

- `skill_id: <slug>` — must equal the (I, R)'s `id`.
- `skill_source: <url-or-path>` — where the skill came from (URL, package registry id, local path).
- `skill_version: <semver>` — version of the skill manifest.
- `skill_author: <author-string>` — who authored the skill.
- `manifest_signature: <hash>` — cryptographic signature of the manifest, optional but RECOMMENDED. Applications MAY require signed manifests via policy.
- `declared_capabilities: [<capability-tag>, ...]` — the operations the skill declares it will perform. Examples: `kernel.ir.new`, `kernel.outside.http:domain=example.com`.
- `required_authorizations: [<auth-id>, ...]` — authorizations the skill requires to operate. Skills cannot operate without their declared authorizations.
- `prism_ir_program: <ir-id>` — reference to the PRISM-IR program (I, R) that implements the skill's behavior.
- `installation_scope: <scope-id>` — the scope the skill is installed in. Capabilities visible only to that scope.
- `lifecycle_status: installed` \| `suspended` \| `revoked` — current lifecycle state. `installed` is operational; `suspended` is paused (kernel rejects ops by this skill); `revoked` is terminal (the skill's records are eligible for cancellation cascade).

**Body shape**: prose describing the skill's purpose, recommended.

**Authority**: caller authority for installation; `hard` for revocation. A skill may be installed by any author with appropriate role; revocation requires hard authority via a policy-mediated authorization.

**On-disk location**: `ir/<scope>/_skills/<skill-id>.md`. Filename suffix `.skill.md`.

**Bootstrap**: `kernel.init` creates no skills. Applications author them at install time.

**Install discipline**: installation validates the manifest against installation policies (e.g., signature requirement, declared-capability whitelist), evaluates required authorizations, writes the skill's (I, R) records into the kernel. **No code runs at install.** Per §9, the skill's behavior is bounded by its PRISM-IR program; loading a skill never executes arbitrary code.

**Revocation**: a `_kernel.policy` revoking a skill cascades cancellation through the skill's installed (I, R)s. The skill's `lifecycle_status` transitions to `revoked`; subsequent operations attributed to the skill reject. Provenance is preserved — the cancelled records remain in the ledger with full audit trail.

### 7.6 `_simulation.alterverse-store`

**Purpose**: Meta-projection naming a runtime-hosted Alterverse store. Per §15, the Alterverse — the tree of all simulation timelines — is hosted by the runtime, not by the kernel ledger. The kernel hosts this meta-projection so the runtime's Alterverse store has a kernel-side anchor: identity, scope, format, retention.

**Projection-declared frontmatter extensions**:

- `store_id: <slug>` — must equal the (I, R)'s `id`.
- `store_scope: <scope-id>` — the scope this Alterverse store covers.
- `store_format_version: <semver>` — version of the runtime's Alterverse store format.
- `current_branch: <branch-id>` — current active branch in the store.
- `root_branch: <branch-id>` — root branch (the initial timeline).
- `store_path: <path-or-url>` — where the store lives. Local path or runtime-managed URL.
- `replay_policy: <opaque>` \| `null` — runtime-defined replay discipline.
- `retention_policy: <opaque>` \| `null` — runtime-defined retention discipline.

**Body shape**: prose describing the simulation context, recommended for non-trivial stores.

**Authority**: caller authority. Alterverse stores represent simulation work; convention authority is typical.

**On-disk location**: `ir/<scope>/_simulation/<store-id>.md`. Filename suffix `.store.md`.

**Bootstrap**: `kernel.init` creates no Alterverse stores. Runtimes author them.

**Cross-reference shape**: real bridge crossings during simulation appear in both the kernel ledger (as tier 3 events) and the Alterverse store (as runtime events), linked by event ID. The kernel does not enforce the cross-reference; the runtime is responsible for maintaining it. The kernel exposes the meta-projection so applications can query "which Alterverse stores cover this scope" and "what is the current branch of this store" through standard kernel queries.

### 7.7 Backward compat with v1.0.1-partial projections

The twelve preserved projection types are unchanged in their schemas. v1.1 reading a v1.0.1-partial record finds compliant records. Two extensions on preserved types:

- **`_kernel.tier3-event`** records may carry the three-vector cost decomposition per §6.7. v1.0.1-partial single-vector events are read as `resolver_cost` with zero kernel and factory components.
- **`_kernel.bridge`** is preserved unmodified as the backward-compat path. New bridge work targets `kernel.outside.http` per §11 and bridges-as-PRISM-IR per §10.

---

## Section 8 — Governance: roles, policies, policy evaluation

This section specifies the governance machinery v1.1 introduces: how roles confer permissions, how policies gate kernel operations, and how the kernel evaluates policies against ops at runtime. The projection types involved (`_kernel.role`, `_kernel.policy`, `_kernel.policy-evaluation`) are specified in §7; this section specifies how they compose.

### 8.1 What governance is for

Without governance machinery, every kernel operation either succeeds for any caller with sufficient authority or fails. There is no middle ground — no "this op is permitted but only after a human reviews," no "this op is permitted but the payload must be transformed first," no "this op is permitted only if the data classification matches a whitelist." v1.0.1-partial relied on authority levels alone, which is sufficient for a single-author project but insufficient for multi-factory deployments where different factories operate with different trust levels and applications need to enforce decisions like "no PII to outside calls" or "skill X cannot author records in scope Y."

v1.1 adds policies as first-class kernel content. Policies are (I, R) records (`_kernel.policy`); they are queryable, auditable, and superseded through the standard supersession discipline; they bind kernel operations through an evaluation phase the kernel runs on every op that has applicable policies.

Roles are the access-control primitive policies reference. A role `payroll-admin` confers permissions like `kernel.ir.cancel:scope=payroll` (the role's holder can cancel (I, R)s in scope `payroll`). Policies refer to roles when their decisions depend on caller identity (e.g., "deny `kernel.ir.cancel` unless caller holds `payroll-admin`").

### 8.2 Roles

Roles are declarative grants of permissions. A `_kernel.role` (I, R) carries:

- A `role_id`
- A list of permission tags it grants (`grants:`)
- A list of holders (`holders:`)

Permission tags are application-defined strings. The kernel does not interpret their structure; it matches them as opaque strings against policy conditions. Common patterns include `<op-name>:scope=<scope-id>` (an op-and-scope tag), `<op-name>:classification=<classification>` (an op-and-classification tag), or domain-specific tags applications invent.

The kernel uses roles in two places:

- **Policy conditions** (§8.3) reference roles to gate ops by caller identity.
- **`visible_when` predicates** (§4.4) reference roles to gate visibility by caller identity.

Roles are hard-authority records. A role's holders list is sovereignty-shaped: who holds what role binds access control across the project. Adding a holder requires hard-authority supersession of the role record. The kernel rejects convention-authored role authoring or supersession with `AUTHORITY_INSUFFICIENT`.

### 8.3 Policies

Policies are conditional decisions about kernel operations. A `_kernel.policy` (I, R) declares:

- Which operation(s) it gates (`applies_to_op:`)
- Optional scope and classification restrictions
- A condition (predicate or resolver reference)
- A decision (`allow`, `deny`, `transform`, `defer`, `follow-up`)
- Optional transform/defer/follow-up parameters

When a kernel operation is invoked, the kernel queries for policies matching the op-name. For each matching policy, it evaluates the condition. The condition can be either:

- **An inline predicate** — a small expression evaluable by the kernel against op inputs and caller context. Predicates compose `any` / `all` / `not` over leaf checks (caller role, authority, scope, classification, payload signature).
- **A resolver reference** — the id of a `_kernel.resolver` (I, R) whose dispatch evaluates the condition. This means a policy's condition can itself be a resolved (I, R) — the kernel uses its standard dispatch path to ask "should this op be permitted?" Resolver-evaluated policies inherit all the calibration, surrogation, and supersession discipline of any other resolver. A policy that says "consult resolver X" can be calibrated over time as X's predictions about op safety prove accurate or not.

Policies are hard-authority records. Authoring or superseding a policy requires hard authority through a sovereign's identity bridge, parallel to roles.

### 8.4 The five decisions

A policy's `decision:` field takes one of five values:

- **`allow`** — the policy permits the op. The kernel proceeds.
- **`deny`** — the policy refuses the op. The kernel rejects with `POLICY_DENIED`.
- **`transform`** — the policy permits the op with a modification. The `transform_action` field carries the modification (e.g., redact PII from payload before outside call, append audit metadata to record before write). The kernel applies the transform and proceeds with the modified op.
- **`defer`** — the policy refuses the op pending escalation. The `defer_to` field names a role authorized to override. The kernel rejects with `POLICY_REQUIRES_AUTHORIZATION` and includes the deferred role in the error context. A subsequent op carrying an authorization from a holder of the deferred role proceeds.
- **`follow-up`** — the policy permits the op and queues a follow-up action. The `follow_up_action` field carries the action (e.g., notify a human reviewer, schedule a recalibration check). The op proceeds; the follow-up is authored as a separate (I, R) the relevant party will act on.

The five decisions cover the full T&S action space discussed in the decisions log §13 (allow, deny, allow with limits, allow with caveats, allow with delay, defer to escalation, decompose-and-partial-action) without baking T&S into the kernel. T&S is application-level; the kernel's policy machinery is the mechanism applications use to enforce their T&S decisions.

### 8.5 Multi-policy evaluation

When multiple policies apply to one op, the kernel evaluates them in author order (oldest first). Evaluation short-circuits on the first `deny`. `transform` and `follow-up` decisions accumulate: an op may pick up multiple transforms and multiple follow-ups across the policy stack.

The accumulated decision is recorded as a `_kernel.policy-evaluation` (I, R) (§7.4), keyed by a hash of the op name and input parameters. Subsequent identical ops can read the cached evaluation when its `valid_through` has not elapsed, skipping re-evaluation. Cache invalidation is automatic via TTL; explicit invalidation is via supersession of the policy record (which writes a tier 3 event the kernel uses to invalidate cached evaluations referencing that policy).

### 8.6 Policy evaluation phase on every op

The kernel runs a policy evaluation phase on every op that has applicable policies. The phase executes between authority check and atomic commit:

1. **Authority check** — caller's `authority_level` against op requirements.
2. **Lease check** — any `_kernel.lease` records protecting the target.
3. **Policy evaluation phase** — query policies, evaluate conditions, accumulate decisions.
4. **Classification check** — when `data_classification` is involved.
5. **Atomic commit** — the op's writes complete together, or none of them do.

Steps 1-4 fail before commit. Step 5 succeeds atomically.

Operations with no applicable policies skip step 3 entirely. The kernel does not invoke evaluation machinery when nothing matches; the cost of policy evaluation scales with policy count, not with op count.

### 8.7 Authoring policies safely

Policies bind kernel behavior; misauthored policies can deny legitimate ops. v1.1 specifies three discipline expectations applications SHOULD follow:

- **Test policies in a separate scope before promoting them.** A scope `<scope>-policy-staging` can host candidate policies; ops in that scope exercise them; once verified, the policy is superseded into the production scope.
- **Use `defer` over `deny` when uncertain.** A `defer` policy refuses ops without permanently blocking them; an authorized override can proceed. A `deny` policy is unconditional; recovering requires policy supersession.
- **Prefer resolver-evaluated conditions for complex logic.** Inline predicates are fast but limited in expressivity; resolver references are slow but expressive. For policies that depend on rich context (e.g., "deny outside calls during scheduled maintenance windows"), a resolver reference is more honest about its complexity than a sprawling inline predicate.

### 8.8 Cancellation by policy

Policies can be authored that gate `kernel.ir.cancel`. Examples:

- **Two-person discipline for high-stakes scopes**: a policy on `kernel.ir.cancel` for scope `production` with `decision: defer` and `defer_to: scope-admin`. The originating author cannot cancel alone; an admin must authorize.
- **Cooldown periods**: a policy with `decision: deny` for cancellations attempted within N hours of authoring, allowing the original author time to correct rather than cancel.
- **Cascade gating**: a policy with `decision: defer` when `cascade: true` and the cascade would affect more than M dependents, requiring explicit confirmation.

These are application choices. The kernel provides the machinery; applications compose policies that match their domain's needs.

---

## Section 9 — Skills as PRISM-IR programs

This section specifies skills: how they install, what they can do, how the kernel bounds them, and how they revoke. The projection type involved (`_kernel.skill`) is specified in §7.5; this section specifies how skills compose with the kernel's other primitives to produce manifest-bounded, auditable, revocable behavior.

### 9.1 What skills are for

A skill is a packaged program a user installs to extend their kernel's capabilities. Examples: a skill that authors recurring research briefings; a skill that drafts emails in a specific style; a skill that monitors a category of outside data and writes summaries. Skills are the user-visible unit of "things this kernel can now do that it couldn't before installation."

The architecture problem skills solve: how to install an extension that does meaningful work without inheriting the security failure modes of fetch-and-execute extension models. The OpenClaw and Moltbook patterns (load remote markdown, then execute) are structurally vulnerable to prompt injection and supply-chain attacks. v1.1 commits to a different model: skills are declarative PRISM-IR programs, bounded at runtime by what their manifest declares, auditable end-to-end.

### 9.2 Skills are PRISM-IR programs

A skill's behavior is a PRISM-IR program. The skill manifest (`_kernel.skill` per §7.5) references the program by id (`prism_ir_program: <ir-id>`). The PRISM-IR program lives as an (I, R) record under the skill's installation scope, with `projection_types: [prism-ir]` per the standard PRISM-IR hosting machinery.

What a skill does is what its PRISM-IR program does. The program declares nodes, edges, decisions, generators, surrogates — all the standard PRISM-IR vocabulary. When the skill runs, the runtime walks the program through the kernel's standard dispatch path. There is no separate "skill runtime"; the same factory that runs any other PRISM-IR program runs skills.

This means **skills cannot do anything PRISM-IR cannot express.** A skill's outside calls go through `kernel.outside.http` (§11), which is policy-gated and audit-logged. A skill's resolver invocations go through `kernel.selector.select` and standard dispatch. A skill's record authoring goes through `kernel.ir.new`, which is policy-gated and lease-checked. There is no privileged path; skills are userspace.

### 9.3 Manifest declarations bound runtime behavior

The skill manifest declares what the skill will do. Specifically, `declared_capabilities:` lists the operations the skill expects to perform, and `required_authorizations:` lists the authorizations the skill needs.

At runtime, the kernel enforces the manifest:

- **Outside calls are bounded.** If a skill's manifest declares `kernel.outside.http:domain=api.example.com` but the skill attempts to call `api.other.com`, the call rejects with `OUTSIDE_CALL_DENIED`. The policy enforcement happens in the standard policy evaluation phase (§8.6); a synthetic policy generated from the skill's manifest gates outside calls by domain.
- **Record authoring is bounded.** If a skill's manifest declares it authors records in scope `<skill-id>` only, attempts to write to other scopes reject with `POLICY_DENIED`.
- **Authorizations are bounded.** A skill cannot use authorizations beyond its declared `required_authorizations:`. The kernel rejects authorization references the manifest does not list.

The bounding is not a separate enforcement layer; it is the standard policy machinery applied to a synthetic policy generated from the manifest at install time. The synthetic policy is itself a `_kernel.policy` (I, R), authored at install time, with the skill's `_kernel.skill` (I, R) as its provenance. Applications can supersede the synthetic policy if the manifest needs revision (e.g., the skill version updated and now requires a new domain), but this requires hard authority and is auditable.

### 9.4 Installation

Installation is a sequence of kernel ops:

1. **Read the manifest.** The skill's `_kernel.skill` (I, R) is authored via `kernel.ir.new` with the manifest fields populated.
2. **Validate the manifest against installation policies.** Any `_kernel.policy` records that gate `kernel.ir.new` for projection type `_kernel.skill` evaluate. Common installation policies: signature requirement (`manifest_signature` MUST be present and valid), declared-capability whitelist (only certain capability tags are permitted), source whitelist (only manifests from approved sources install).
3. **Author the synthetic bounding policy.** The kernel authors a `_kernel.policy` (I, R) generated from the manifest's `declared_capabilities:` and `required_authorizations:`. This policy gates the skill's runtime behavior. The synthetic policy carries `authored_via: kernel.skill-install` (a distinct value from `kernel.self`, which is reserved for the cogito bridge per §4.6) so audit queries can distinguish kernel-derived policies from sovereign-authored ones; the manifest's `_kernel.skill` (I, R) is recorded as the policy's provenance source via `supersedes` chain or explicit cross-reference.
4. **Author required authorizations.** The kernel authors `_kernel.authorization` records the skill needs, with the skill's `_kernel.skill` (I, R) as provenance.
5. **Write the PRISM-IR program.** The skill's `prism_ir_program` (I, R) is authored via `kernel.ir.new` with `projection_types: [prism-ir]`.
6. **Set lifecycle status.** The skill's `lifecycle_status: installed` is set; the skill is operational.

**No code runs at install.** The PRISM-IR program is markdown-with-frontmatter authored as a kernel record. The kernel does not execute the program at install; the program runs only when invoked through the standard factory dispatch path. There is no `kernel.skill.install_and_execute`. There is no fetch-and-execute path. There is, structurally, no way for a skill's installation to do more than write records into the kernel.

This is the architectural answer to the OpenClaw failure mode. A malicious manifest cannot bootstrap to arbitrary code execution because there is no privileged execution path to bootstrap to. A malicious manifest could attempt to write malformed records, but the standard validation rejects malformed records; could attempt to claim capabilities it doesn't have, but the policy phase rejects ops that exceed declared capabilities; could attempt to social-engineer the installation policy itself, but the installation policy is a hard-authority record that requires sovereign authoring or supersession.

### 9.5 Runtime behavior

When a skill is invoked (typically by a user message or a scheduled trigger authored as a separate (I, R)), the factory dispatches its PRISM-IR program through the standard walking and dispatch machinery:

- Each node executes via `kernel.selector.select` + `kernel.ir.resolve` (or via `kernel.outside.http` for outside-call nodes).
- Each operation passes through the standard policy evaluation phase, where the synthetic bounding policy gates capabilities.
- Each event is recorded in the tier 3 ledger with `skill_id` as part of the event metadata. (The `skill_id` is a convention; per the decisions log §19.5, the kernel does not enforce it as a structured field, but factories adopting the convention enable downstream observability.)

The skill's behavior is fully observable. Every record it authors carries the skill's id in provenance. Every outside call it makes is in the ledger with payload hash and resolved authorization. Every cost it incurs is in the three-cost decomposition, attributable to the skill via the event metadata.

### 9.6 Revocation

A skill is revoked by authoring a `_kernel.policy` that revokes it. The revocation policy:

- Has `applies_to_op: [<every-op>]` for ops attributed to the skill (matched by skill_id event metadata)
- Has `decision: deny`
- Triggers cancellation cascade through the skill's installed (I, R)s

When the revocation policy is authored (hard authority required), the kernel:

1. Sets the skill's `lifecycle_status: revoked`.
2. Cancels the skill's `_kernel.skill` (I, R) via `kernel.ir.cancel` with `cascade: true`.
3. The cascade marks the skill's `prism_ir_program`, the synthetic bounding policy, and any authorizations the skill held as `cancelled` (terminally) or `stale` (per §3.8 cascade rules).
4. Subsequent ops attributed to the skill reject with `POLICY_DENIED` from the revocation policy, until the cascade completes and `IR_CANCELLED` errors take over.

Provenance is preserved. The revocation does not delete the skill's records; it marks them terminal. An audit query can reconstruct what the skill did, what it was authorized for, why it was revoked, and when. This is the architectural answer to the "we installed something then forgot about it" failure mode: revocation leaves a complete record of the skill's lifecycle.

### 9.7 Comparison with fetch-and-execute models

The OpenClaw / Moltbook pattern is: load remote markdown, then execute. The execution is opaque — the markdown becomes a prompt to an LLM, the LLM produces actions, the actions run. There is no manifest, no declared bound, no policy gate, no auditable record of what was permitted.

v1.1's skill model is structurally different:

- **Skills are declarative.** The PRISM-IR program is inspectable before running. A skill's behavior is what its program declares; there is no opaque execution.
- **Skills are bounded.** Manifests declare capabilities; the kernel enforces them.
- **Skills are scoped.** A skill installed in scope X has no visibility outside X unless its manifest declares cross-scope capabilities.
- **Skills are revocable.** A revocation policy cascades cancellation through the skill's records with provenance preserved.
- **Skills are auditable.** Every operation attributed to a skill is in the ledger with full cost decomposition, payload hash, and resolver provenance.

The launch differentiator framing in the decisions log §28.1 reads: "Architecture explicitly addresses the OpenClaw / Moltbook security failure mode: skills as declarative PRISM-IR programs, install-time policy gate, manifest-bounded runtime, scoped, revocable." This section specifies how the architecture delivers each of those properties.

---

## Section 10 — Bridges as PRISM-IR programs

This section specifies the v1.1 architectural commitment that bridges are PRISM-IR programs. The implication: every outside-call resolver in the kernel is itself an (I, R), inspectable, decomposable, auditable, and (eventually) surrogateable. The `_kernel.bridge` projection type is preserved as a backward-compat path during the transition; new bridge work targets the PRISM-IR-program model.

### 10.1 What changes

In v1.0.1-partial, a bridge is a `_kernel.bridge` (I, R) record naming a Python implementation under `src/eightos/bridges/`. The implementation is opaque to the kernel — when a bridge crosses, the implementation runs; the kernel records what came back. Bridges are first-class projection types but their behavior lives in code outside the kernel's introspection.

In v1.1, every bridge is a PRISM-IR program. The simplest bridge is a single-node program wrapping a Python function via `op: script`; a more elaborate bridge can decompose into nodes for authorization, request shaping, response parsing, and error handling — each visible in the (I, R) graph.

This makes bridges:

- **Inspectable** at the (I, R) level. A user can read the bridge's program before allowing it to be authored to their kernel.
- **Decomposable.** A bridge that wraps a complex outside protocol (multi-step authentication, retry-with-backoff, response paging) can express each step as a node, each of which is independently auditable.
- **Composable with the kernel's other primitives.** A bridge's nodes can invoke `kernel.outside.http` for the actual outside call, `kernel.ir.new` to author records, `kernel.gatekeeper.check` to verify authorization — all the standard machinery.
- **Surrogateable.** Per axiom 7, a bridge that has accumulated operational history can train a surrogate that approximates its behavior at lower cost. The surrogate is itself a PRISM-IR program; the substitution machinery is unchanged.

### 10.2 The Anthropic bridge as the worked example

The Anthropic bridge from Block 3 is the first real outside-contact bridge. v1.1 commits to reauthoring it as a PRISM-IR program. The reauthoring is implementation work; the spec commitment is that the bridge can be expressed as a PRISM-IR program without losing functionality.

Sketch of the reauthored shape (illustrative, not normative):

```yaml
prism: anthropic-bridge
version: 1.0.0
nodes:
  - id: validate-authorization
    t: task
    o: { op: kernel-op, op_name: kernel.gatekeeper.check }
  - id: shape-request
    t: task
    o: { op: script, ref: anthropic-shape-request }
  - id: outside-call
    t: task
    o: { op: kernel-op, op_name: kernel.outside.http }
  - id: parse-response
    t: task
    o: { op: script, ref: anthropic-parse-response }
edges:
  - from: validate-authorization
    to: shape-request
  - from: shape-request
    to: outside-call
  - from: outside-call
    to: parse-response
```

The Python implementations referenced by `op: script` (`anthropic-shape-request`, `anthropic-parse-response`) are leaf-level computations that don't themselves cross outside; the actual outside call is `kernel.outside.http` (§11), which receives a fully-shaped request and returns a response.

A reader inspecting this bridge can see exactly what it does: validates authorization, shapes a request, makes an HTTP call, parses the response. Each step is decomposable further if governance requires it.

### 10.3 Why this matters for governance

In v1.0.1-partial, a malicious or buggy bridge implementation could do anything Python can do — write to disk, make additional outside calls, exfiltrate data — and the kernel would record only the declared bridge crossing, not the additional work.

In v1.1, the bridge's PRISM-IR program declares every operation it performs. The kernel enforces that the program does only what it declares: outside calls go through `kernel.outside.http` and are policy-gated; record authoring goes through `kernel.ir.new` and is bounded by classification and policy. A bridge that attempts work its program does not declare fails through the standard policy machinery.

This composes with the skill model from §9. Skills are PRISM-IR programs; bridges are PRISM-IR programs. The architectural pattern is: **userspace extensions are PRISM-IR programs, bounded by policy, audited via the ledger.** Different categories of extension (skill, bridge, decomposer, custom resolver) share the same architectural shape and the same governance machinery.

### 10.4 Backward compat: `_kernel.bridge` preserved

The `_kernel.bridge` projection type is preserved unchanged in v1.1. Existing v1.0.1-partial bridges authored as `_kernel.bridge` records remain crossable via `kernel.bridge.cross` (§3.12). The transition to bridges-as-PRISM-IR is a migration over time, not a v1.1 cutover.

The two patterns coexist:

- **Legacy bridges** (`_kernel.bridge` records, crossed via `kernel.bridge.cross`) — supported indefinitely.
- **PRISM-IR bridges** — the new pattern; new bridge work SHOULD target this pattern.

A bridge migrated from legacy to PRISM-IR is superseded: the `_kernel.bridge` record's `superseded_by` points to the new bridge's PRISM-IR program (I, R); the new program's `supersedes` points back. The migration is per-bridge and incremental.

### 10.5 OPEN-Q-006 final resolution

OPEN-Q-006 asked where outside-contact code for `kernel.bridge.cross` lives. v1.0.1-partial's resolution placed bridge implementations under `src/eightos/bridges/` with the `_kernel.bridge` (I, R) referencing the implementation file. v1.1 supersedes that resolution: bridges live as PRISM-IR (I, R)s; their Python implementations (when used) live wherever the bridge program's `op: script` references point. No specific filesystem location is mandated for the implementation files; the PRISM-IR program declares the references, and the references are resolved by the runtime.

The decisions log §10.5 names this explicitly: "OPEN-Q-006 final resolution: bridges live as PRISM-IR (I, R)s; their Python implementations (when used) live wherever `op: script` references point." v1.1 closes OPEN-Q-006.

### 10.6 Implications for §11 outside-call governance

Bridges-as-PRISM-IR composes with §11's outside-call governance: the bridge's PRISM-IR program invokes `kernel.outside.http` as a leaf node, and `kernel.outside.http` carries the policy gates, payload hashing, and audit machinery. The bridge does not directly contact the outside; it composes the outside call through the kernel's outside-call primitive.

This is why §11 specifies `kernel.outside.http` as the canonical outside-call primitive rather than as one bridge among many: it is the leaf that every bridge composes, the place the kernel actually crosses to outside reality. Bridges layered above are composition, not new outside contact.

---

## Section 11 — Outside-call governance

This section specifies `kernel.outside.http` and the outside-call governance machinery. Outside-call primitives are specified separately from §3's seventeen SDK operations because axiom 0 — the inside/outside boundary — divides the kernel's surface into two categories per §0.2 and §2.4. Inside ops manipulate state the kernel owns; outside-call primitives cross a boundary the kernel observes but does not contain. The two categories share an SDK shape (op contract, atomicity, error codes, event emission) but are structurally distinct.

### 11.1 Why outside-call primitives are their own category

Inside ops are deterministic in their effects on kernel state: a successful `kernel.ir.new` produces a record, an event, and index updates. The kernel commits the work atomically; the result is reproducible from the input.

Outside-call primitives are not deterministic in this way. The kernel can shape the request, can decide whether to send it, can record what came back — but cannot guarantee what came back. The outside is sovereign over its own outputs (per v1.0 §0.2's bridge-sovereignty framing). The kernel's job is to record honestly: what was sent, what came back, what cost was incurred, what authorization permitted it.

This is structurally different from inside ops. Inside ops are about state; outside-call primitives are about boundary-crossing events. They deserve their own section because confusing them — treating an outside call as if it were a deterministic state mutation — invites bugs that erase the kernel's honesty about the inside/outside split.

### 11.2 `kernel.outside.http`

**Purpose**: Make a network call to an outside service. Records direction, target, payload, response, cost, authorization, and audit metadata. Replaces `kernel.bridge.cross` for new outside-call work; legacy `_kernel.bridge` records remain crossable via `kernel.bridge.cross` (§3.12) for the transition window.

**Input**:
```json
{ "direction": "outbound" | "inbound" | "bidirectional",
  "target_category": "network",
  "target_identifier": "<url-string>",
  "payload": <opaque>,
  "for_ir_id": "<id>",
  "authorization_id": "<id>"|null,
  "priority": <int>|null,
  "expires_at": "<iso8601>"|null,
  "store_payload_sidecar": <bool>|null }
```

**Output**:
```json
{ "response": <opaque>,
  "payload_hash": "<hash>",
  "response_hash": "<hash>",
  "cost_actual": {
    "resolver_cost": { ... },
    "kernel_cost": { ... },
    "factory_cost": { ... }
  },
  "queue_time_ms": <num>,
  "serve_time_ms": <num>,
  "sidecar_path": "<path>"|null,
  "tier3_event_id": "<id>" }
```

**Atomicity**: best-effort with documented failure mode, parallel to `kernel.bridge.cross`. `BRIDGE_UNREACHABLE` (or `OUTSIDE_UNREACHABLE` for non-bridge contexts) = no event written, no state change. `EVENT_WRITE_FAILED_AFTER_CROSSING` = outside contacted, event record lost; response returned in error context.

**Authorization**: requires `authorization_id` for any outside call gated by policy. The kernel verifies the authorization via `kernel.gatekeeper.check` before sending the request. Authorizations record who permitted the call, scope of authority, cost ceiling, and validity window.

**Priority and queue**: `priority` is an opaque integer the kernel passes to its outside-call queue scheduler. Higher integers are higher priority; the kernel does not interpret the integer beyond ordering. `expires_at` is the latest acceptable service time; the kernel drops queued calls whose `expires_at` has passed with `EXPIRES_AT_PASSED`.

**Payload hashing**: the request payload is hashed at queue time and recorded in `payload_hash`. The response payload is hashed at receipt and recorded in `response_hash`. Hashes enable deduplication ("we sent this before, the response is in cache"), drift detection ("the same request now produces different responses, the outside changed"), cache-as-resolver patterns, and forensic replay.

**Sidecar storage**: when `store_payload_sidecar: true` (and an applicable policy permits it), the full request and response payloads are stored as files referenced by `sidecar_path`. Default is off — payloads exist only as hashes in the event ledger. Specific scopes or destinations can require sidecar storage via policy (e.g., regulated workloads where the full payload must be retained for audit).

**Three-cost decomposition**: the same three-vector shape per §6. `resolver_cost` is the outside call's cost (API charges, network time, billable units). `kernel_cost` is the kernel's queue management and event-writing overhead. `factory_cost` is the factory's contribution.

**Files**: writes one tier 3 event with payload and response hashes; optionally writes a sidecar payload file under `.8os/payloads/<event-id>.{request,response}` when sidecar storage is enabled; updates indexes.

**Errors**: `OUTSIDE_UNREACHABLE`, `EVENT_WRITE_FAILED_AFTER_CROSSING`, `AUTHORIZATION_REQUIRED`, `OUTSIDE_CALL_DENIED` (policy denied), `BUDGET_EXHAUSTED` (cost ceiling exceeded), `RATE_LIMIT_EXHAUSTED` (rate limit hit), `EXPIRES_AT_PASSED` (queue cutoff elapsed), `CLASSIFICATION_VIOLATION` (payload classification incompatible with destination policy), `PAYLOAD_TOO_LARGE`.

**Axioms**: 0 (inside/outside), 4 (queue cutoff), 5 (cost), 6 (provenance and authority).

### 11.3 Direction, target category, and target identifier

`direction` distinguishes:

- `outbound` — the kernel initiates the call (typical case: LLM API request).
- `inbound` — the outside initiates the call (typical case: webhook delivery).
- `bidirectional` — long-lived connection with traffic in both directions (typical case: streaming).

`target_category` is `network` for `kernel.outside.http`. Future outside-call primitives (file IO, human consultation, simulator invocation) MAY introduce additional categories; v1.1 specifies only `network`.

`target_identifier` for network targets is a URL. The kernel does not interpret the URL beyond using it for policy matching and audit logging. Policies referring to specific domains or URL patterns enforce at evaluation time.

### 11.4 Audit shape

Every outside-call event records, at minimum:

- Direction (outbound / inbound / bidirectional)
- Target category (`network` for v1.1)
- Target identifier (the URL)
- Payload hash
- Response hash
- Resolved authorization (the `_kernel.authorization` (I, R) that permitted the call)
- Three-cost decomposition
- Queue time (how long the call waited before service)
- Serve time (how long the actual outside call took)
- Optional sidecar payload (gated by policy)

This audit shape answers governance questions cleanly:

- **Did we ever send classification X to outside service Y?** Query events filtered by `target_identifier` matching Y, `data_classification` of the for_ir_id matching X.
- **What URLs has any factory in this scope hit this week?** Query events filtered by scope, `target_category: network`, time window.
- **When the same prompt was sent across time, did the responses drift?** Query events grouped by `payload_hash`, compare `response_hash` over time.
- **Has this exact payload been crossed before? Can we cache?** Query events by `payload_hash`; if a recent matching event exists with acceptable validity, return its response.
- **Who authorized this outside call, and is the authorization still valid?** Query the `authorization_id` field, check `valid_through`.

The kernel exposes the data; userspace observability tools compose the queries.

### 11.5 Queue discipline

`kernel.outside.http` maintains an internal queue per (target_identifier, scope) pair. The queue serves calls in priority order (higher integer first) with FIFO within priority. Calls with `expires_at` set are dropped when their cutoff elapses, regardless of their queue position.

Queue state is not directly inspectable as an (I, R); the queue is implementation state of the kernel binary. Audit queries reconstruct queue history from tier 3 events: a queued event has a `queue_time_ms` recording how long it waited, and a dropped event has an explicit drop event with `EXPIRES_AT_PASSED`.

Multiple factories sharing a kernel share the queue. The kernel arbitrates priority across factories per the integer they pass; factories that lie about priority (claiming higher priority than they should) are detectable by queue analytics — a per-factory honesty observation.

### 11.6 Bridges as PRISM-IR programs invoking `kernel.outside.http`

Per §10, bridges are PRISM-IR programs. The actual outside call within a bridge program is a node with `op: kernel-op, op_name: kernel.outside.http`. The bridge's other nodes (request shaping, response parsing, retry logic, error handling) compose around the outside-call leaf without themselves crossing outside.

This composition is why bridges are not opaque: every outside call is a kernel-op invocation, recorded in the event ledger, gated by policy. A bridge cannot hide outside calls behind opaque Python; the calls are kernel ops, and kernel ops are auditable by definition.

### 11.7 Classification flow through outside calls

When an (I, R) carries `data_classification`, and that (I, R) is the source of a payload sent via `kernel.outside.http`, the kernel checks classification policies before sending. A policy declaring "no `pii-raw` content may be sent to `*.example.com`" rejects the call with `CLASSIFICATION_VIOLATION`.

Classifications can be transformed in flight via policy. A policy with `decision: transform` and a transform action that tokenizes PII can convert `pii-raw` to `pii-tokenized-fbb-v1` before sending; the call then proceeds. The transform itself is recorded in the audit trail, so an auditor sees: original classification, transform applied, transformed classification, payload hash post-transform.

This is the architectural answer to the "we accidentally sent PII to OpenAI" failure mode. The kernel's classification machinery composes with policy and outside-call gating to enforce data discipline at the boundary.

### 11.8 The non-network outside-call primitives

v1.1 ships only `kernel.outside.http` for `target_category: network`. Future outside-call primitives may include:

- `kernel.outside.file` for file IO
- `kernel.outside.human` for human consultation (already partly covered by the human bridge in v0.2; possibly subsumed)
- `kernel.outside.simulator` for simulator invocation
- `kernel.outside.cli` for shell commands

These are not specified in v1.1. They are flagged as future work per §20. The audit shape and policy machinery are designed to extend to them without breaking changes.

### 11.9 Why this is not the 18th SDK op

Per §0.2, outside-call primitives are a separate category from the seventeen SDK operations. Counting `kernel.outside.http` as the eighteenth op would flatten the inside/outside distinction the kernel was built around. The split is structural, not editorial.

A reader counting "what does the kernel expose" gets seventeen inside ops and a small number of outside-call primitives (currently one). The count separation reflects the architecture: the kernel's surface to its own state and the kernel's surface to outside reality are different surfaces. Both are SDK-shaped; both are auditable; they are not the same thing.

This framing also generalizes cleanly. As `kernel.outside.file`, `kernel.outside.human`, etc. land in future versions, they join the outside-call category without contaminating the inside-op count. The seventeen inside ops are the contract for kernel state; the outside-call primitives are the contract for boundary crossing. Two contracts, parallel in shape, distinct in intent.

---

## Section 12 — Decision-and-action separation

This section specifies how SLA, deadline, balk, renege, kill, substitute, and escalate are expressed in the v1.1 architecture. **None of these are new PRISM-IR grammar.** They are patterns composed from PRISM-IR's existing decision-node and edge-condition primitives plus the kernel's `expires_at` queue-cutoff mechanism. v1.1 commits to the cleavage explicitly: decisions live in PRISM-IR, actions follow from decisions, the kernel hosts both.

### 12.1 Why this section exists

A common request when designing process runtimes is "add SLA semantics" or "add timeout-and-retry as first-class grammar." The temptation is to introduce new vocabulary on the language side: `sla:`, `timeout:`, `balk_after:`, `kill_at:`, etc. v1.0's PRISM-IR specification carries an `sla:` field on nodes; the hard question is what runtime behavior follows.

v1.1 commits that **the language declares; the runtime decides; the kernel respects**. Specifically:

- PRISM-IR carries `sla:` as a **measurement target**, not as a behavioral mandate. A node with `sla: { latency_p95_ms: 500 }` declares the target; runtime measurement against the target produces a fact; decision nodes downstream of the target consume the fact and route accordingly.
- Behavioral patterns (balk, renege, kill, substitute, escalate) are expressed as **decision flows** in PRISM-IR using existing primitives: decision nodes, edge conditions, fail policies, and the `surrogates` block.
- The kernel exposes one primitive — `expires_at` on queue-able operations — that lets the language express queue cutoffs honestly.

This means PRISM-IR's grammar does not change to express SLA-like behavior. Existing v1.1 PRISM-IR (and v1.0 PRISM-IR before it) already has the vocabulary.

### 12.2 The action vocabulary mapped to existing primitives

The standard queueing-theory action vocabulary maps as follows:

- **Balk** — the factory chooses not to enqueue an outside call. Expressed as a decision node before the outside-call node, evaluating whether the queue's expected wait would exceed acceptable bounds. The decision routes to either the outside-call node or to a fallback (e.g., a surrogate, a cached response, an escalation node).
- **Renege** — a queued outside call is cancelled before service. Expressed via `expires_at` on `kernel.outside.http`; the kernel drops the queued call when `expires_at` elapses with `EXPIRES_AT_PASSED`. The PRISM-IR program's fail policy handles the drop.
- **Kill** — an in-flight outside call is aborted. Best-effort at the kernel level: `kernel.ir.cancel` on the parent (I, R) drops pending ops (per §3.8), but already-in-flight network calls cannot always be aborted cleanly. The kernel records the cancellation honestly; the cost is attributed regardless of abort success.
- **Substitute** — a different resolver is used than the one originally selected. PRISM-IR's `surrogates` block declares substitution candidates; the factory's selector chooses among them per axiom 5 and v1.0's selection mechanics. Substitution is the standard surrogate-substitution pattern from axiom 7, not a new primitive.
- **Escalate** — when a predictor's output is unsatisfactory, the candidate ground-truth resolver runs. Already specified in v1.0 §3.7 via VOI consultation and stakes. Escalation is built into the prediction-economics machinery, not a separate primitive.

### 12.3 The kernel primitive: `expires_at`

The kernel exposes `expires_at` as a base parameter on queue-able operations (currently `kernel.outside.http` per §11.2). The semantics are minimal: if the operation has not been served by `expires_at`, the kernel drops it with `EXPIRES_AT_PASSED`. The kernel does not interpret the meaning of the deadline ("it's a hard SLA," "it's a soft preference," "it's an escalation trigger") — it just respects the cutoff.

The PRISM-IR program supplies meaning. The language expresses the *process meaning* via decision nodes that route based on `EXPIRES_AT_PASSED` outcomes; the kernel just respects the timestamp.

This is the same pattern as v1.0's `priority` integer: opaque to the kernel, meaningful to the language. The kernel handles dispatch; the language handles semantics.

### 12.4 Why this stays in PRISM-IR (not the kernel)

The decisions log §21 marks decision-and-action separation as a **MUST-live-in-PRISM-IR** concern. The reasoning, restated: factory-internal decisions are un-decomposable, un-auditable, un-surrogateable. If a factory implements "if the LLM is slow, fall back to the cached response" as Python logic inside the factory, that decision is invisible to the kernel and to other factories. The fall-back path is not in any (I, R), so it cannot be calibrated, superseded, or replaced by a learned surrogate. Worse, two factories on the same kernel might implement the same decision differently, producing inconsistent behavior on the same workload.

The same decision expressed as a PRISM-IR decision node is in the (I, R) graph. It is auditable (the decision and its outcome are tier 3 events), calibrate-able (the decision's accuracy can be measured over time), supersede-able (the decision logic can be updated through kernel supersession), and surrogateable (the decision can eventually be replaced by a learned model per axiom 7).

This is why v1.1 does not add SLA semantics to the kernel. The kernel's job is to host the (I, R) graph honestly; the language's job is to express the process; the runtime's job is to walk the graph. Adding SLA semantics to the kernel would absorb language-level concerns into the substrate, defeating the cleavage.

### 12.5 What this means for spec authors

A PRISM-IR program author wanting "SLA-like" behavior writes:

- An `sla:` field on the node that declares the measurement target.
- Decision node(s) that read the measurement and route accordingly.
- Edge conditions that branch on outcomes (timeout, slow response, retry exhaustion).
- A `surrogates:` block declaring fallback resolvers.
- The standard fail policy on outside-call nodes.

No new PRISM-IR fields. No new kernel ops. The composition produces every SLA-like pattern the user might want, with full audit trail and surrogation potential.

If a workload surfaces a pattern that genuinely cannot be expressed with these primitives, that surfaces as a PRISM-IR amendment proposal — a language concern, not a kernel concern. The kernel stays minimal.

---

## Section 13 — Multi-factory architecture and lease coordination

This section specifies the v1.1 commitment to multi-factory deployments and the lease primitive that coordinates them. The reference implementation at v1.0.1-partial is single-writer-per-process; v1.1 names this as an implementation gap, not an architectural one. The kernel is multi-factory-capable at the spec level; subsequent implementation work lands the multi-factory binary.

### 13.1 What "multi-factory" means

A factory is a runtime that walks PRISM-IR programs and dispatches resolvers (§1.4). Multiple factories may run concurrently against the same kernel — different processes, different machines, possibly different organizations — all writing to the same (I, R) graph and reading the same tier 3 event ledger.

The use cases:

- **Performance**: parallel factories drain a backlog of pending (I, R) work faster than a single factory can.
- **Specialization**: one factory specializes in high-latency outside calls; another specializes in inside-resolver work; a third specializes in human-in-the-loop nodes.
- **Trust separation**: an organization runs factory A in a high-security environment for sensitive workloads and factory B in a lower-trust environment for public workloads, sharing the same kernel for unified audit.
- **Geographic distribution**: factories run in different regions for latency or compliance reasons.

In every case, the factories must coordinate without trusting each other to behave correctly. The kernel is the trusted middle.

### 13.2 What the kernel must enforce for multi-factory safety

Per the cleavage principle (§1.1), the kernel hosts anything mutually-distrusting factories cannot safely re-implement. For multi-factory deployments specifically, this means:

- **Identity uniqueness across writers.** Two factories attempting to author (I, R)s with the same id MUST result in exactly one success and one rejection. Race conditions cannot produce duplicate ids.
- **Lease arbitration.** When a factory acquires write rights against a scope or (I, R), other factories must respect the lease. The kernel rejects writes against held leases with `LEASE_HELD`.
- **Atomicity across the graph.** Per-op atomicity (§3) prevents partial writes; the cross-factory case adds the requirement that one factory's commit cannot be interleaved with another's mid-operation.
- **Honest cost attribution.** When two factories contribute to the same workload (e.g., factory A authors an (I, R), factory B resolves it), the three-cost decomposition (§6) attributes work to the correct factory.
- **Honest priority arbitration.** When two factories enqueue outside calls with priority integers, the kernel honors the integers honestly without per-factory bias.

These are kernel responsibilities at v1.1. The current binary at v1.0.1-partial implements only the single-writer case; the multi-factory binary lands as subsequent implementation work.

### 13.3 Leases as the coordination primitive

The lease primitive (`_kernel.lease` per §7.1) is the v1.1 mechanism for write coordination. The basic shape:

- A factory acquires a lease by authoring a `_kernel.lease` (I, R) with `lease_for: <scope-or-ir-id>`, `held_by: factory:<factory-id>`, `lease_purpose: write`, and a `valid_through` expiration.
- Other factories querying the kernel before write check for active leases on their target. An active lease held by another factory rejects their write with `LEASE_HELD`.
- The lease expires automatically at `valid_through`. The kernel does not auto-renew.
- Explicit release is via supersession; the lease's `status` becomes `superseded`. (Or the lease simply expires; both work.)

Lease acquisition itself is a write, so the kernel's identity-uniqueness invariant prevents two factories from simultaneously acquiring a lease for the same target: exactly one `kernel.ir.new` succeeds; the other fails with `ID_CONFLICT`.

### 13.4 Lease purposes

The `lease_purpose:` field takes one of four values:

- **`write`** — exclusive write access. While held, no other factory may write to the leased scope or (I, R). Other factories may read.
- **`read`** — shared read access. Multiple factories may hold concurrent `read` leases on the same target. Useful for snapshotting consistent views during analysis.
- **`exclusive`** — exclusive read and write. While held, no other factory may read or write the leased target. Useful for invariant-sensitive operations.
- **`shared`** — concurrent any-purpose access permitted; the lease records intent without enforcing exclusion. Useful as advisory state.

The kernel enforces `write` and `exclusive` semantics (rejecting conflicting concurrent leases); `read` and `shared` are coordination metadata without enforcement on read-only ops.

### 13.5 Lease scope: per-scope, per-(I, R), or finer

Leases name a target in `lease_for:`. The target can be:

- **A scope id** — locks the entire scope. Useful for batch operations that author many (I, R)s.
- **A specific (I, R) id** — locks one record. Useful for targeted edits like supersession or cancellation.
- (Future) **A path prefix or projection-type filter** — finer-grained locking. Not specified in v1.1.

A factory checking lease state queries the `_kernel.lease` records for both the target id and any parent scopes. A scope lease covers all (I, R)s in it; an (I, R) lease covers just that record. Conflicts are detected by the kernel during `kernel.ir.new`, `kernel.ir.resolve`, `kernel.ir.expand`, `kernel.ir.supersede`, and `kernel.ir.cancel` — the writes that would mutate state.

### 13.6 What the kernel does not do for multi-factory

The kernel does not:

- **Schedule across factories.** Each factory schedules its own work. The kernel hosts the result.
- **Arbitrate higher-level coordination.** Patterns like "factory A produces, factory B consumes" are factory-level coordination, not kernel-level. The kernel hosts the (I, R)s the factories use to coordinate (e.g., a queue (I, R), status flags); the factories implement the coordination.
- **Provide cross-factory transactions.** A multi-step workflow that needs all-or-nothing semantics across multiple factories is the workflow's problem, not the kernel's. The kernel offers per-op atomicity and lease-bounded mutual exclusion; richer transactional patterns compose from these.
- **Enforce priority fairness.** The kernel honors priority integers honestly, but if all factories pass the same priority (or all pass priority 999), the kernel does not impose its own fairness. Cross-factory priority discipline is an application concern.

### 13.7 The implementation gap

The v1.0.1-partial reference implementation is single-writer-per-process. The JSONL ledger, the filesystem layout, and the index-update machinery all assume one writer at a time. v1.1's multi-factory commitment requires:

- Lease records as `_kernel.lease` projection type with the policy-evaluation phase honoring them on every write op
- Atomic commit machinery that handles concurrent writers (file locks, database transactions, or equivalent)
- Index update mechanisms that don't race across writers
- The DuckDB storage migration (§16) which provides multi-writer transactional semantics

These land in subsequent implementation blocks. v1.1 is the architectural commitment; the binary catches up.

### 13.8 Bridge queues are kernel-level, not factory-level

Per §11, `kernel.outside.http` maintains an internal queue that serves outside calls in priority order. This queue is **kernel-level**, not factory-level: all factories sharing a kernel share the queue.

This is deliberate. If each factory had its own outside-call queue, two factories hitting the same external service would not coordinate their rate limits, would not deduplicate identical requests, and would not compose budget enforcement. Kernel-level queueing makes these governance properties tractable.

The trade-off: a slow outside service can become a contention point across factories. v1.1 accepts this trade-off because the audit and governance benefits outweigh the contention cost. Factories that want non-contended outside-call paths can use distinct target identifiers (e.g., separate API keys, separate endpoints) which then queue separately.

---

## Section 14 — Time and clocks

This section specifies how time is treated by the kernel: which clocks are used for which fields, what causal ordering looks like in a multi-factory deployment, and how application-level time (frames, branches, simulation clocks) is hosted without kernel interpretation.

### 14.1 Two kernel clocks

The kernel uses two clocks:

- **Wall-clock**, supplied by the operating system. Used for `resolved_at`, `valid_through`, `expires_at`, ULID generation, `authored_on`, and any other timestamp the kernel writes.
- **Monotonic-elapsed**, supplied by the operating system. Used for cost accounting (the time deltas inside `clock_ms`).

The kernel does not maintain its own clock service. Wall-clock skew across writers is the OS's concern; the kernel records what the OS supplied. Monotonic-elapsed cannot decrease, which makes it suitable for measuring durations even when wall-clock adjusts (NTP corrections, leap seconds).

### 14.2 ULIDs and timestamp ordering

(I, R) ids generated by the kernel use ULID format: lexicographically sortable, timestamp-prefixed. ULIDs are best-effort timestamp-ordered: within a single writer, newer ids sort later than older ids; across multiple writers, clock skew can produce out-of-order ULIDs.

The kernel tolerates this: replay tools and audit queries do not assume ULID ordering equals causal ordering. Causal ordering is established separately (§14.3).

### 14.3 Causal ordering via dependency edges and event-log sequence

Per axiom 3, the (I, R) graph carries explicit dependency edges (`depends_on`). Causal ordering across (I, R)s is established by these edges, not by timestamp comparison. An (I, R) that depends on another is causally downstream of it regardless of timestamp ordering.

For tier 3 events, the kernel maintains an event-log sequence number per writer (factory). Events from a single writer are ordered by sequence; events across writers are ordered by dependency edges where they exist, and partially-ordered otherwise.

This means: in a multi-factory deployment, two events from different factories may have indistinguishable causal ordering in the kernel ledger. The kernel does not impose a total order it cannot honestly defend. Tools that need a total order compute one downstream from the partial order plus tie-breaking rules they choose.

### 14.4 The kernel does not maintain a clock service

Some kernels run their own NTP-like clock service to synchronize across writers. v1.1 does not. The reasoning: clock synchronization is a real cost, and the kernel does not need synchronized clocks to function correctly. Causal ordering is by dependency edges; timestamps are advisory; queries that need monotonic time use monotonic-elapsed.

If a future deployment needs cross-factory clock synchronization (e.g., for forensic ordering of events that lack dependency edges), the application layer can compose it from the existing primitives. The kernel doesn't.

### 14.5 Application-level clocks

Beyond wall-clock and monotonic, applications often need other clocks:

- **Simulation clocks** — a Monte Carlo trial's frame time, advancing by sampled durations rather than wall-clock seconds.
- **Domain clocks** — business-day time, market-hours time, regulatory-clock time.
- **Logical clocks** — Lamport timestamps, vector clocks for distributed reasoning.

The kernel hosts these as frontmatter fields without interpreting them. An (I, R) carrying `frame_time: 1234.5` and `frame: mc-trial-7` is stored, queried, and returned as authored. The kernel does not advance the simulation clock; the runtime does. The kernel does not interpret the frame; the application does.

This is the same opinion-free pattern as currencies and authority levels (§0.1). The kernel knows there are clocks but doesn't pick them; applications declare what each clock means.

### 14.6 Frames and branches

Two specific application-time annotations are common enough to warrant explicit naming:

- **Frames** are simulation-time coordinate systems. A Monte Carlo trial's records carry `frame: mc-trial-7`; a discrete-event simulation jumping to its next scheduled event carries the new `frame_time`. Frames make multiple parallel simulation timelines distinguishable in a single (I, R) graph.
- **Branches** are alternate timelines. A counterfactual simulation diverging from a backup point carries a new `branch_id` referencing its parent. Branches enable the Alterverse pattern (§15) where multiple "what-if" simulations coexist.

Multiple frames and branches can coexist in a single (I, R) graph. The kernel hosts them without interpretation; the runtime is the timekeeper for any frame.

### 14.7 Frame and branch identity

Frame and branch IDs live in the Alterverse store (§15), not in the kernel-indexable id space. The kernel can store `frame:` and `branch_id:` as frontmatter fields on (I, R) records, but it does not maintain a `frame-id-to-ids` index or a `branch-id-to-ids` index. The runtime maintains those mappings in the Alterverse store; the kernel hosts the meta-projection (§7.6) that names the store.

This is a deliberate cleavage: frames and branches are runtime concerns that change rapidly during simulation; indexing them in the kernel would impose write-amplification on hot paths the simulation runtime can manage more cheaply in its own store.

### 14.8 Half-life and freshness models

v1.1 does not specify a half-life mechanism on (I, R)s. Applications that need freshness modeling declare it via frontmatter:

```yaml
freshness_model:
  kind: half-life | linear-decay | step-function
  clock: wall | frame | <domain-clock>
  params: { ... }
```

Freshness resolvers are then registered to consume the frontmatter and produce freshness scores. The kernel does not interpret `freshness_model:`; it stores the field and lets domain-specific resolvers reason about it.

This composes with axiom 4's `valid_through`: a record with `freshness_model: kind: half-life` and `valid_through: <timestamp>` decays continuously per the model and becomes invalid abruptly at the timestamp. Either, both, or neither may be present.

---

## Section 15 — Alterverse hosting

This section specifies the v1.1 commitment that the Alterverse — the tree of all simulation timelines — is hosted by the runtime, not by the kernel ledger. v1.1 corrects PRISM-IR v1.1's framing of the Alterverse as a filter view over the kernel ledger; the corrected framing lands in PRISM-IR v1.2 as an additive amendment. This section specifies the kernel side; the language side is in PRISM-IR v1.2 when it publishes.

### 15.1 What the Alterverse is

The Alterverse is the tree of all simulation timelines a runtime hosts. A simulation runs through a PRISM-IR program, generating events as tokens are created, nodes are entered, edges are taken, branches are forked, phase boundaries are crossed, and metrics are updated. A counterfactual simulation can fork at any backup point and produce a different timeline. The set of all such timelines, organized as a tree of branches, is the Alterverse.

The PRISM-IR v1.1 specification framed the Alterverse as "a query over the kernel's tier 3 event ledger filtered by flow identity" (PRISM-IR v1.1 §1.4). v1.1 of Block 1 corrects this: the kernel ledger and the Alterverse store are different stores with different ownership and different write patterns.

### 15.2 Why the Alterverse is runtime-hosted, not kernel-hosted

The kernel ledger records what the kernel did: real bridge crossings, real outside calls, real kernel ops. Every event in the kernel ledger represents a real boundary crossing between the kernel and outside reality, or a real internal kernel state change.

The Alterverse store records what the simulation experienced: tokens created within a simulation, nodes entered within a frame, branches forked from backup points. Most of these events are pure-internal — they don't represent real boundary crossings, just simulation-internal state.

Putting simulation-internal events in the kernel ledger would conflate two stores with different semantics:

- **The kernel ledger** is canonical for governance: every event represents real cost, real authorization use, real cross-factory observable activity.
- **The Alterverse store** is canonical for replay and counterfactual analysis: branches fork, replay from arbitrary points, no governance implications because nothing real happened.

Conflating them makes the kernel ledger huge (one Monte Carlo trial can produce millions of pure-internal events) and confuses governance queries (a "list all bridge crossings this week" query has to filter out simulation-internal events).

v1.1 separates them: the kernel ledger stays focused on real events; the Alterverse store hosts simulation-internal events in a runtime-managed format optimized for replay.

### 15.3 The kernel-side hook: `_simulation.alterverse-store`

Per §7.6, the `_simulation.alterverse-store` projection type is the kernel-side anchor for runtime-hosted Alterverse stores. The meta-projection record names the store's identity, scope, format version, current branch, root branch, location, replay policy, and retention policy.

The kernel does not host the store contents; it hosts the meta-projection. Applications query the kernel for "which Alterverse stores cover this scope" or "what is the current branch of this store" and get results from the meta-projection records. To read store contents, the application uses the runtime's API — the kernel doesn't proxy it.

### 15.4 Cross-references between the two stores

Some events appear in both stores:

- **Real bridge crossings during simulation.** When a simulation's PRISM-IR program reaches a node that crosses outside (e.g., calls an LLM to evaluate a counterfactual), the call really happens — real cost is incurred, real outside service is contacted. This event is in the kernel ledger (as a real outside-call event) and in the Alterverse store (as a simulation event with the bridge-crossing context).
- **Decision events that are both governance-relevant and simulation-relevant.** A policy evaluation during a simulated workflow appears in both stores.

Cross-references are by event ID. The kernel writes a tier 3 event with id X; the Alterverse store records the same event under id X with simulation-context metadata; queries linking the two stores match on id.

The kernel does not enforce the cross-reference. The runtime is responsible for maintaining it. v1.1 specifies the convention; future implementation work lands the runtime-side machinery.

### 15.5 Pure-internal simulation events

Most simulation events are pure-internal: they don't cross outside, they don't change real kernel state, they exist only within the simulation's frame. Examples:

- A token entering a node in the simulation's flow
- A branch forking from a backup point
- A counter incrementing on a metric measurement
- A frame advancing past an event-time boundary

These events live only in the Alterverse store. The kernel does not see them; it hosts the meta-projection but doesn't replicate the contents.

This dramatically reduces the kernel's write volume during simulation. A Monte Carlo trial generating 100,000 internal events produces (at most) tens of kernel-ledger events for the real bridge crossings; the rest live in the Alterverse store at the runtime's preferred density.

### 15.6 Backup and replay

Backup-and-replay is runtime work. The runtime checkpoints simulation state at user-declared points; when a counterfactual analysis is requested, the runtime forks a new branch from a checkpoint and resumes simulation from that point with different parameters or different random seeds.

The kernel hosts the meta-projection but does not host the checkpoints. Checkpoint state is opaque to the kernel — the runtime decides what to capture, when to compact, when to retain, when to discard. The retention and replay policies declared in the meta-projection are runtime-defined opaque values; the kernel records them and exposes them to queries but does not interpret them.

### 15.7 Multiple frames coexisting

In a parallel Monte Carlo run with N trials, each trial's records carry its own `frame: mc-trial-N` annotation. The Alterverse store organizes them as branches under a common root; queries can filter by frame to see one trial's events, or aggregate across frames to see ensemble statistics.

The kernel hosts the (I, R)s and tier 3 events; it does not impose a frame-organization. The Alterverse store does. This is the same cleavage as elsewhere: kernel hosts; runtime organizes.

### 15.8 Generators and PRISM-IR

PRISM-IR's `generators:` block (preserved from v1.0) declares distributions for event generation: arrival processes, service-time distributions, decision probabilities. The runtime samples from these distributions; the sampled events go into the Alterverse store; aggregate statistics produce metrics.

The runtime is the only component that samples; the kernel does not sample distributions. The kernel persists what the runtime authored. This composition is unchanged from PRISM-IR v1.1.

### 15.9 PRISM-IR v1.2 amendment

The PRISM-IR v1.2 amendment (anticipated, not yet published — see §1.3) makes the runtime-hosted Alterverse explicit on the language side. v1.1 of Block 1 commits to the kernel side; once PRISM-IR v1.2 publishes, the two specifications align.

If PRISM-IR v1.2 does not publish on schedule, v1.1 of Block 1 still commits to the kernel-side semantics specified here. Applications using PRISM-IR v1.1 can target v1.1 of Block 1 with the understanding that the Alterverse-as-filter-view framing in PRISM-IR v1.1 is superseded by this section's framing for kernel-hosted hooks.

---

## Section 16 — Storage

This section specifies the v1.1 storage commitment: DuckDB as the backend for the event ledger, indexes, and (with the vss extension) vector search. Markdown remains canonical for (I, R) records. Sidecar files hold large payloads when policy enables them.

### 16.1 DuckDB as backend

v1.1 commits to DuckDB as the storage backend for:

- **The tier 3 event ledger.** Events are written to a DuckDB table indexed by event id, scope, target identifier (for outside calls), payload hash (for deduplication), and time.
- **The kernel's regenerable indexes.** All twelve v1.0.1-partial indexes plus the v1.1 additions (`policy-evaluations`, `lease-holders`) live as DuckDB tables.
- **Vector search**, via DuckDB's `vss` extension. Embeddings are application-supplied; the kernel exposes vector similarity as a query primitive composable with structured filters.

The decisions log §18 names DuckDB as the choice. The reasons:

- **Query performance** at the scale 8OS workloads will reach: tens of millions of events, queries with multiple structured filters and time ranges, joins between events and indexes.
- **Multi-writer transactional semantics** that the v1.0.1-partial JSONL ledger lacks. DuckDB's MVCC handles concurrent writers correctly; JSONL needs file locking that doesn't compose well across processes.
- **Vector search** without a separate vector database. The vss extension lets vector similarity queries join cleanly with structured filters (e.g., "find the most semantically similar (I, R)s in scope X authored last week").
- **Embedded operation** — DuckDB runs in-process, requires no server, and has no separate operational footprint. This matches 8OS's deployment model where a kernel binary runs on a developer's laptop or a single application server.

### 16.2 Markdown remains canonical for (I, R) records

(I, R) records are stored as markdown files with YAML frontmatter, exactly as in v1.0.1-partial. The DuckDB indexes derive from the markdown files; the markdown files are the source of truth.

This is deliberate. Markdown files are:

- **Human-readable** — a reader can `cat` an (I, R) and understand it without tooling.
- **Git-friendly** — version control sees text changes; merge conflicts are tractable; review tools work.
- **Replicable** — copying the markdown directory replicates the kernel's content; rebuilding the DuckDB indexes is mechanical.

DuckDB indexes regenerate from markdown via `kernel.reindex --rebuild`. If the indexes diverge from the markdown (corruption, version mismatch, incomplete write), the markdown is authoritative; the indexes rebuild.

### 16.3 Sidecar payloads

Large outside-call payloads (full LLM prompts, full responses, file contents) are not stored in the event ledger directly. The ledger records the payload hash; the full payload, when policy enables sidecar storage, lives as a file under `.8os/payloads/<event-id>.{request,response}`.

This separates governance metadata (always in the ledger) from payload bulk (gated by policy). Audit queries against the ledger are fast because they don't pull payload bytes; investigations that need the full payload read the sidecar files explicitly.

Sidecar storage is policy-gated. Default is off — payloads exist only as hashes in the ledger. Specific scopes or destinations can require sidecar storage via policy (e.g., regulated workloads where the full payload must be retained for audit).

### 16.4 Storage is implementation-defined for callers

The seventeen-op SDK (§3) and the outside-call primitives (§11) are the contract. Whether the backend is JSONL files, DuckDB, SQLite, or something else is opaque to programs using the SDK.

This means: the v1.0.1-partial binary uses JSONL. The v1.1-target binary uses DuckDB. A future v1.2 binary could use a different backend without breaking existing programs. The migration from JSONL to DuckDB is bounded implementation work; the spec contract doesn't change.

### 16.5 Vectors are application-supplied

The kernel does not compute embeddings or pick embedding models. Applications declare embedding schemes (which model, what shape) and store the resulting vectors as DuckDB columns on (I, R) or event records.

The kernel exposes vector similarity queries via DuckDB's vss extension. Applications compose vector queries with structured filters: "find the 10 most semantically similar (I, R)s in scope X, with `data_classification: pii-free`, authored after date Y."

This composition is the value-add: a separate vector database can do similarity search but cannot easily filter by structured kernel metadata; the kernel's structured queries can filter but cannot do similarity search; DuckDB+vss does both.

### 16.6 Migration from JSONL

The v1.0.1-partial JSONL ledger migrates to DuckDB during the v1.1 implementation work. Migration shape:

1. Read existing JSONL events into DuckDB tables.
2. Rebuild all twelve v1.0.1-partial indexes against the DuckDB tables.
3. Build the new v1.1 indexes (`policy-evaluations`, `lease-holders`, `payload-hash-to-events` for outside-call deduplication).
4. Verify event-count and content checksums match between JSONL and DuckDB.
5. Switch reads to DuckDB; preserve JSONL for one version cycle for fallback safety; then delete.

Migration scripts are bounded subsequent implementation work. The current v1.0.1-partial binary continues to work; the v1.1 binary lands the migration.

---

## Section 17 — Observability

This section specifies how observability tooling consumes kernel state. v1.1 adds no new SDK ops for observability; the existing read primitives plus DuckDB query interface suffice.

### 17.1 No new SDK ops for observability

The seventeen-op SDK plus the outside-call primitives expose what observability tooling needs:

- `kernel.event.get` — read individual events
- `kernel.ir.list` — list (I, R)s with filters
- `kernel.ir.get` — read individual (I, R)s
- `kernel.ir.deps` — query dependency graphs
- DuckDB query access — for richer queries the SDK ops don't cover directly

Adding a `kernel.observe` op or similar would duplicate work the existing primitives already do. v1.1 declines.

### 17.2 Polling-based, not streaming

v1.1 is polling-based for observability. Tools tail the ledger by polling DuckDB for events with sequence numbers higher than the tool's last-seen marker. Streaming primitives — server-sent events, websocket subscriptions, push notifications — are deferred.

The reason: streaming primitives multiply the kernel's surface area without strong evidence the workloads need them. A polling interval of 1 second is fast enough for human-in-the-loop tools; lower-latency observability can compose from polling at higher frequency. If a workload genuinely needs streaming primitives, that surfaces as an OPEN-Q for a future version.

### 17.3 Userspace tools, not kernel-shipped

Observability tooling is userspace. Multiple tools may consume the same kernel; none ship with the kernel binary. The kernel's job is to expose state honestly; the ecosystem's job is to ship viewers.

This includes:

- A "Task Manager" equivalent showing currently-active (I, R)s and their resolvers
- A cost dashboard aggregating three-cost decomposition by scope, factory, skill
- A drift detector flagging (I, R)s whose `valid_through` has passed but whose `status` is still `resolved`
- An audit query interface for governance investigations
- Real-time event tailing for development

None of these are specified in v1.1. They are downstream tools that compose from the SDK and DuckDB query interface.

### 17.4 Standard query patterns documented as conventions

The spec documents standard query patterns as conventions tools SHOULD follow. Examples:

- **Cost rollup** — sum `resolver_cost`, `kernel_cost`, `factory_cost` separately by scope and time window, present three-vector totals.
- **Outside-call audit** — filter events by `target_category: network`, group by `target_identifier`, present unique destinations per scope.
- **Skill activity** — filter events by skill_id metadata, group by op, present per-skill activity rollups.

These are conventions, not enforcement. Tools that follow them are interoperable; tools that don't still work but aren't interoperable with each other.

### 17.5 Factory-id and skill-id as event metadata conventions

Per the decisions log §19.5, factory_id and skill_id are event metadata conventions, not kernel-enforced fields. Factories and skills SHOULD include their id in event metadata when authoring; the kernel does not validate or enforce these fields, but tools observing the ledger benefit from them being present.

This is a deliberate non-enforcement: kernels that enforce specific metadata fields fragment as ecosystems grow (each tool wants different metadata). Conventions evolve faster than schema. v1.1 documents the conventions; tools adopt them; the kernel stays minimal.

### 17.6 Cost rollups as materialized views, not kernel schema

Aggregate cost queries (per-scope totals, per-factory totals, per-skill totals) compose as DuckDB materialized views or repeated queries over the event ledger. They are not baked into the kernel schema as denormalized fields.

This means: the kernel's storage commitment is to the events themselves, in their normalized form. Aggregations are a query-time concern. Tools that want fast cost rollups maintain their own materialized views; the kernel does not.

The trade-off is query performance vs storage simplicity. v1.1 picks storage simplicity. Tools that need real-time cost dashboards run materialized-view refresh on their own cadence.

---

## Section 18 — Error codes

This section consolidates the error codes referenced throughout the spec. The list is exhaustive for v1.1; new error codes require a spec amendment.

### 18.1 (I, R) lifecycle errors

- `IR_NOT_FOUND` — referenced (I, R) does not exist.
- `IR_NOT_VISIBLE` — (I, R) exists but caller's scope cannot see it.
- `ID_CONFLICT` — attempted to author an (I, R) with an id that already exists.
- `IR_NOT_RESOLVABLE` — (I, R) status is not `open` or `stale`; cannot resolve.
- `IR_NOT_SUPERSEDABLE` — (I, R) status is `superseded`, `cancelled`, or `stale`; cannot supersede.
- `IR_NOT_CANCELLABLE` — (I, R) status is `superseded` (per BLOCK-4.5-SPEC-AMENDMENTS.md Amendment 3 — `stale` dropped). The state must be in `{open, resolved, stale}` for cancellation. Already-cancelled records reject with `IR_ALREADY_CANCELLED`; superseded records cannot be cancelled (supersede the new content instead).
- `IR_SUPERSEDES_TARGET_NOT_CANCELLED` — `kernel.ir.new` was called with a `supersedes:` input pointing at an (I, R) whose status is not `cancelled` (per BLOCK-4.5-SPEC-AMENDMENTS.md Amendment 4). Supersede-with-replacement applies only to cancelled records; for living records (`open`, `resolved`, `stale`), use `kernel.ir.supersede` (§3.7).
- `IR_ALREADY_CANCELLED` — (I, R) is already cancelled; cancellation is terminal.
- `IR_ALREADY_EXPANDED` — (I, R) is already expanded; cannot re-expand.
- `IR_NOT_EXPANDED` — (I, R) is not expanded; cannot collapse.
- `EVENT_ALREADY_PROMOTED` — tier 3 event has already been promoted to tier 2.
- `PROMOTION_NOT_PERMITTED` — event category is not eligible for promotion to the requested projection type.

### 18.2 Schema and validation errors

- `SCHEMA_INVALID` — record fails schema validation (missing required field, invalid value).
- `CONFLICTING_PROJECTION_FIELDS` — multiple projection types declare conflicting required fields.
- `CONFLICTING_PROJECTION_TARGETS` — multiple projection types declare conflicting `target_subdirectory` values.
- `INVALID_DEPTH` — depth parameter on `kernel.ir.get` is invalid.
- `INVALID_FILTER` — filter on `kernel.ir.list` is malformed.
- `INVALID_DIRECTION` — direction parameter on `kernel.ir.deps` is invalid.
- `INVALID_ACTION` — action on `kernel.gatekeeper.check` is invalid.
- `INVALID_SCOPE_OF_AUTHORITY` — `scope_of_authority` on `kernel.authorize` is invalid.
- `VISIBILITY_PREDICATE_NOT_PERMITTED` — convention-authored record carries `visible_when`.
- `COST_DECOMPOSITION_INVALID` — cost vectors malformed (missing components, negative values, non-numeric).

### 18.3 Authority and authorization errors

- `AUTHORITY_INSUFFICIENT` — caller's authority is below required level.
- `AUTHORITY_INSUFFICIENT_FOR_SUPERSESSION` — superseder's authority is below superseded record's.
- `CANCELLATION_AUTHORITY_INSUFFICIENT` — caller's authority is insufficient for the cancellation requested.
- `AUTHORIZATION_REQUIRED` — operation requires an authorization that was not supplied.
- `AUTHORIZATION_NOT_FOUND` — referenced authorization does not exist.

### 18.4 Lease errors

- `LEASE_HELD` — target is under a lease held by another writer.
- `LEASE_EXPIRED` — operation against a lease whose `valid_through` has passed.

### 18.5 Policy errors

- `POLICY_DENIED` — applicable policy denied the operation.
- `POLICY_REQUIRES_AUTHORIZATION` — applicable policy defers; authorization needed.

### 18.6 Outside-call errors

- `OUTSIDE_UNREACHABLE` — outside service did not respond.
- `BRIDGE_UNREACHABLE` — legacy bridge unreachable (preserved from v1.0.1-partial).
- `EVENT_WRITE_FAILED_AFTER_CROSSING` — outside contacted; event record lost; response in error context.
- `OUTSIDE_CALL_DENIED` — applicable policy denied the outside call.
- `BUDGET_EXHAUSTED` — cost ceiling exceeded.
- `RATE_LIMIT_EXHAUSTED` — rate limit hit.
- `EXPIRES_AT_PASSED` — queue cutoff elapsed before service.
- `PAYLOAD_TOO_LARGE` — request payload exceeds kernel limits.
- `CLASSIFICATION_VIOLATION` — payload classification incompatible with destination policy.

### 18.7 Resolver and bridge errors

- `RESOLVER_NOT_FOUND` — referenced resolver does not exist.
- `RESOLVER_VECTORS_MISSING` — resolver lacks declared cost or capability vectors.
- `BRIDGE_NOT_FOUND` — referenced bridge does not exist.
- `NO_CANDIDATE_RESOLVERS` — selector found no candidate resolvers for the intention.
- `VOI_CONSULTATION_FAILED` — VOI resolver invocation failed.

### 18.8 Scope and event errors

- `SCOPE_NOT_FOUND` — referenced scope does not exist.
- `EVENT_NOT_FOUND` — referenced event does not exist.
- `EVENT_NOT_VISIBLE` — event exists but caller's scope cannot see it.

### 18.9 Init and maintenance errors

- `REPO_PATH_INVALID` — repo path on `kernel.init` is invalid or unwritable.
- `VERSION_DOWNGRADE_REJECTED` — existing repo version is newer than requested.
- `VENDORED_BODY_INVALID` — kernel binary's vendored body schema fails self-validation.
- `INDEX_DRIFT_DETECTED` — `kernel.reindex --check` found inconsistency between records and indexes.
- `RECORD_UNREADABLE` — record file cannot be read or parsed.
- `IR_CANCELLED` — pending op against an (I, R) that has been cancelled.

---

## Section 19 — Migration from v1.0.1-partial to v1.1

This section specifies the migration shape from v1.0.1-partial to v1.1. The migration is bounded subsequent implementation work; this section names what migration must accomplish.

### 19.1 What v1.1 adds that needs migration

- The new `cancelled` status enum value (§5)
- Three-cost decomposition on event records (§6)
- Six new projection types (§7) and the records that compose them
- Three new base frontmatter fields (`data_classification`, `domain`, `visible_when`)
- DuckDB storage backend (§16)
- New error codes and the spec sections that reference them

### 19.2 Migration discipline

The migration script (`scripts/migrate-v1.0.1-partial-to-v1.1.py`) MUST be:

- **Idempotent.** Running it twice produces the same result as running it once.
- **Reversible-or-fenced.** Either the migration is reversible to v1.0.1-partial state, or it explicitly fences forward (records the migration as a tier 3 event with `kernel.self` provenance, after which downgrade is not supported).
- **Pre-flight validating.** Before any change, validate that the existing repo is a clean v1.0.1-partial state. Refuse to migrate dirty or partially-migrated repos without explicit `--force` flag.
- **Tested.** All migration phases tested against representative v1.0.1-partial repos before release.

### 19.3 Migration phases

1. **Pre-flight check.** Validate v1.0.1-partial state (version string, schema conformance, index consistency). Refuse if dirty.
2. **Schema additions.** Add the three new base frontmatter fields as optional. Existing records are valid without them; new records may carry them.
3. **Status enum extension.** Extend the status enum to include `cancelled`. No existing records carry the new value; the extension is forward-compatible.
4. **Cost decomposition migration.** Per §6.7, treat existing single-vector `cost_actual` as `resolver_cost` with `kernel_cost` and `factory_cost` set to zero. Update event records in place; preserve a backup of the original JSONL ledger for one version cycle.
5. **DuckDB index materialization.** Build DuckDB tables from existing JSONL events; rebuild the twelve v1.0.1-partial indexes; build the new v1.1 indexes; verify checksums.
6. **Vendored body refresh.** Update vendored projection bodies to v1.1 versions. Per the per-version body seal discipline (Block 2.7's amendment, folded into v1.1's §4 vendored body seal), the kernel binary owns body content per version.
7. **Tier 3 migration event.** Author one tier 3 event recording the migration through `authored_via: kernel.self`.

### 19.4 Mapping from prior amendment documents

Block 2.7 corrections, Block 2.8 amendments, and v1.0.1-partial amendments are folded into v1.1 sections as follows:

| Prior content | Now in v1.1 |
|---|---|
| Block 2.7 Patch 1 (configuration-as-content) | §4 (frontmatter), §7 (projection definitions) |
| Block 2.7 Patch 5 (`bridge_type` → `authored_via` rename) | §4.1 (preserved as `authored_via`; `bridge_type` retained as legacy field) |
| Block 2.8 (proposal_status rename, authorization extension) | §7 (projection types preserved verbatim) |
| v1.0.1-partial Amendment 1 (target_subdirectory) | §3.2 (`kernel.ir.new` path resolution), §7 (projection definition body schema) |
| v1.0.1-partial Amendment 2 (mandatory `authored_via`) | §3.2 (required field), §4.1 (base schema), §3.17 (reindex enforcement) |
| v1.0.1-partial Amendment 3 (per-version body seal) | §4.8 (vendored body seal discipline) |

If any prior content is not yet folded, that surfaces as a blocker on §22's "all forward references resolve" ship precondition.

### 19.5 Backward compatibility

A v1.0.1-partial repo at the time of v1.1 publication migrates cleanly via the script in §19.3. After migration, the repo is at v1.1. Reverting to v1.0.1-partial is supported through the backup of the JSONL ledger and the markdown records (markdown is unchanged shape).

A v1.1 binary attempting to run against a v1.0.1-partial repo (without migration) refuses with `VERSION_MISMATCH` and prompts the user to run the migration script.

A v1.0.1-partial binary attempting to run against a v1.1 repo refuses with `VERSION_DOWNGRADE_REJECTED`. Downgrade requires explicit user action (restore from backup).

---

## Section 20 — What v1.1 does not do

Surfacing constraints v1.1 declines to address, so future blocks know they are open.

### 20.1 Factory specification

v1.1 does not specify the factory. Block 3 manifested one factory (`src/eightos/factory/`); v1.1 commits the substrate the factory runs on. A separate factory specification (likely SPEC-FACTORY-001) is future work. Multiple factories can coexist on the same kernel; v1.1 specifies the kernel-level coordination machinery (leases, policies, three-cost decomposition) but not how any specific factory walks graphs or dispatches.

### 20.2 Surrogate training pipeline

v1.0 deferred the surrogate training pipeline; v1.1 also defers. The `kernel.surrogate.train` interface stub from v0.1.0 is **removed** in v1.1 (§3.0 / decisions log §4.4). Surrogate training is userspace; future work specifies a training-pipeline architecture that consumes the calibration corpus and produces trained surrogates.

### 20.3 Autonomous dispatch

v1.1 does not specify autonomous dispatch — kernel-driven scheduling that picks workloads to run without explicit user invocation. The chat-6 reframe (factories as userspace PRISM-IR programs) plus v1.1's governance and skill machinery covers most of what an autonomous-dispatch spec would have specified. Remaining gaps surface during implementation as concrete OPEN-Qs.

### 20.4 Streaming observability primitives

v1.1 is polling-based for observability (§17.2). Streaming primitives are deferred until a workload demonstrates need.

### 20.5 Non-network outside-call primitives

v1.1 ships only `kernel.outside.http` for `target_category: network`. File IO, human consultation, simulator invocation, shell commands as kernel primitives are future work (§11.8).

### 20.6 Cross-factory transactional semantics

The kernel offers per-op atomicity and lease-bounded mutual exclusion (§13). Richer cross-factory transactions (multi-step all-or-nothing across factories) are not specified. Workloads needing such semantics compose them from existing primitives or use external coordination.

### 20.7 Finer-grained depth selection strategies

The selector picks from coarse-grid declared depth points per v1.0 §5.1. Continuous optimization over depth, gradient-based depth-budget tuning, learned depth selectors — all reserved for future versions.

### 20.8 Continuous integration over depth or workload size

v1.1 does not respec the sixteen operations preserved from v1.0.1-partial; their op contracts are inherited. v1.1 does add `kernel.ir.cancel` as the seventeenth, and extends the cost shape on existing ops to three-vector decomposition.

### 20.9 PRISM-IR v1.2 grammar additions beyond Alterverse

v1.1 anticipates the Alterverse-storage clarification in PRISM-IR v1.2. Other PRISM-IR v1.2 candidates — workload-meta-properties grammar (decisions log §24.2), arrival-time vs queue-time semantics — are deferred to PRISM-IR v1.2's drafting and may slip to v1.3.

### 20.10 T&S decision mechanism specification

Per the decisions log §13, T&S decisions compose from v1.1's policy machinery. v1.1 does not specify a T&S-specific decision language or T&S-specific projection types. Applications compose T&S from `_kernel.policy` records, classification flow (§11.7), and skill manifests (§9). The transform mechanism for `decision: transform` policies is OPEN-Q-033 (§21).

---

## Section 21 — Open questions

This section lists open questions remaining after v1.1. Resolved questions from prior versions are preserved as historical record in the open-questions registry (`docs/open-questions.md`).

### 21.1 Carried open from v1.0.1-partial

- **OPEN-Q-001** — Human override of kernel-authored selection. Not addressed at v1.1; future version.
- **OPEN-Q-003** — Tier 3 retention policy. Project-level for now; future kernel `_kernel.retention-policy` projection if multi-tenant retention becomes a real concern.
- **OPEN-Q-009** — Promotion target tier-2 category. Defaults to `resolver-selection`; not yet a hot path.
- **OPEN-Q-024** — VOI cost-vector degeneracy at zero costs. Awaiting empirical workload that exercises calibration on LLM resolvers.
- **OPEN-Q-025** — Calibration corpus predicted/actual type heterogeneity. Awaiting cross-domain calibration workloads.

### 21.2 Closed in v1.1

- **OPEN-Q-006** — Bridge implementation location. **CLOSED** by §10.5: bridges live as PRISM-IR (I, R)s; their Python implementations (when used) live wherever `op: script` references point.
- **OPEN-Q-019** — `domain` as base frontmatter. **CLOSED** by §4.3: `domain` is now an optional base field, parallel to `stakes`.
- **OPEN-Q-026** — Resolver and bridge frontmatter fields read by the factory but not declared in vendored projection bodies. **CLOSED** by §7's projection-type specifications and the bridges-as-PRISM-IR transition (§10).
- **OPEN-Q-027** — Disambiguation of `resolver` vs `resolver_id`. **CLOSED** by §4.1's base field table specifying `resolver` as the base field on (I, R)s and §7.5 specifying skill-related resolver references.
- **OPEN-Q-028** — Pricing data location for bridges. **CLOSED** by §10's bridges-as-PRISM-IR commitment: pricing lives in the bridge's program where `op: script` references point, not in `_kernel.bridge` frontmatter.

### 21.3 New in v1.1

- **OPEN-Q-031** — Transitive cancellation cascade depth and termination. §3.8 specifies cascade walks one hop in `deps-reverse`. Whether `stale` should propagate transitively from cascaded dependents to their dependents — and if so, with what depth bound — is deferred. Resolution criterion: first workload exercising a multi-level dependency graph under cancellation.
- **OPEN-Q-032** — Cascade event emission for already-stale or already-cancelled dependents. §3.8 specifies skip-no-emit. Whether to emit a tier 3 event for every walked dependent (including no-op skips) for audit-completeness is deferred. Resolution criterion: observability tooling exposes a need.
- **OPEN-Q-033** — Transform-policy mechanism. §8.4 specifies `decision: transform` produces an action; the actual mechanism (resolver invocation, synchronous function, deferred call) is not specified. The three options have different cost profiles, atomicity properties, and failure modes. Resolution criterion: first transform-policy workload determines the right mechanism.
- **OPEN-Q-034** — Multi-factory atomicity discipline beyond leases. v1.1 commits to leases for write coordination. Whether richer patterns (read-write barriers, cross-factory checkpoints) need kernel primitives or compose from leases alone is deferred. Resolution criterion: first multi-factory deployment exercising contention beyond simple write exclusion.
- **OPEN-Q-035** — ULID clock skew tolerance. v1.1 says ULIDs are best-effort timestamp-ordered; replay tolerates skew. Whether tools that depend on tighter ordering need additional kernel-side machinery (e.g., per-writer sequence numbers exposed in events) is deferred. Resolution criterion: first multi-factory deployment that surfaces ordering bugs traceable to ULID skew.
- **OPEN-Q-036** — Lease vs filesystem-mutex final shape. The lease primitive specifies the spec-level contract; the implementation may use database row locks, filesystem flock, or other mechanisms. Whether the implementation choice has spec-visible consequences is deferred.

### 21.4 Reserved for PRISM-IR v1.2

These are PRISM-IR concerns; they surface in this spec as anticipated v1.2 amendment items:

- **OPEN-Q-030** — Workload-meta-properties drift. PRISM-IR v1.2 candidate; may slip to v1.3.

---

## Section 22 — Status

This is **v1.1.0**. It supersedes v1.0.1-partial. It locks the architectural commitments enumerated in §0–§21:

- The four-layer architectural model (§1)
- The kernel responsibility taxonomy (invariants / limits / facts / primitives — §2)
- The seventeen SDK operations (§3) including the new `kernel.ir.cancel`
- The (I, R) frontmatter schema with three new optional base fields (§4)
- The five-value status enum including the new `cancelled` (§5)
- The three-cost decomposition (§6)
- The eighteen projection types (§7) including the six new in v1.1
- Governance machinery (§8)
- Skills as PRISM-IR programs (§9)
- Bridges as PRISM-IR programs (§10)
- Outside-call governance with `kernel.outside.http` (§11)
- Decision-and-action separation as PRISM-IR composition (§12)
- Multi-factory architecture and lease coordination (§13)
- Time and clocks (§14)
- Alterverse hosting (§15) anticipating PRISM-IR v1.2
- DuckDB storage commitment (§16)
- Polling-based observability conventions (§17)
- Consolidated error codes (§18)
- Migration from v1.0.1-partial (§19)
- Explicit non-commitments (§20)
- Open questions for future versions (§21)

### 22.1 Publication preconditions

v1.1 ships only when all of the following are true:

- **All forward references resolve.** Every `§N` reference points at an actual section in this document. Final pass before publication verifies this. Any unresolved reference is a ship-blocker; v1.1 does not publish with rotted references.
- **All "to be added" markers are removed.** Any "TODO," "see below," "to be specified" markers in the text are resolved before publication.
- **The implementation gap section (front matter) is current.** What's not yet implemented at publication time is named precisely; if any item lands during the drafting window, it moves out of the gap list.
- **The decisions log §27.1 commitments are all addressed.** Each commitment in the decisions log either lands as a v1.1 spec section, lands as a v1.2 amendment commitment, or surfaces as an explicit open question with resolution criterion.
- **PRISM-IR v1.2 status is named honestly.** Either v1.2 publishes alongside v1.1 (referenced by version), or v1.1 names the anticipated amendment with explicit hedge that the language-side commitment is DEIA Solutions' to make.

These are checklist items for publication, not v1.1 spec content. They live here so a future drafter completing v1.1 has them visible.

### 22.2 Stability commitment

Future versions may add projection types, resolvers, error codes, optional base fields, and other refinements. They SHOULD preserve the principles that:

- Every artifact the kernel manages is an (I, R)
- The kernel's reasoning about its own reasoning is itself (I, R)-shaped
- Mechanisms are kernel; values are application
- The inside/outside boundary (axiom 0) is structural, not stylistic
- Decision-and-action separation lives in PRISM-IR, not in the kernel
- Skills, bridges, and factories are PRISM-IR programs running on the kernel substrate

Departures from these principles indicate a flaw in the principles or a flaw in the design, to be resolved by amendment with explicit axiom-level reasoning.

### 22.3 What comes after v1.1

The next block is the factory specification (SPEC-FACTORY-001 working name). It consumes v1.1's substrate commitment and specifies how a factory walks PRISM-IR programs, dispatches resolvers, materializes (I, R) graphs, and composes the v1.1 governance machinery into a coherent runtime. Block 3's reference factory implementation is the worked example.

After the factory specification, subsequent blocks land:

- The DuckDB storage migration
- Multi-factory binary support
- The new projection types as binary code
- The six v1.1 implementation gap items currently named in the front matter
- Bridges-as-PRISM-IR migration (per-bridge, incremental)

The path is sequential but each block is bounded. v1.1 is the architectural commitment; the binary catches up over multiple subsequent rounds.

---

*End of Block 1 specification v1.1. Authored 2026-04-28 by Q88N + Claude. Supersedes v1.0.1-partial. Consolidates v1.0.0, Block 2.7 corrections, Block 2.8 amendments, and v1.0.1-partial amendments. Locks the v1.1 architectural commitments derived in the Block 4 architecture conversation.*














