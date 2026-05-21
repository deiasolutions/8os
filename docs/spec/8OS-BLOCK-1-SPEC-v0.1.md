---
id: 8OS-BLOCK-1-SPEC
version: 0.1.0
status: accepted
kind: derivation
scope: project
domain: 8os/representation
codename: ZORTZI
authored_by: Q88N + Claude (Block 1 derivation)
authored_on: 2026-04-26
supersedes: null
superseded_by: null
depends_on: 8OS-KERNEL-SPEC v0.1.0
revisit_when: implementation surfaces a contradiction with any axiom or SDK operation
provenance: derivation captured in conversation "8OS - Block 1"
---

# 8OS Block 1 Specification — On-Disk Representation and SDK Contract v0.1

## What this document is

This is the Block 1 derivation specification for **8OS** (codename **ZORTZI**). It defines
the concrete on-disk representation of the kernel and the SDK contract that mediates all
operations on it. Block 0 locked the eight axioms (the kernel ABI). Block 1 locks the
representation that satisfies them and the operation set that enforces them.

This document is the input contract for Block 2, which will implement the kernel binary
against the SDK specified here.

Everything in this document is derived from and constrained by the eight axioms in
8OS-KERNEL-SPEC v0.1.0. Any conflict between this document and the axioms is resolved in
favor of the axioms.

## Conventions

- **Paths** are repository-relative unless noted.
- **IDs** are stable, human-readable slugs assigned at creation, never reused, never
  silently mutated. Renames are supersession events.
- **References between (I, R) records** store IDs only, never paths. Path resolution goes
  through the kernel-maintained index.
- **Timestamps** are ISO 8601 UTC with millisecond precision.
- **YAML serialization** is canonical: sorted keys, LF line endings, no trailing
  whitespace.
- **JSON serialization** is canonical: sorted keys, UTF-8, no trailing whitespace.
- **`_` prefix** on a directory or filename signals kernel-managed content not intended
  for direct human edit (e.g. `_ops/`, `_scope.yml`, `_node.md`, `_kernel/`, `_index.yml`,
  `_checksum.yml`).

---

## Section 1 — On-disk representation

### 1.1 Folder tree

```
<repo-root>/
├── .8os/                          # kernel metadata; never directly edited by users
│   ├── version                    # semver of the kernel ABI this repo targets
│   ├── resolvers/                 # resolver registrations (axiom 5)
│   │   ├── <resolver-id>.yml      # one file per resolver
│   │   └── _index.yml             # generated; cached lookup
│   ├── bridges/                   # bridge configurations (axiom 0)
│   │   └── <bridge-id>.yml        # one file per bridge
│   ├── projections/               # projection-type declarations (axiom 1)
│   │   ├── _kernel/               # ships with kernel; projects cannot write here
│   │   │   ├── tier3-event.yml    # JSONL → (I, R) virtual projection mapping
│   │   │   ├── authorization.yml  # built-in tier 2 schema extension
│   │   │   ├── resolver-selection.yml
│   │   │   └── capability-update.yml
│   │   └── <project-projection>.yml  # project-declared projection types
│   ├── surrogates/                # surrogate lineage (axiom 7)
│   │   └── <surrogate-id>/
│   │       ├── lineage.yml        # what was approximated, when, with what corpus
│   │       ├── training-set.jsonl # frozen training corpus reference
│   │       └── validation.yml     # holdout results, drift estimates
│   ├── events/                    # ABCDEFG event capture (axiom 7 fuel)
│   │   ├── YYYY/MM/DD/
│   │   │   └── <file>.jsonl       # append-only resolution events, one JSON per line
│   │   └── raw/                   # large payload sidecars
│   │       └── <event-id>.json
│   ├── index/                     # generated indexes; committed; CI-checked
│   │   ├── id-to-path.yml
│   │   ├── path-to-id.yml
│   │   ├── scope-to-ids.yml
│   │   ├── tier-to-ids.yml
│   │   ├── projection-to-ids.yml
│   │   ├── resolver-to-events.yml
│   │   ├── bridge-to-resolvers.yml
│   │   ├── deps-forward.yml
│   │   ├── deps-reverse.yml
│   │   ├── temporal.yml
│   │   ├── surrogate-lineage.yml
│   │   └── _checksum.yml
│   └── sdk/
│       └── schemas/
│           ├── <op-name>.v<n>.input.json
│           ├── <op-name>.v<n>.output.json
│           └── <op-name>.v<n>.error.json
├── ir/                            # the (I, R) graph (axiom 1)
│   ├── _ops/                      # tier 2 records (kernel-authored)
│   │   ├── _scope.yml
│   │   ├── resolver-selection/
│   │   │   └── <event-id>.md
│   │   ├── authorization/
│   │   │   └── <event-id>.md
│   │   └── capability-update/
│   │       └── <event-id>.md
│   ├── <user-scope>/              # tier 1 user content
│   │   ├── _scope.yml             # scope declaration (axiom 3)
│   │   ├── <ir-node>.md           # collapsed (I, R)
│   │   └── <ir-node>/             # expanded (I, R) — folder-as-fractal
│   │       ├── _node.md           # the parent (I, R), collapsed view
│   │       └── <child-ir>.md      # children
│   └── <user-scope-2>/
│       └── ...
├── projections/                   # generated views over ir/ (ADRs, specs, etc.)
│   └── <projection-type>/
│       └── <name>.md
├── .githooks/
│   └── pre-push                   # opt-in: runs `8os reindex --check`
├── .github/
│   └── workflows/
│       └── 8os-index-check.yml    # CI enforcement of γ
├── .gitattributes                 # marks .8os/index/* as generated
├── .gitignore
├── 8OS-KERNEL-SPEC-v0.1.md        # vendored axioms (Block 0 spec)
├── 8OS-BLOCK-1-SPEC.md            # vendored representation + SDK (this doc)
└── README.md
```

### 1.2 File types

- **`.md` (I, R) record** — canonical artifact for tier 1 and tier 2. YAML frontmatter
  carries machine-queryable metadata; markdown body carries human-readable Intention and
  Resolution. One file = one (I, R).
- **`.yml` config / index / scope / lineage** — pure structured data. No prose.
- **`.jsonl` event stream** — append-only, line-delimited JSON. One line per event.
  Optimized for streaming writes and ML training extraction.
- **`.json` raw payload sidecar** — large payloads (LLM transcripts, simulation outputs)
  referenced from event lines.
- **JSON Schema** — at `.8os/sdk/schemas/`, versioned per operation.

### 1.3 Naming conventions

- Resolvers: `.8os/resolvers/<resolver-id>.yml` where `<resolver-id>` is a stable slug,
  unique within the repo.
- Bridges: `.8os/bridges/<bridge-id>.yml`, same rules.
- Projections: `.8os/projections/<type>.yml` (project) or `.8os/projections/_kernel/<type>.yml`
  (kernel-shipped).
- Scopes: `ir/<scope-id>/_scope.yml`. Scope IDs are unique across the repo.
- (I, R) records collapsed: `ir/<scope>/<slug>.md` or `ir/<scope>/<parent>/<slug>.md`.
- (I, R) records expanded: `ir/<scope>/<slug>/_node.md` plus children at
  `ir/<scope>/<slug>/<child-slug>.md`.
- Tier 2 records: `ir/_ops/<category>/<event-id>.md` where `<category>` is one of
  `resolver-selection`, `authorization`, `capability-update`.
- Tier 3 events: `.8os/events/YYYY/MM/DD/<file>.jsonl`. Sharding within a day is permitted
  if volume demands; default is one file per day per writer.
- Raw payloads: `.8os/events/raw/<event-id>.json`.
- Surrogates: `.8os/surrogates/<surrogate-id>/lineage.yml`, `training-set.jsonl`,
  `validation.yml`.

### 1.4 Tier model

Three tiers. All (I, R)s. Identical schema. Tier is a queryable filter, not a class
distinction.

- **Tier 1 (substantive)** — user-meaningful decisions: ADRs, specs, captured policies.
  Default visibility for human-facing traversal. Storage: `ir/<user-scope>/` as `.md`.
- **Tier 2 (operational)** — kernel-authored records: resolver-selection, authorization,
  capability-update. Storage: `ir/_ops/<category>/` as `.md`.
- **Tier 3 (ephemeral)** — per-invocation resolution events. Massive volume, surrogate-
  training fuel. Storage: `.8os/events/YYYY/MM/DD/<file>.jsonl` as JSONL lines, projected
  to (I, R) shape on read via `.8os/projections/_kernel/tier3-event.yml`.

### 1.5 Collapse / expand

A node lives at `ir/<scope>/<slug>.md` when collapsed. When expanded, it becomes
`ir/<scope>/<slug>/_node.md` plus sibling child files. The transformation is a kernel
operation (`kernel.ir.expand` / `kernel.ir.collapse`); manual `mv` is discouraged but
recoverable via `kernel.reindex`. Git rename detection preserves blame and history because
content is preserved across the rename.

### 1.6 Path stability

References between (I, R)s store IDs only. Paths are resolved via
`.8os/index/id-to-path.yml`. When a node moves (expand/collapse/scope refactor), the index
is regenerated; references are unchanged. A genuine ID change is a supersession event,
never a silent mutation.

---

## Section 2 — (I, R) frontmatter schema

Applies to every tier 1 and tier 2 (I, R) record. Tier 3 records have the same logical
shape, projected from JSONL lines via `.8os/projections/_kernel/tier3-event.yml`.

```yaml
---
# === IDENTITY (axiom 1) ===
id: <stable-slug>                     # globally unique within repo; required
kind: ir-node                         # constant discriminator
tier: 1 | 2 | 3                       # required; mandatory authoring decision
projection_types: [<string>, ...]     # opaque to kernel; each must exist in .8os/projections/

# === FRACTAL (axiom 2) ===
collapsed_summary: <one-sentence>     # opaque view; required
expanded_into: <id-or-null>           # ID of child folder root if expanded
parent: <id-or-null>                  # ID of parent _node if this is a child

# === SCOPE & PROPAGATION (axiom 3) ===
scope: <scope-id>                     # references ir/<scope>/_scope.yml
depends_on: [<id>, ...]               # explicit upstream (I, R) dependencies
visible_to: [<scope-id>, ...]         # downstream visibility; default = own scope

# === TEMPORAL VALIDITY (axiom 4) ===
resolved_at: <iso-8601-or-null>
valid_through: <iso-8601-or-null>
revalidate_trigger: <free-text-or-null>
status: open | resolved | superseded | stale

# === RESOLVER (axiom 5) ===
resolver: <resolver-id-or-null>       # null until resolved
resolution_event: <event-id-or-null>  # references .8os/events/.../<event-id>

# === PROVENANCE & AUTHORITY (axiom 6) ===
authored_by: <agent-or-human-id>      # required
authored_on: <iso-8601>               # required
authority_level: hard | convention | uncalibrated  # required
bridge_type: <bridge-id-or-null>      # null = inside resolution
supersedes: <id-or-null>
superseded_by: <id-or-null>

# === SURROGATE LINEAGE (axiom 7, only if applicable) ===
surrogate_of: <resolver-id-or-null>

# === PROJECTION-SPECIFIC EXTENSIONS ===
# Projection types may declare additional required frontmatter fields in their
# .8os/projections/<type>.yml. The kernel does not interpret these; consumers do.
# Example for projection_types: [authorization]:
authorizes:
  bridge: <bridge-id>
  for_ir: <ir-id>
  scope_of_authority: single | session | until <iso-8601>
---

# Intention
<prose>

# Resolution
<prose, populated when status == resolved>
```

Required fields (validation enforced by kernel): `id`, `kind`, `tier`, `collapsed_summary`,
`scope`, `status`, `authored_by`, `authored_on`, `authority_level`.

---

## Section 3 — Resolver YAML schema

One file per resolver: `.8os/resolvers/<resolver-id>.yml`.

```yaml
id: <resolver-id>                     # required; stable
kind: resolver
display_name: <human-readable>

# === BRIDGE LINKAGE (axiom 0) ===
bridge: <bridge-id-or-null>           # null = pure-inside resolver

# === COST VECTOR (axiom 5, 3Cs) ===
cost:
  clock:
    unit: ms
    declared: <number-or-null>        # designer estimate
    measured_p50: <number-or-null>    # populated by event aggregation
    measured_p95: <number-or-null>
  coin:
    unit: usd
    declared: <number-or-null>
    measured_p50: <number-or-null>
  carbon:
    unit: g-co2e
    declared: <number-or-null>
    measured_p50: <number-or-null>

# === CAPABILITY VECTOR (axiom 5, σπαρ) — per-domain ===
capability:
  - domain: <domain-string>
    sigma:
      declared: <0.0-1.0-or-null>
      measured: <0.0-1.0-or-null>
      sample_n: <int>
    pi:
      declared: <0.0-1.0-or-null>
      measured: <0.0-1.0-or-null>
    alpha:
      declared: <0.0-1.0-or-null>
      measured: <0.0-1.0-or-null>
    rho:
      declared: <0.0-1.0-or-null>
      measured: <0.0-1.0-or-null>

# === SURROGATE LINEAGE (axiom 7, only if applicable) ===
surrogate_of: <resolver-id-or-null>
surrogate_lineage_ref: <path-or-null>  # e.g. .8os/surrogates/<id>/lineage.yml

# === PROVENANCE (axiom 6) ===
authored_by: <agent-or-human>
authored_on: <iso-8601>
authority_default: hard | convention | uncalibrated
```

`measured_*` fields are populated by event aggregation, never hand-edited.

---

## Section 4 — Bridge YAML schema

One file per bridge: `.8os/bridges/<bridge-id>.yml`.

```yaml
id: <bridge-id>                       # required; stable
kind: bridge
display_name: <human-readable>

# === OUTSIDE TYPE (axiom 0) ===
outside_type: llm-api | human-reviewer | physics-sim | sensor | external-service | cpu-instruction | other
outside_label: <free-text>

# === ENDPOINT ===
endpoint:
  protocol: https | local | stdin | webhook | other
  address: <url-or-path-or-null>
  auth_ref: <secrets-key-or-null>     # references external secret; never inline

# === CAPABILITY DECLARATION ===
synchronous: true | false
batchable: true | false
rate_limit:
  unit: requests-per-minute
  value: <int-or-null>

# === COST DEFAULTS ===
default_cost:
  clock_ms_p50: <number-or-null>
  coin_usd_p50: <number-or-null>
  carbon_g_p50: <number-or-null>

# === SAFETY / GOVERNANCE ===
requires_authorization: true | false
authorization_authority: hard | convention | uncalibrated

# === PROVENANCE ===
authored_by: <agent-or-human>
authored_on: <iso-8601>
status: active | deprecated | quarantined
```

`outside_type` is enumerated, not free-form. Extension is a kernel-version concern, not a
project concern.

---

## Section 5 — Tier 3 event JSONL schema

Append-only at `.8os/events/YYYY/MM/DD/<file>.jsonl`. One JSON object per line.

```json
{
  "event_id": "<ulid>",
  "event_type": "resolution" | "assessment" | "promotion" | "operation",
  "ts": "<iso-8601-with-ms>",

  "ir_node_id": "<id>",
  "ir_node_path_at_event": "<path-snapshot>",

  "resolver_id": "<resolver-id>",
  "bridge_id": "<bridge-id-or-null>",

  "intention": {
    "text": "<str>",
    "context_refs": ["<id>", "..."],
    "scope": "<scope-id>",
    "depth": <int>
  },

  "resolution": {
    "text": "<str>",
    "structured": { },
    "authority_level": "hard | convention | uncalibrated"
  },

  "cost_actual": {
    "clock_ms": <number>,
    "coin_usd": <number>,
    "carbon_g": <number>,
    "model_name": "<str-or-null>",
    "tokens_in": <int-or-null>,
    "tokens_out": <int-or-null>
  },

  "capability_assessment": {
    "domain": "<domain>",
    "sigma": <0.0-1.0-or-null>,
    "pi": <0.0-1.0-or-null>,
    "alpha": <0.0-1.0-or-null>,
    "rho": <0.0-1.0-or-null>,
    "assessor": "<agent-or-human-id>",
    "assessed_at": "<iso-8601-or-null>"
  },

  "supersedes_event": "<event-id-or-null>",
  "outcome": "accepted | rejected | superseded | pending",

  "raw_payload_ref": "<path-or-null>"
}
```

`capability_assessment` is optional at write time; populated later via follow-up
`event_type: assessment` records that reference the original via `supersedes_event`.

`raw_payload_ref` points to `.8os/events/raw/<event-id>.json` for large payloads. Summary
lives in the event line; full payload lives in the sidecar.

`ir_node_path_at_event` is a snapshot, not a live reference. Events record where the node
was when the event occurred.

A promoted JSONL line carries an additional marker line appended after promotion:
```json
{"event_id": "<orig>", "promoted_to": "<new-ir-id>", "promoted_at": "<ts>"}
```

---

## Section 6 — Index set

Twelve indexes under `.8os/index/`. All committed. All regenerated deterministically by
`kernel.reindex`. All checked by `kernel.reindex --check`.

| File | Contents | Drives |
|------|----------|--------|
| `id-to-path.yml` | `<id>` → current filesystem path (or JSONL line locator for tier 3) | All reference resolution |
| `path-to-id.yml` | Reverse of above | Agent reads path, needs ID |
| `scope-to-ids.yml` | `<scope-id>` → list of IDs in that scope | Axiom 3 scope queries |
| `tier-to-ids.yml` | `1 \| 2 \| 3` → list of IDs (tier 3 as count + JSONL refs) | Tier filter on traversal |
| `projection-to-ids.yml` | `<projection-type>` → list of IDs | Projection-typed queries |
| `resolver-to-events.yml` | `<resolver-id>` → list of event IDs with date partitions | Surrogate training extraction |
| `bridge-to-resolvers.yml` | `<bridge-id>` → list of resolver IDs using it | Bridge deprecation analysis |
| `deps-forward.yml` | `<id>` → list of IDs it depends on | Forward traversal |
| `deps-reverse.yml` | `<id>` → list of IDs depending on it | Axiom 3 blast-radius |
| `temporal.yml` | Sorted `(valid_through, id)` and `(revalidate_trigger, id)` | Axiom 4 freshness checks |
| `surrogate-lineage.yml` | `<surrogate-id>` → approximated resolver, training count, validation, drift | Axiom 7 audit |
| `_checksum.yml` | SHA-256 of each above + input-set hash | Two-level cheap-check |

### 6.1 Regeneration discipline (γ)

CI-enforced + manual locally. `kernel.reindex` writes; `kernel.reindex --check` verifies.
On mismatch, exit non-zero with structured drift diff. CI runs `--check` on every PR;
stale index = red build = unmergeable. Local pre-push hook is opt-in via
`git config core.hooksPath .githooks`. Determinism is non-negotiable: byte-identical output
for byte-identical input regardless of OS, locale, or filesystem ordering.

### 6.2 Two-level check

`_checksum.yml` records the input-set hash (sorted IDs of all contributing records). If
unchanged from committed, indexes are trusted without recomputation. If changed, full
recompute and compare. Common case (no IR changes) is a hash compare; expensive case
(changes present) is a full pass.

---

## Section 7 — SDK contract

### 7.1 Wire format

JSON object on stdin to `8os <op>`. JSON object on stdout for success, JSON object on
stderr for error. Exit code 0 = success, exit code 1 = error. No interleaved logging on
stdout/stderr.

Each operation has versioned schemas at `.8os/sdk/schemas/<op>.v<n>.{input,output,error}.json`.
All operations in this contract are at v1. Kernel validates input before execution and
output before return.

### 7.2 Common envelopes

Success:
```json
{
  "schema_version": 1,
  "op": "<op-name>",
  "status": "ok",
  "data": { <op-specific> },
  "event_id": "<ulid-or-null>",
  "indexes_updated": ["<index-name>", ...]
}
```

Error:
```json
{
  "schema_version": 1,
  "op": "<op-name>",
  "status": "error",
  "code": "<ERROR_CODE>",
  "message": "<human-readable>",
  "context": {
    "axiom_violated": <int-or-null>,
    "input_field": "<dotted-path-or-null>",
    "offending_value": <any-or-null>,
    "suggested_action": "<str-or-null>"
  }
}
```

### 7.3 Stable error code enumeration

```
SCHEMA_INVALID
KERNEL_OUTPUT_INVALID
NOT_FOUND
ALREADY_EXISTS
INVALID_STATE
AUTHORIZATION_REQUIRED
AUTHORITY_INSUFFICIENT
SCOPE_VIOLATION
DEPENDENCY_BROKEN
INDEX_DRIFT
ATOMICITY_FAILURE
ATOMICITY_FAILURE_PARTIAL
BRIDGE_UNREACHABLE
EVENT_WRITE_FAILED_AFTER_CROSSING
KERNEL_VERSION_MISMATCH
```

### 7.4 Atomicity vocabulary

- **single-commit, all-or-nothing** — stage all writes to `.8os/.staging/<op-id>/`,
  validate, atomically rename into final paths, append tier 3 event, regenerate listed
  indexes. Failure at any step removes staged writes; on-disk state moves from "pre" to
  "post" with no intermediate visible state.
- **no-commit, read-only** — pure query. Idempotent.
- **best-effort with documented failure mode** — `kernel.bridge.cross` only. Outside
  contact is non-atomic by nature; failure modes are enumerated and detectable.

### 7.5 Standard mutating execution order

For every mutating operation:

1. Validate input against `.input.json` schema.
2. Read kernel state needed for the operation.
3. Stage all writes under `.8os/.staging/<op-id>/`.
4. Validate the would-be post-state.
5. Atomic rename from staging to final paths.
6. Append tier 3 event line.
7. Regenerate listed indexes.
8. Validate output against `.output.json` schema.
9. Emit success envelope on stdout, exit 0.

Failure at steps 1–7 → staging removed → error envelope on stderr, exit 1. Failure at step
8 → `KERNEL_OUTPUT_INVALID` (kernel bug; on-disk state is correct).

### 7.6 Operation set (eighteen operations, all v1)

#### 7.6.1 `kernel.init`

**Input**:
```json
{ "project_name": "<str>", "primary_scope_id": "<str>",
  "primary_operator_id": "<str>", "kernel_version": "<semver>" }
```
**Output data**:
```json
{ "bootstrap_ir_id": "<id>", "bootstrap_path": "<path>", "primary_scope_path": "<path>" }
```
**Atomicity**: single-commit, all-or-nothing.
**Axioms**: 0, 1, 6.
**Files**: read `.8os/version`; write `ir/<scope>/_scope.yml`, `ir/<scope>/000-bootstrap.md`,
`.8os/events/<date>/<file>.jsonl`, all twelve indexes.
**Errors**: `KERNEL_VERSION_MISMATCH`, `ALREADY_EXISTS`, `SCHEMA_INVALID`.

#### 7.6.2 `kernel.reindex`

**Input**: `{ "mode": "full" | "check" }`
**Output data (full)**: `{ "mode": "full", "input_set_hash": "<sha256>", "indexes_written": 12 }`
**Output data (check, no drift)**: `{ "mode": "check", "input_set_hash": "<sha256>", "drift_detected": false }`
**Output (check, drift)**: error with `code: INDEX_DRIFT`, `context.drift_diff`.
**Atomicity**: full = single-commit across all twelve indexes; check = no-commit.
**Axioms**: 3, 4, 7.
**Files**: read `ir/**`, `.8os/resolvers/**`, `.8os/bridges/**`, `.8os/events/**`; write
all twelve `.8os/index/*.yml` (full only).
**Errors**: `INDEX_DRIFT` (check only).
**Note**: Emits no tier 3 event (would create infinite recursion).

#### 7.6.3 `kernel.ir.new`

**Input**:
```json
{ "scope_id": "<str>", "slug": "<str>", "tier": 1|2|3,
  "intention_text": "<str>", "projection_types": ["<str>", ...],
  "parent_id": "<id>"|null, "depends_on": ["<id>", ...],
  "authority_level": "hard"|"convention"|"uncalibrated", "authored_by": "<str>" }
```
**Output data**: `{ "ir_id": "<id>", "path": "<path>", "tier": <int> }`
**Atomicity**: single-commit, all-or-nothing.
**Axioms**: 1, 2, 3, 6.
**Files**: read `id-to-path`, `scope-to-ids`, `.8os/projections/*.yml`; write tier 1/2 →
`ir/<resolved-path>/<slug>.md`, tier 3 → JSONL append; plus tier 3 event for the operation;
plus `id-to-path`, `path-to-id`, `scope-to-ids`, `tier-to-ids`, `projection-to-ids`,
`deps-forward`, `deps-reverse`, `_checksum`.
**Errors**: `ALREADY_EXISTS`, `NOT_FOUND`, `DEPENDENCY_BROKEN`, `SCHEMA_INVALID`.

#### 7.6.4 `kernel.ir.resolve`

**Input**:
```json
{ "ir_id": "<id>", "resolver_id": "<id>", "resolution_text": "<str>",
  "cost_actual": { "clock_ms": <num>, "coin_usd": <num>, "carbon_g": <num>,
                   "model_name": "<str>"|null, "tokens_in": <int>|null, "tokens_out": <int>|null },
  "bridge_id": "<id>"|null, "authorization_id": "<id>"|null,
  "valid_through": "<iso8601>"|null, "revalidate_trigger": "<str>"|null }
```
**Output data**:
```json
{ "ir_id": "<id>", "ir_status": "resolved", "resolved_at": "<iso8601>",
  "valid_through": "<iso8601>"|null, "resolution_event_id": "<ulid>" }
```
**Atomicity**: single-commit, all-or-nothing.
**Axioms**: 4, 5, 6, 7.
**Files**: read target (I, R), resolver YAML, bridge YAML if applicable, authorization
(I, R) if supplied; write target (I, R), tier 3 event, `temporal`, `resolver-to-events`,
`_checksum`.
**Errors**: `INVALID_STATE`, `AUTHORIZATION_REQUIRED`, `NOT_FOUND`.

#### 7.6.5 `kernel.ir.expand`

**Input**: `{ "ir_id": "<id>" }`
**Output data**: `{ "ir_id": "<id>", "old_path": "<path>", "new_path": "<path>" }`
**Atomicity**: single-commit, all-or-nothing. File move must be a single atomic rename
detectable as such by git.
**Axioms**: 2.
**Files**: read `id-to-path`, source `.md`; write `<path>/<slug>/_node.md`, tier 3 event,
`id-to-path`, `path-to-id`, `_checksum`; delete source `.md`.
**Errors**: `INVALID_STATE`, `NOT_FOUND`, `ATOMICITY_FAILURE`.

#### 7.6.6 `kernel.ir.collapse`

**Input**: `{ "ir_id": "<id>" }`
**Output data**: `{ "ir_id": "<id>", "old_path": "<path>", "new_path": "<path>" }`
**Atomicity**: single-commit, all-or-nothing. Refuses on non-empty expansion.
**Axioms**: 2.
**Files**: read `id-to-path`, source `_node.md`, list of folder; write
`<path>/<slug>.md`, tier 3 event, `id-to-path`, `path-to-id`, `_checksum`; delete source
`_node.md`, then empty folder.
**Errors**: `INVALID_STATE`, `NOT_FOUND`.

#### 7.6.7 `kernel.ir.promote`

**Input**:
```json
{ "event_id": "<ulid>", "to_tier": 1|2, "target_scope": "<id>",
  "target_slug": "<str>", "authored_by": "<str>",
  "authority_level": "hard"|"convention"|"uncalibrated" }
```
**Output data**:
```json
{ "new_ir_id": "<id>", "new_path": "<path>",
  "promoted_from_event": "<ulid>", "original_jsonl_marked": true }
```
**Atomicity**: single-commit, all-or-nothing across new (I, R), JSONL marker append, tier
3 event, indexes.
**Axioms**: 1, 6.
**Files**: read source JSONL, `.8os/projections/_kernel/tier3-event.yml`; write new tier
1/2 (I, R), source JSONL with marker appended, tier 3 event, seven indexes.
**Errors**: `NOT_FOUND`, `ALREADY_EXISTS`, `INVALID_STATE`.

#### 7.6.8 `kernel.ir.supersede`

**Input**:
```json
{ "old_ir_id": "<id>", "new_intention_text": "<str>",
  "authored_by": "<str>", "reason": "<str>" }
```
**Output data**: `{ "old_ir_id": "<id>", "new_ir_id": "<id>", "new_path": "<path>" }`
**Atomicity**: single-commit, all-or-nothing.
**Axioms**: 4, 6.
**Files**: read old (I, R); write new (I, R), updated old (I, R), tier 3 event, seven
indexes.
**Errors**: `INVALID_STATE`, `NOT_FOUND`.

#### 7.6.9 `kernel.bridge.add`

**Input**: full bridge YAML schema fields (see Section 4).
**Output data**: `{ "bridge_id": "<id>", "path": "<path>" }`
**Atomicity**: single-commit, all-or-nothing.
**Axioms**: 0, 6.
**Files**: read `bridge-to-resolvers`; write `.8os/bridges/<id>.yml`, tier 3 event,
`bridge-to-resolvers`, `_checksum`.
**Errors**: `ALREADY_EXISTS`, `SCHEMA_INVALID`.

#### 7.6.10 `kernel.resolver.add`

**Input**: full resolver YAML schema fields (see Section 3).
**Output data**: `{ "resolver_id": "<id>", "path": "<path>" }`
**Atomicity**: single-commit, all-or-nothing.
**Axioms**: 5, 6.
**Files**: read bridge YAML if `bridge_id` set, `bridge-to-resolvers`; write
`.8os/resolvers/<id>.yml`, tier 3 event, `bridge-to-resolvers`, `resolver-to-events`,
`_checksum`.
**Errors**: `ALREADY_EXISTS`, `NOT_FOUND`, `SCHEMA_INVALID`.

#### 7.6.11 `kernel.bridge.cross`

**Input**:
```json
{ "bridge_id": "<id>", "resolver_id": "<id>", "for_ir_id": "<id>",
  "authorization_id": "<id>"|null, "payload": <opaque> }
```
**Output data**:
```json
{ "response": <opaque>,
  "cost_actual": { "clock_ms": <num>, "coin_usd": <num>, "carbon_g": <num>,
                   "model_name": "<str>"|null, "tokens_in": <int>|null, "tokens_out": <int>|null },
  "raw_payload_ref": "<path>"|null }
```
**Atomicity**: best-effort with documented failure mode. `BRIDGE_UNREACHABLE` = no event
written, no state change. `EVENT_WRITE_FAILED_AFTER_CROSSING` = outside contacted, event
record lost; response payload returned in error context so caller can retry the event
write.
**Axioms**: 0, 5, 6, 7.
**Files**: read bridge YAML, resolver YAML, authorization (I, R); write
`.8os/events/<date>/<file>.jsonl`, optional `.8os/events/raw/<event-id>.json`,
`resolver-to-events`, `_checksum`.
**Errors**: `AUTHORIZATION_REQUIRED`, `BRIDGE_UNREACHABLE`,
`EVENT_WRITE_FAILED_AFTER_CROSSING`, `NOT_FOUND`.

#### 7.6.12 `kernel.authorize`

**Input**:
```json
{ "bridge_id": "<id>", "for_ir_id": "<id>"|null,
  "scope_of_authority": "single"|"session"|"until",
  "valid_through": "<iso8601>"|null,
  "cost_ceiling": { "coin_usd": <num>|null, "carbon_g": <num>|null, "clock_ms": <num>|null }|null,
  "authored_by": "<str>" }
```
**Output data**:
```json
{ "authorization_ir_id": "<id>", "path": "<path>", "valid_through": "<iso8601>"|null }
```
**Atomicity**: single-commit, all-or-nothing.
**Axioms**: 1, 4, 6.
**Files**: read bridge YAML, scope of `for_ir_id`, author authority; write
`ir/_ops/authorization/<event-id>.md`, tier 3 event, eight indexes (`id-to-path`,
`path-to-id`, `scope-to-ids`, `tier-to-ids`, `projection-to-ids`, `temporal`,
`deps-forward`, `deps-reverse`, `_checksum`).
**Errors**: `AUTHORITY_INSUFFICIENT`, `NOT_FOUND`.

#### 7.6.13 `kernel.gatekeeper.check`

**Input**:
```json
{ "bridge_id": "<id>", "resolver_id": "<id>",
  "for_ir_id": "<id>", "authorization_id": "<id>"|null }
```
**Output data**:
```json
{ "permitted": true|false, "reason": "<str>",
  "authorization_used": "<id>"|null, "valid_through": "<iso8601>"|null }
```
**Atomicity**: no-commit, read-only. Idempotent. No tier 3 event (calling operation
records the check).
**Axioms**: 6.
**Files**: read bridge YAML, resolver YAML, authorization (I, R) or scan
`ir/_ops/authorization/` filtered through `temporal.yml`.
**Errors**: `NOT_FOUND`.

#### 7.6.14 `kernel.selector.select`

**Input**:
```json
{ "for_ir_id": "<id>", "domain": "<str>",
  "demands": { "min_sigma": <num>|null, "min_pi": <num>|null,
               "min_alpha": <num>|null, "min_rho": <num>|null,
               "max_clock_ms": <num>|null, "max_coin_usd": <num>|null, "max_carbon_g": <num>|null },
  "candidate_resolver_ids": ["<id>", ...]|null }
```
**Output data**:
```json
{ "selected_resolver_id": "<id>", "selection_ir_id": "<id>", "selection_path": "<path>",
  "fitness_scores": [ { "resolver_id": "<id>", "score": <num>,
                        "breakdown": { "sigma_match": <num>, "cost_pressure": <num>, "availability": <num> } }, ... ] }
```
**Atomicity**: single-commit, all-or-nothing.
**Axioms**: 1, 5, 6.
**Files**: read all (or filtered) `.8os/resolvers/*.yml`, target (I, R); write
`ir/_ops/resolver-selection/<event-id>.md`, tier 3 event, seven indexes.
**Errors**: `NOT_FOUND`, `SCHEMA_INVALID`. (No-candidate-satisfies is a successful
selection record with `selected = null` plus explanation.)

#### 7.6.15 `kernel.ir.get`

**Input**:
```json
{ "ir_id": "<id>", "view": "collapsed"|"expanded"|"full", "include_body": true|false }
```
**Output data**:
```json
{ "ir_id": "<id>", "path": "<path>", "tier": <int>,
  "frontmatter": { <full schema> },
  "intention_text": "<str>"|null, "resolution_text": "<str>"|null,
  "children": [ { "ir_id": "<id>", "collapsed_summary": "<str>" }, ... ]|null,
  "subgraph": <recursive-structure>|null }
```
**Atomicity**: no-commit, read-only.
**Axioms**: 2.
**Files**: read `id-to-path`, target (I, R), recursively for `expanded`/`full`.
**Errors**: `NOT_FOUND`.

#### 7.6.16 `kernel.ir.list`

**Input**:
```json
{ "scope_id": "<id>"|null, "tier": [1|2|3, ...]|null,
  "projection_type": "<str>"|null,
  "status": ["open"|"resolved"|"superseded"|"stale", ...]|null,
  "valid_at": "<iso8601>"|null, "authored_by": "<str>"|null,
  "authority_level": ["hard"|"convention"|"uncalibrated", ...]|null,
  "limit": <int>, "offset": <int> }
```
Default `tier` filter is `[1]`. All filters AND-composed.
**Output data**:
```json
{ "results": [ { "ir_id": "<id>", "path": "<path>", "tier": <int>,
                 "collapsed_summary": "<str>", "status": "<str>" }, ... ],
  "total_matching": <int>, "returned": <int> }
```
**Atomicity**: no-commit, read-only.
**Axioms**: 3, 4, 6.
**Files**: read indexes; for `collapsed_summary`, the (I, R) files of the result page.
**Errors**: `SCHEMA_INVALID`.

#### 7.6.17 `kernel.ir.deps`

**Input**:
```json
{ "ir_id": "<id>", "direction": "forward"|"reverse"|"both",
  "max_depth": <int>, "tier_filter": [1|2|3, ...]|null }
```
**Output data**:
```json
{ "ir_id": "<id>", "direction": "<str>", "depth_reached": <int>,
  "graph": [ { "ir_id": "<id>", "depth": <int>, "via": ["<id>", ...] }, ... ],
  "truncated": true|false }
```
**Atomicity**: no-commit, read-only.
**Axioms**: 3.
**Files**: read `deps-forward` and/or `deps-reverse`, `scope-to-ids` for tier filter.
**Errors**: `NOT_FOUND`.

#### 7.6.18 `kernel.event.get`

**Input**: `{ "event_id": "<ulid>", "include_raw_payload": true|false }`
**Output data**:
```json
{ "event_id": "<ulid>", "event_record": { <full event schema> },
  "raw_payload": <opaque>|null, "promoted_to_ir_id": "<id>"|null,
  "ir_projection": { <(I, R) frontmatter as virtual projection> } }
```
**Atomicity**: no-commit, read-only.
**Axioms**: 1, 7.
**Files**: read target JSONL file, optional `.8os/events/raw/<event-id>.json`.
**Errors**: `NOT_FOUND`.

### 7.7 Deferred operation

`kernel.surrogate.train` — interface-only in v1. Reads `.8os/events/` filtered by
`resolver_id`, produces a frozen training corpus reference, registers a new resolver with
`surrogate_of: <original>`, writes `lineage.yml` and `validation.yml`. Full schema
deferred per OPEN-Q-002.

---

## Section 8 — v0.2 migration path

The schemas in `.8os/sdk/schemas/` are the migration. v0.2 introduces an in-process Python
SDK that implements the same operations against the same schemas and produces the same
on-disk effects. The v0.1 subprocess CLI remains as the reference behavior. v0.2 ships
with a conformance test that runs identical inputs through both the subprocess CLI and the
in-process SDK against snapshot-restored kernel states and compares success/error
envelopes, on-disk diff, and tier 3 event content (with timestamps and event IDs
normalized for comparison). Any divergence is a v0.2 bug; the subprocess CLI is the
reference. The conformance test is itself an (I, R) projection in the v0.2 repo, recording
its results as tier 3 events.

---

## Section 9 — Open questions

### OPEN-Q-001 — Human override of kernel-authored selection

When `kernel.selector.select` (kernel-authored, tier 2, `convention` authority) chooses
resolver R1 and a human prefers R2, the override may be modeled as: (a) a new tier 2
selection record with human authorship, (b) a tier 1 ADR that supersedes the kernel's
tier 2 record, or (c) both — a tier 1 ADR plus a new tier 2 selection citing the ADR as
its `depends_on`. Likely answer is (c); not committed pending propagation analysis.

### OPEN-Q-002 — Surrogate training stack

`kernel.surrogate.train` interface-only in v1. Implementation surface (training framework,
holdout protocol per PROCESS-13, validation thresholds, drift detection) deferred to
whichever block specifies the training stack.

### OPEN-Q-003 — Tier 3 retention

Tier 3 events and `.8os/events/raw/` payloads accumulate without bound in v0.1. Retention
policy (rolling window, cold-storage migration, surrogate-derived compaction) deferred
until storage becomes a real concern.

---

*End of specification v0.1. Authored in Block 1. Depends on 8OS-KERNEL-SPEC v0.1.0. Feeds
Block 2.*
