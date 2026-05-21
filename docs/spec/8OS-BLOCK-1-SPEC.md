---
id: 8OS-BLOCK-1-SPEC
version: 0.2.0
status: accepted
kind: derivation
scope: project
domain: 8os/representation
authored_by: Q88N + Claude (Block 2.7 derivation)
authored_on: 2026-04-26
supersedes: 8OS-BLOCK-1-SPEC v0.1.0
superseded_by: null
depends_on: 8OS-KERNEL-SPEC v0.1.0
revisit_when: implementation surfaces a contradiction with the eight axioms or with this representation
provenance: Block 2.5 surfaced OPEN-Q-010, OPEN-Q-011, OPEN-Q-012; v0.2 resolves them by collapsing kernel-configuration objects into kernel-defined projection types of (I, R), per axiom 1
---

# 8OS Block 1 Specification v0.2

## What this document is

This is the on-disk representation specification for 8OS, version 0.2. It supersedes v0.1.0. It preserves the eighteen-operation SDK contract from v0.1.0 verbatim and refactors the representation of kernel-configuration objects to comply strictly with axiom 1.

v0.2 makes one principled change: **the kernel's configuration objects — resolvers, bridges, projections, scopes, surrogate lineage records — are themselves (I, R) pairs**, authored through the same SDK operations as user content, scoped to a reserved `_kernel` scope, and projected through five kernel-defined projection types.

There are no typed configuration operations. `resolver.add` and `bridge.add` from v0.1.0 are removed. All configuration is authored through `kernel.ir.new` with the appropriate `projection_types` field.

## Why v0.2 exists

v0.1.0 specified eighteen operations and twelve indexes that implemented axiom 1's claim that *every artifact the kernel manages is either an (I, R) pair or a structured collection of (I, R) pairs*. But v0.1.0's representation carved out exceptions: resolvers lived in `.8os/resolvers/<id>.yml`, bridges in `.8os/bridges/<id>.yml`, projection definitions in `.8os/projections/<id>.yml`, scopes in `ir/<scope>/_scope.yml`. These were configuration objects with their own typed operations (`resolver.add`, `bridge.add`) and direct file writes for projections and scopes.

This was an axiom violation hidden under "implementation detail." Axiom 1 admits no exceptions.

Block 2.5 surfaced the cost. Three findings (OPEN-Q-010, OPEN-Q-011, OPEN-Q-012) all traced back to the same root: the SDK's content-vs-configuration split. The kernel could not host PRISM-IR as a projection through its own SDK — Block 2.5 had to write `.8os/projections/prism-ir.yml` directly, bypassing the kernel.

v0.2 resolves the split by removing it. Configuration is content. The eighteen content operations are sufficient to manage the kernel's configuration because configuration is (I, R)-shaped from the start.

## Status of v0.1.0

v0.1.0 is superseded but referenced. The eighteen-operation SDK contract from v0.1.0 §SDK is preserved verbatim in v0.2. v0.2 specifies the on-disk representation changes; it does not respecify the operations. Any operation behavior not explicitly clarified in v0.2 follows v0.1.0.

Implementations targeting v0.1.0 must migrate to v0.2 per the migration discipline in §7. There are no v0.1.0-compatible runtimes after v0.2 lands; the supersession is total.

---

## Section 1 — On-disk representation (changed)

### 1.1 Folder structure

The v0.2 repo layout consolidates kernel-configuration objects into the IR graph and reserves a `_kernel` scope for them. Compare against v0.1.0 §1.1.

```
<repo-root>/
├── .8os/
│   ├── version                            # ABI version (e.g., "0.2.0")
│   ├── events/                            # tier 3 event JSONL streams
│   │   ├── YYYY/MM/DD/<file>.jsonl
│   │   └── raw/                           # large-payload sidecars
│   ├── index/                             # twelve regenerable indexes (per v0.1.0)
│   │   └── <as in v0.1.0>
│   ├── projections/_kernel/               # vendored kernel projection bodies (read-only)
│   │   └── <type>.yml                     # NOT projection (I, R)s — these are
│   │                                      # vendored body schemas, sealed at kernel ship
│   └── sdk/
│       └── schemas/                       # JSON Schemas for SDK operations (per v0.1.0)
├── ir/
│   ├── _kernel/                           # NEW — reserved kernel-configuration scope
│   │   ├── projection/                    # projection-definition (I, R)s
│   │   │   ├── _node.md                   # category root, optional
│   │   │   └── <projection-id>.md
│   │   ├── resolver/                      # resolver-definition (I, R)s
│   │   │   └── <resolver-id>.md
│   │   ├── bridge/                        # bridge-definition (I, R)s
│   │   │   └── <bridge-id>.md
│   │   ├── scope/                         # scope-declaration (I, R)s
│   │   │   └── <scope-id>.md
│   │   └── surrogate-lineage/             # surrogate-lineage (I, R)s
│   │       └── <surrogate-id>.md
│   ├── _ops/                              # tier 2 records (per v0.1.0)
│   │   └── <as in v0.1.0>
│   └── <user-scope>/                      # tier 1 user content (per v0.1.0)
│       └── <as in v0.1.0>
├── .githooks/                             # per v0.1.0
├── .github/                               # per v0.1.0
├── .gitattributes                         # per v0.1.0
├── .gitignore
├── 8OS-KERNEL-SPEC-v0.1.md
├── 8OS-BLOCK-1-SPEC.md                    # this document, v0.2
└── README.md
```

### 1.2 Removed from v0.1.0

The following directories from v0.1.0 §1.1 are removed in v0.2:

- `.8os/resolvers/` — replaced by `ir/_kernel/resolver/`
- `.8os/bridges/` — replaced by `ir/_kernel/bridge/`
- `.8os/projections/<type>.yml` (project-declared) — replaced by `ir/_kernel/projection/`

`.8os/projections/_kernel/` is preserved but its meaning changes. See §1.3.

The convention `ir/<scope>/_scope.yml` from v0.1.0 is removed. Scopes are now scope-declaration (I, R)s under `ir/_kernel/scope/`. Existing scope folders still hold their (I, R) content; they no longer carry a `_scope.yml` file.

### 1.3 `.8os/projections/_kernel/` — vendored kernel projection bodies

The `_kernel` subdirectory under `.8os/projections/` is preserved with a refined meaning. It holds **vendored body schemas for the five kernel projection types**, sealed at kernel ship time. These are not projection (I, R)s. They are the body content the kernel reads to validate kernel-configuration (I, R)s.

The relationship is:

- `ir/_kernel/projection/<type>.md` is the projection-definition (I, R) — frontmatter with provenance, authority, intention.
- `.8os/projections/_kernel/<type>.yml` is the vendored body content for the kernel-shipped projection types. Sealed; not editable post-clone.
- A user-declared projection (an (I, R) authored by the user, not vendored) carries its body content inline in the (I, R)'s body. No separate vendored file.

This is the only asymmetry between kernel-shipped configuration and user-authored configuration in v0.2. The asymmetry exists because the kernel must boot with its core projection types already valid before the first `ir.new` call has happened. Bootstrap requires vendored body content; everything authored after bootstrap follows the uniform (I, R) pattern.

### 1.4 The `_kernel` scope

A new reserved scope is introduced: `_kernel`. It has the following properties:

- Declared at kernel ship time. Vendored as `ir/_kernel/_scope.yml` is removed; the scope declaration is itself an (I, R) at `ir/_kernel/scope/_kernel.md` of `projection_types: [_kernel.scope]`. Bootstrap creates this (I, R) before any other.
- Authored only by the kernel itself or by humans with `authority_level: hard`. The gatekeeper rejects writes from `convention` or `uncalibrated` authors.
- Not visible to user-scope traversals by default. `ir.list` on a user scope does not include `_kernel` entries unless `--include-kernel` is passed.
- Indexed in the same twelve indexes as user content. No separate kernel index.

The `_kernel` scope is structurally identical to `_ops` (kernel-authored, reserved) but semantically different: `_ops` records what the kernel did; `_kernel` declares what the kernel is configured to do.

---

## Section 2 — (I, R) frontmatter schema (clarified)

The v0.1.0 frontmatter schema is preserved with one renaming (§2.5). v0.2 clarifies one mechanism that was specified but not implemented in v0.1.0: **projection-declared frontmatter extensions** (Block 2.5 OPEN-Q-010).

### 2.1 Projection-declared frontmatter extensions

Every projection-definition (I, R) declares zero or more required frontmatter fields beyond the base 8OS frontmatter. When `kernel.ir.new` is called with `projection_types: [<type>]`:

- The kernel reads the projection-definition (I, R) for each type in the list.
- The union of all projection-declared required fields becomes part of the (I, R)'s required frontmatter for this operation.
- The operation's input must include values for those fields, validated against their declared types.
- The fields are written to the (I, R)'s frontmatter alongside the base 8OS frontmatter.

The fields are not nested under a separate block. They appear at the top level of frontmatter alongside `id`, `tier`, `scope`, etc. Field-name collisions with base 8OS frontmatter are forbidden — the kernel rejects projection definitions that would collide.

### 2.2 Filename suffix from projection (Block 2.5 OPEN-Q-012)

A projection-definition (I, R) may declare a `filename_suffix` field in its body. When an (I, R) of that projection type is created via `ir.new`:

- The id remains a clean slug (e.g., `expense-approval`).
- The on-disk filename uses the suffix (e.g., `expense-approval.prism.md`).
- The id-to-path index records the mapping; the id never includes the suffix.

If multiple projection types are listed and they declare conflicting suffixes, the kernel rejects the operation with a structured error. Projections that declare no `filename_suffix` default to `.md`.

### 2.3 The `_kernel` scope authority requirement

`(I, R)`s in scope `_kernel` must have `authority_level: hard`. The gatekeeper rejects `ir.new` calls into `_kernel` with author authority below hard. This is enforced for all five kernel projection types and any future (I, R)s scoped to `_kernel`.

### 2.4 Authority foundations — the kernel's *cogito* and the human's sovereignty

Every (I, R) in 8OS has an authored_by that traces, eventually, through a finite chain of authority assertions to one of two foundational sources:

- **The kernel's *cogito***: the kernel binary observes itself running. When `8os init` executes, *something* is executing this code, observing the observation, writing the bootstrap files. That self-observation is the kernel's existence claim — *I am running, therefore I can record what I am*. The `kernel.self` bridge (§3.4) is this claim made operational. It is the only foundational authority source the kernel can ground without prior structure.

- **The human's sovereignty**: the human running init asserts their own existence as the project's sovereign per #NOKINGS. Their identity is grounded in being themselves — a real human, in a real moment, with real authority over their own decisions and the systems they govern. The `human-<id>` bridge (§3.4) records this identity.

Both are real, both are recorded, both produce real provenance. Neither is a magic exception. The kernel and the human are symmetric foundations of the project's authority graph — kernel authors `_kernel` records through `kernel.self`; humans author user-scope records through their identity bridges. They are co-equal foundations: the kernel cannot author into a user's scope without that user's authority, and a human cannot author into the `_kernel` scope's foundational records without the kernel's bootstrap consent.

This is axiom 0 applied honestly to the kernel's own existence. The kernel is, from the kernel's perspective, *outside* — the kernel binary, the filesystem, the OS underneath, the hardware. The kernel cannot decompose its own substrate. But it can observe itself running on that substrate. That observation is a bridge crossing. It composes with the rest of the kernel's bridge mechanics without special-casing.

### 2.5 Base frontmatter rename: `bridge_type` → `authored_via` (BLOCK-2.7-SPEC-CORRECTIONS Patch 5)

The v0.1.0 base frontmatter declared a field named `bridge_type` that records the bridge through which an (I, R) was authored. The field stores a **bridge id**, not a bridge type — the name was misleading. v0.2's `_kernel.bridge` projection (§3.4) declares `bridge_type` as the bridge's category enum (`api | human | ...`), which collides with the base field on name and triggers §2.1's no-collision rule.

The base field is renamed in v0.2 to `authored_via`. It reads cleanly alongside `authored_by` (who) and `authored_on` (when), completing a three-field provenance story. The semantics are unchanged — the field still stores the id of the bridge through which the (I, R) was authored.

Migration of v0.1 (I, R)s rewrites any `bridge_type: <bridge-id>` frontmatter line to `authored_via: <bridge-id>`. The rewrite is idempotent.

After this rename, `bridge_type` exists in the schema only as the projection-declared extension on `_kernel.bridge` records (§3.4). Base frontmatter has no field by that name.

---

## Section 3 — The five kernel projection types

Each kernel projection type is defined here. Each definition specifies: purpose, projection-declared frontmatter extensions, body shape, authority requirements, on-disk location for the projection-definition (I, R) itself.

### 3.1 `_kernel.scope`

**Purpose**: declare a scope (axiom 3).

**Projection-declared frontmatter extensions**:
- `parent_scope: <scope-id> | null` — parent in the scope hierarchy. `null` only for the root user scope and `_kernel` itself.
- `authority_defaults: {hard: [], convention: [], uncalibrated: []}` — default authority attribution for (I, R)s authored in this scope.
- `visibility_defaults: [<scope-id>, ...]` — default `visible_to` for (I, R)s in this scope.

**Body shape**: free-form prose describing the scope's purpose. Optional. The scope's mechanical declaration is its frontmatter.

**Authority**: `hard` only. Scope creation is a foundational decision.

**On-disk location**: `ir/_kernel/scope/<scope-id>.md`.

**Bootstrap**: `8os init` creates two scope (I, R)s. The first is `_kernel`, authored through the `kernel.self` bridge (see §3.4) by the kernel binary observing its own initialization. Its parent is null. Its authority assertion is grounded in the kernel's own existence — the kernel is running, therefore it can record what it is. The second is the user-supplied primary scope, authored through a `human-<id>` bridge by the human running init. Their authority assertion is grounded in the human's identity as the project's sovereign. Both are real bridge crossings producing real provenance. Neither is a magic exception.

### 3.2 `_kernel.projection`

**Purpose**: declare a projection type (axiom 1's projection mechanism).

**Projection-declared frontmatter extensions**:
- `projection_id: <slug>` — must equal the (I, R)'s `id`. Redundant; provided for body-self-description symmetry with PRISM-IR.
- `filename_suffix: <string>` — default filename suffix for (I, R)s of this type. Default `.md`.
- `body_shape: free | yaml | yaml-fenced | json | none` — declares what the body of (I, R)s of this type contains.
- `body_schema_ref: <uri-or-null>` — optional reference to a schema specifying the body's structure (e.g., for `prism-ir`, a reference to `docs/spec/PRISM-IR-SPEC-v1.1.md`).
- `required_frontmatter: [{name, type, description}, ...]` — fields this projection requires (I, R)s of its type to carry.
- `optional_frontmatter: [{name, type, description}, ...]` — fields this projection allows but doesn't require.

**Body shape**: free prose describing the projection's purpose, links to external specs, examples. The mechanical declaration is in frontmatter.

**Authority**: `hard` for `_kernel.*` projections (kernel-shipped); `convention` or higher for user-declared projections.

**On-disk location**: `ir/_kernel/projection/<projection-id>.md`.

**Bootstrap**: `8os init` creates the five `_kernel.*` projection (I, R)s: `_kernel.scope`, `_kernel.projection`, `_kernel.resolver`, `_kernel.bridge`, `_kernel.surrogate-lineage`.

### 3.3 `_kernel.resolver`

**Purpose**: register a resolver with declared cost and capability vectors (axiom 5).

**Projection-declared frontmatter extensions**:
- `resolver_id: <slug>` — must equal the (I, R)'s `id`.
- `bridge: <bridge-id> | null` — references a `_kernel.bridge` (I, R), or null for inside resolvers.
- `cost: {clock_ms, coin_usd, carbon_g, currency: USD}` — declared cost vector per invocation.
- `capability: {<domain>: {sigma, pi, alpha, rho}}` — declared capability vectors per domain.
- `model_name: <string-or-null>` — for LLM resolvers, the model identifier; null otherwise.

**Body shape**: free prose describing what the resolver does, when to select it, known limitations.

**Authority**: `hard` for kernel-internal resolvers (`kernel.selector`, `kernel.gatekeeper`, `kernel.calibrator`); `convention` for user-declared resolvers (LLMs, humans, scripts, etc.).

**On-disk location**: `ir/_kernel/resolver/<resolver-id>.md`.

**Bootstrap**: `8os init` creates the three kernel-internal resolvers: `kernel.selector`, `kernel.gatekeeper`, `kernel.calibrator`. User adds project-specific resolvers post-init via `ir.new`.

### 3.4 `_kernel.bridge`

**Purpose**: declare an inside/outside bridge (axiom 0).

**Projection-declared frontmatter extensions**:
- `bridge_id: <slug>` — must equal the (I, R)'s `id`.
- `bridge_type: api | human | simulation | script | sensor | other`
- `endpoint: <string-or-null>` — for `api` bridges, the URL or service name; semantics defined by bridge type.
- `requires_authorization: bool` — whether crossings require an authorization (I, R) per axiom 6.
- `scope_of_authority: single | session | persistent` — default authorization scope when crossings are authorized.
- `cost_envelope: {clock_ms_max, coin_usd_max, carbon_g_max}` — upper bounds the kernel enforces on resolvers using this bridge.

**Optional frontmatter extensions**:
- `bridge_status: active | quarantined | deprecated | removed` — bridge availability state. Defaults to `active` when absent. `kernel.bridge.cross` rejects crossings into a bridge with `bridge_status: quarantined` with `BRIDGE_UNREACHABLE`. `deprecated` and `removed` are reserved for future enforcement (warnings on use, hard rejection, respectively); v0.2 records them but does not act on them differently from `active` outside of the `quarantined` check. The name is namespaced (`bridge_status`, not bare `status`) to avoid collision with the base 8OS `status` field that records (I, R) lifecycle. (BLOCK-2.7-SPEC-CORRECTIONS Patch 4.)

**Body shape**: free prose describing the outside system the bridge connects to, change-tracking discipline (per axiom 4 — outside drift may invalidate surrogates of resolvers using this bridge), known characteristics.

**Authority**: `hard` for bridges to systems with consequential outside reach (LLM APIs, payment systems, regulatory submissions); `convention` for low-stakes bridges.

**On-disk location**: `ir/_kernel/bridge/<bridge-id>.md`.

**Bootstrap**: `8os init` creates two vendored bridges that ship with the kernel itself.

The first is **`kernel.self`** — the bridge through which the kernel records observations about its own state. It is authored into existence by the kernel binary at the moment of init, with the kernel binary's own version, build identifier, and checksum as its endpoint. The bridge's existence is grounded in the kernel's own existence: when `8os init` runs, *something* is running this code, and that something is what the bridge connects to. This is the kernel's *cogito* — the existence claim that grounds the kernel's own first authority assertion. `kernel.self` is the only bridge that can author the foundational `_kernel`-scope (I, R)s (the `_kernel` scope declaration itself and the five vendored kernel projection-type definitions). After bootstrap, those records are read-only except via supersession events authored by humans with `hard` authority.

The second is **`human-<primary-operator-id>`** — the bridge through which the human running init authors the user-scope declaration. The human's identity is supplied at init prompt; the bridge endpoint records that identity. The human's authority is grounded in their existence as the project's sovereign per #NOKINGS.

Both vendored bridges are real bridges with real provenance. The kernel and the human are symmetric foundations of the project's authority graph: both authority chains terminate at a self-grounding existence claim, neither is more fundamental than the other.

User adds project-specific bridges post-init via `ir.new` (LLM APIs, payment systems, simulation engines, additional human bridges, etc.).

### 3.5 `_kernel.surrogate-lineage`

**Purpose**: declare a surrogate resolver's lineage (axiom 7).

**Projection-declared frontmatter extensions**:
- `surrogate_id: <slug>` — must equal the (I, R)'s `id`.
- `surrogate_of: <resolver-id>` — the resolver this surrogate approximates.
- `training_corpus: {start: <iso-8601>, end: <iso-8601>, event_count: <int>}` — the tier 3 event slice the surrogate was trained on.
- `validation: {holdout_event_count, accuracy_metric, accuracy_value}` — validation results.
- `trained_on: <iso-8601>` — when training completed.
- `trained_by: <resolver-id>` — what trained the surrogate (could be a human, could be another surrogate, could be a script).

**Body shape**: free prose describing the surrogate's intended use, known limitations, drift-detection plan.

**Authority**: `convention` for routine surrogates; `hard` for surrogates of high-authority resolvers.

**On-disk location**: `ir/_kernel/surrogate-lineage/<surrogate-id>.md`.

**Bootstrap**: `8os init` creates no surrogates. Surrogates emerge from operational history; they can't be bootstrapped.

---

### §3.6 Operation-output projection types

In addition to the five configuration projection types (§3.1–3.5), the kernel ships with four projection types that describe records produced as operation side effects. These are vendored at bootstrap through `kernel.self` like the configuration types, but they describe ephemeral operational artifacts rather than configuration state.

#### §3.6.1 `_kernel.tier3-event`

**Purpose**: typed projection over tier 3 events written to `.8os/events/YYYY/MM/DD/*.jsonl`.

**Projection-declared frontmatter**: none beyond base 8OS frontmatter (these records carry their content in the body or in the JSONL stream itself; the projection exists primarily so that tier 3 events appear in the projection-to-ids index and are discoverable through `ir.list --projection _kernel.tier3-event`).

**Body shape**: free-form, typically empty for events stored canonically in the JSONL stream. (I, R) records of this type are pointers to the canonical event location.

**Authority**: `convention` for events authored by user-scope resolvers; `hard` for events authored by `kernel.self` (migrations, reindex completions, init).

**On-disk location**: `ir/<scope>/_events/<event-id>.md` for the (I, R) pointer; canonical event payload remains in `.8os/events/YYYY/MM/DD/*.jsonl`.

**Bootstrap**: vendored at init.

#### §3.6.2 `_kernel.authorization`

**Purpose**: record an authorization decision per axiom 6, produced by the gatekeeper when a bridge crossing requires authorization.

**Projection-declared frontmatter**:
- `bridge_id`: the bridge being crossed.
- `subject_resolution`: the (I, R) the authorization permits.
- `authorized_by`: the human or hard-authority resolver granting authorization.
- `authorization_scope`: `single | session | persistent`.
- `granted_on`: timestamp.
- `expires_on`: optional timestamp; null for persistent authorizations.

**Body shape**: free-form rationale for the authorization, optional.

**Authority**: matches `authorized_by` authority; typically `hard`.

**On-disk location**: `ir/<scope>/_authorizations/<authorization-id>.md`.

**Bootstrap**: vendored at init.

#### §3.6.3 `_kernel.resolver-selection`

**Purpose**: record a selector decision when `kernel.selector.select` is invoked.

**Projection-declared frontmatter**:
- `subject_intention`: the (I, R) being resolved.
- `selected_resolver`: the resolver chosen.
- `candidate_resolvers`: array of resolvers considered.
- `selection_rationale`: brief structured rationale (cost weight, capability weight, authority weight, tiebreaker if any).
- `selected_on`: timestamp.

**Body shape**: free-form additional context, optional.

**Authority**: `convention` (selector decisions are conventional unless overridden).

**On-disk location**: `ir/<scope>/_selections/<selection-id>.md`.

**Bootstrap**: vendored at init.

#### §3.6.4 `_kernel.capability-update`

**Purpose**: record a calibration-driven update to a resolver's capability vector, produced by `kernel.calibrator`.

**Projection-declared frontmatter**:
- `resolver_id`: the resolver whose capabilities are being updated.
- `previous_capabilities`: capability vector before update.
- `updated_capabilities`: capability vector after update.
- `corpus_summary`: summary of the calibration corpus that drove the update (`{event_count, period_start, period_end}`).
- `updated_on`: timestamp.

**Body shape**: free-form rationale, optional.

**Authority**: `convention` (calibration updates are conventional; humans may supersede them with hard authority if calibration is judged wrong).

**On-disk location**: `ir/<scope>/_calibrations/<update-id>.md`.

**Bootstrap**: vendored at init.

---

## Section 4 — The eighteen SDK operations (clarifications, not respecified)

The eighteen operations from v0.1.0 §SDK Contract are preserved verbatim. v0.2 adds the following clarifications. Anything not clarified here follows v0.1.0.

### 4.1 `kernel.ir.new` — clarifications

- Honors projection-declared frontmatter extensions per §2.1. The input includes a single flat `frontmatter_extensions: {<field>: <value>, ...}` block; the kernel validates this against the union of required fields from all listed `projection_types`.
- Honors filename suffix from projection per §2.2.
- For (I, R)s into the `_kernel` scope, enforces `authority_level: hard` per §2.3.
- Foundational `_kernel`-scope records (the `_kernel` scope declaration and the five vendored kernel projection-type definitions) are authorable only through the `kernel.self` bridge at bootstrap. After bootstrap, they are read-only except via supersession events authored by humans with hard authority through their own identity bridge. This makes the kernel's self-knowledge auditable and amendable but never silently rewritten.
- Atomicity: the (I, R) file write, the tier 3 event write, and the index updates are one transaction. If validation fails on any projection-declared field, the operation rejects before any file is staged.

### 4.2 `kernel.ir.list` — clarifications

- Adds optional input `--include-kernel: bool` (default `false`). When `false`, results from the `_kernel` scope are excluded.
- The existing `--projection: <type>` filter works for kernel projection types. `ir.list --projection _kernel.resolver --include-kernel` returns all resolver-definition (I, R)s.

### 4.3 `kernel.ir.get` — clarifications

- Resolves ids that include the projection-declared filename suffix transparently. `ir.get expense-approval` and `ir.get expense-approval.prism` both resolve to the same (I, R) when the suffix is `.prism.md`.

### 4.4 `kernel.bridge.cross` — clarifications

- Reads bridge-definition from `ir/_kernel/bridge/<bridge-id>.md` rather than `.8os/bridges/<bridge-id>.yml` from v0.1.0.
- Otherwise unchanged.

### 4.5 `kernel.gatekeeper.check` — clarifications

- Reads the `_kernel.bridge` (I, R) for `requires_authorization`.
- Otherwise unchanged.

### 4.6 `kernel.selector.select` — clarifications

- Reads `_kernel.resolver` (I, R)s for cost and capability vectors.
- Otherwise unchanged.

### 4.7 `kernel.reindex` — clarifications

- Indexes content from `ir/_kernel/` alongside user-scope content. The same twelve indexes cover all (I, R)s regardless of scope.
- Otherwise unchanged.

### 4.8 Operations removed in v0.2

The following operations from v0.1.0 are **removed** in v0.2:

- `kernel.resolver.add` — use `kernel.ir.new` with `projection_types: [_kernel.resolver]`.
- `kernel.bridge.add` — use `kernel.ir.new` with `projection_types: [_kernel.bridge]`.

The functionality is preserved through `kernel.ir.new` with the appropriate projection type. The typed wrappers are not provided. Implementations targeting v0.1.0 callers must be updated.

### 4.9 No new operations

v0.2 introduces no new operations. The eighteen content operations of v0.1.0 minus the two removed typed operations equals sixteen operations. The kernel surface shrinks.

The deferred `kernel.surrogate.train` interface stub from v0.1.0 is preserved unchanged. Its full implementation remains deferred to a future block.

---

## Section 5 — Indexes (unchanged)

The twelve indexes from v0.1.0 §6 are preserved unchanged. They now index `_kernel` scope content alongside user-scope content. The same regeneration discipline γ applies.

The `projection-to-ids` index now includes `_kernel.*` projection types. `scope-to-ids` includes the `_kernel` scope.

No new indexes are added in v0.2.

---

## Section 6 — Tier 3 events (unchanged)

The tier 3 event JSONL schema from v0.1.0 §5 is preserved unchanged. Operations against the `_kernel` scope emit tier 3 events identically to operations on user content. The events are written to the same `.8os/events/YYYY/MM/DD/` paths.

---

## Section 7 — Migration from v0.1.0 to v0.2

A v0.1.0 repo migrates to v0.2 mechanically. The migration is one-way; there is no v0.1.0 backward-compatibility mode after v0.2 lands.

### 7.1 Migration steps, in order

1. **Convert `.8os/resolvers/<id>.yml` files to `ir/_kernel/resolver/<id>.md` (I, R)s.** Each YAML file becomes the body of an (I, R) of `projection_types: [_kernel.resolver]`. Frontmatter is generated: `id` matches the resolver-id, `tier: 1`, `scope: _kernel`, `authored_by: kernel.migration`, `authored_on: <migration-timestamp>`, `authority_level: hard`, etc. Resolver-specific fields (`cost`, `capability`, `bridge`, `model_name`) move from YAML body into projection-declared frontmatter.

2. **Convert `.8os/bridges/<id>.yml` files to `ir/_kernel/bridge/<id>.md`.** Same pattern as resolvers.

3. **Convert `.8os/projections/<id>.yml` (project-declared, not `_kernel`-prefixed) files to `ir/_kernel/projection/<id>.md`.** Same pattern.

4. **Convert `ir/<scope>/_scope.yml` files to `ir/_kernel/scope/<scope-id>.md` (I, R)s.** The `_scope.yml` files are removed; the scope's (I, R) content remains under `ir/<scope>/`.

5. **Add the five vendored kernel projection-definition (I, R)s** under `ir/_kernel/projection/` per §3. These are kernel-shipped, not migrated from v0.1.0 content.

6. **Add the three kernel-internal resolver (I, R)s** under `ir/_kernel/resolver/` per §3.3. Vendored.

7. **Run `kernel.reindex`.** The twelve indexes regenerate. Any drift surfaces as a CI failure under γ.

8. **Emit a single tier 3 event** recording the migration: scope `_ops`, authored through `kernel.self`, payload listing every (I, R) created and every file removed.

### 7.2 Migration tooling

A migration script is provided as part of v0.2 release (`scripts/migrate-v0.1-to-v0.2.py`). The script is mechanical and idempotent — running it twice on the same repo produces no change after the first run. The script does not require human input beyond confirmation to proceed.

### 7.3 Existing tests

The 51 tests passing under v0.1.0 must be re-validated against v0.2:

- Tests of `resolver.add` and `bridge.add` are removed.
- Tests that assert resolver/bridge/projection/scope content live at v0.1.0 paths are updated to v0.2 paths.
- New tests are added covering: kernel projection types, projection-declared frontmatter validation, filename suffix declaration, `_kernel` scope authority enforcement, the migration script idempotency.

The v0.2 acceptance criterion is: all v0.1.0 tests that survive the SDK trim pass; new v0.2 tests pass; CI passes the γ index-drift check.

---

## Section 8 — What v0.2 does not do

Surfacing constraints v0.2 declines to address, so future blocks know they are open:

- **v0.2 does not specify the surrogate training stack.** The interface stub remains. Training pipeline is a future block.
- **v0.2 does not add `kernel.apply`-style universal configuration operations.** The principled position is that `kernel.ir.new` with appropriate projection types already provides this; a separate `apply` operation would be sugar.
- **v0.2 does not specify the bee runtime, the dispatch loop, or the factory.** Those are Block 3.
- **v0.2 does not respecify the eighteen operations from v0.1.0.** It clarifies; it does not rewrite.
- **v0.2 does not introduce in-process SDKs in any language.** Subprocess CLI remains the reference. Conformance discipline from v0.1.0 §9 applies.

---

## Section 9 — Resolved open questions

OPEN-Q-010 (frontmatter extensions not honored): resolved by §2.1.
OPEN-Q-011 (no projection.add operation): resolved by removing typed configuration operations entirely; `ir.new` with `projection_types: [_kernel.projection]` replaces what `projection.add` would have been.
OPEN-Q-012 (slug/extension collision): resolved by §2.2.

OPEN-Q-005 through OPEN-Q-009 from Block 2 held under Block 2.5's workload. They are preserved as open under v0.2 with the same status as v0.1.0.

No new open questions are introduced by v0.2.

---

## Section 10 — Status

This is **v0.2.0**. It locks the principled refactor: kernel-configuration objects are kernel-defined projection types of (I, R), authored through the same SDK as user content. The eighteen operations of v0.1.0 minus two removed typed wrappers equal sixteen operations. The `_kernel` scope is reserved.

Future versions may add operations, projection types, or representation refinements but should preserve the principle that *every artifact the kernel manages is an (I, R)*. Departures from this principle indicate a flaw in the principle or a flaw in the design, to be resolved by amendment with explicit axiom-level reasoning.

The next block (Block 3) implements the factory: bee resolvers as `_kernel.resolver` (I, R)s, dispatch logic as production rules expressed as (I, R)s, the loop that watches the (I, R) graph for unresolved nodes and routes them to selected resolvers per axiom 5.

---

*End of Block 1 specification v0.2. Authored in Block 2.7. Supersedes v0.1.0.*
