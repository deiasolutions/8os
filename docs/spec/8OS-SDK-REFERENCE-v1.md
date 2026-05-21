---
id: 8OS-SDK-REFERENCE
version: 1.1
status: reference
kind: reference-index
scope: project
domain: 8os/sdk
authored_by: Q88N + Claude
authored_on: 2026-04-28
provenance: consolidates the SDK contract preserved across v0.1 (defines the original op set), v0.2 (trims two typed wrappers, adds clarifications), v1.0 (preserves the v0.2 op set; adds prediction-economics machinery without adding ops), v1.0.1-partial (mandatory `authored_via`, subdirectory discipline), v1.1 (adds `kernel.ir.cancel` and the `cancelled` status; removes the v0.1 `kernel.surrogate.train` interface stub), Block 2.7 corrections, Block 2.8 amendments, and v1.2 (the v1.2 amendment cycle: §3.17 mode rename `mode: "full"` → `mode: "rebuild"` and tier-3 event emission on rebuild via two-phase commit per axiom 8). Refreshed for v1.2 alignment as part of the Block 5.0 close. Filename retained as `8OS-SDK-REFERENCE-v1.md` (durable entry-point name); version-of-record is in frontmatter.
---

# 8OS SDK Reference

**This is a reference index, not a respecification.** The canonical contract for each operation is in the specs cited per-row. When this index and a canonical spec disagree, the canonical spec wins. If you find a disagreement, it is a bug in this index.

The SDK operations are the kernel's instruction set at v1.2. Userspace programs (factories, agent harnesses, tooling) reach the kernel only through these calls. Wire format: JSON in on stdin, JSON out on stdout, structured errors with stable codes on stderr (per v0.1 §7.1–§7.3, preserved unchanged through every later spec).

## How the contract was assembled

| Spec | Contribution to SDK |
|---|---|
| `8OS-BLOCK-1-SPEC-v0.1.md` | Defines the original op set (§7.6.1–§7.6.18) and the wire format (§7.1–§7.5). Source of truth for op signatures. |
| `8OS-BLOCK-1-SPEC.md` (v0.2) | Trims two typed wrappers: removes `kernel.bridge.add` and `kernel.resolver.add` (use `kernel.ir.new` with the appropriate `_kernel.*` projection type). Clarifies `ir.new`, `ir.list`, `ir.get`, `bridge.cross`, `gatekeeper.check`, `selector.select`, `reindex`. Reserves `_kernel` scope. |
| `BLOCK-2.7-SPEC-CORRECTIONS.md` | Renames base frontmatter `bridge_type` → `authored_via` (Patch 5). Adds operation-output projection types `_kernel.tier3-event`, `.authorization`, `.resolver-selection`, `.capability-update` (Patch 3). Adds `bridge_status` (Patch 4). |
| `BLOCK-2.8-SPEC-AMENDMENTS.md` | Renames `_kernel.calibration-policy-proposal.status` → `proposal_status`. Extends `_kernel.authorization` for supersede-calibration-policy authorizations. |
| `8OS-BLOCK-1-SPEC-v1.0.md` | Preserves the v0.2 op set verbatim. Adds three new projection types (`_kernel.prediction`, `.calibration-policy`, `.calibration-policy-proposal`) and one kernel-internal resolver (`kernel.voi`) — none of which are new SDK operations. Expands the behavior of `kernel.selector.select` and the `kernel.calibrator` resolver. |
| `8OS-BLOCK-1-SPEC-v1.0.1-PARTIAL.md` | Makes `authored_via` mandatory on `kernel.ir.new`. Adds projection-declared subdirectory discipline (`target_subdirectory`). Vendored body seal refreshes across kernel versions on `kernel.init` upgrade-mode. `kernel.reindex --check` validates `authored_via` presence. |
| `8OS-BLOCK-1-SPEC-v1_1.md` | Adds `kernel.ir.cancel` (v1.1 §3.8) and the `cancelled` status enum value (v1.1 §5). Removes v0.1's `kernel.surrogate.train` interface stub from the registry (v1.1 §3.0). Lifts `domain` to optional base frontmatter (v1.1 §4.3). Commits to a four-layer architectural model and names what is specified-but-not-yet-implemented in its "Implementation gap, named honestly" section. Superseded by v1.2; preserved for lineage. |
| `8OS-BLOCK-1-SPEC-v1_2.md` | **Active spec.** v1.2 amendment cycle (Block 5.0): §3.17 `kernel.reindex` mode rename `mode: "full"` → `mode: "rebuild"` (no deprecation alias; legacy value is `SCHEMA_INVALID`) and §3.17 tightening to mandate tier-3 event emission on rebuild via a two-phase commit per axiom 8 (Reflexivity, kernel spec v0.2). Adds axiom-8 cross-references in §2.4 (kernel sovereignty), §3.5 (calibrator capability-update), and §3.17 (reindex). Inherits the v1.1 SDK contract; no operations added or removed. |

v1.1 consolidated rather than amended — the chain v0.1 → v0.2 → 2.7 → 2.8 → v1.0 → v1.0.1-partial folded into v1.1's text. v1.2 is a small additive amendment cycle on top of v1.1: same SDK operations, with `kernel.reindex` tightened per axiom 8. The earlier documents are preserved on disk for lineage but the active contract is in v1.2 alone.

## The SDK operations

| # | Operation | What it does | Canonical signature | Active clarifications |
|---|---|---|---|---|
| 1 | `kernel.init` | Bootstrap a new 8OS repo — write `_kernel` scope, vendored projection bodies, vendored bridges (`kernel.self` and `human-<id>`), kernel-internal resolvers, the kernel index set. | v0.1 §7.6.1 | v1.0.1-partial Amendment 3 (vendored body refresh on upgrade) |
| 2 | `kernel.reindex` | Regenerate the kernel index set from `ir/**` and `.8os/events/**`. Mode `rebuild` rewrites every index and emits a tier-3 rebuild event via two-phase commit (v1.2 §3.17, axiom 8); mode `check` raises `INDEX_DRIFT` if regeneration would change anything. | v0.1 §7.6.2 | v1.0.1-partial Amendment 2 (`--check` enforces `authored_via` presence); v1.1 §4.3 (`--check` rejects empty-string `domain`); v1.2 §3.17 (mode rename `full` → `rebuild`; rebuild emits a tier-3 event recording the regeneration) |
| 3 | `kernel.ir.new` | Create a tier 1, 2, or 3 (I, R) record. The single content-creation op; replaces v0.1's typed wrappers for resolvers/bridges. | v0.1 §7.6.3 | v0.2 §4.1 (projection-declared frontmatter, `_kernel`-scope hard-authority gate); v1.0.1-partial Amendments 1 and 2 (subdirectory discipline; mandatory `authored_via`); v1.1 §4.3 (optional `domain`) |
| 4 | `kernel.ir.resolve` | Attach a resolution to an existing intention. Records the resolver, the cost vector consumed, the bridge crossed (if any), and temporal validity. | v0.1 §7.6.4 | none material |
| 5 | `kernel.ir.expand` | Convert a leaf `<slug>.md` into a folder `<slug>/_node.md` so children can be authored under it. Atomic file move. | v0.1 §7.6.5 | none material |
| 6 | `kernel.ir.collapse` | Inverse of expand. Refuses on non-empty expansion. | v0.1 §7.6.6 | none material |
| 7 | `kernel.ir.promote` | Promote a tier 3 event to a tier 1 or tier 2 (I, R), with the original JSONL line marked as promoted. | v0.1 §7.6.7 | none material |
| 8 | `kernel.ir.supersede` | Supersede an existing (I, R) with a new one carrying a `supersedes:` link. Used for spec amendments and decision reversals. | v0.1 §7.6.8 | none material |
| 9 | `kernel.ir.get` | Read one (I, R). Views: `collapsed`, `expanded`, `full`. | v0.1 §7.6.15 | v0.2 §4.3 (transparent suffix resolution) |
| 10 | `kernel.ir.list` | Query (I, R)s by scope, tier, projection, status, validity, author, authority. AND-composed filters. | v0.1 §7.6.16 | v0.2 §4.2 (`--include-kernel`, `--projection _kernel.*`) |
| 11 | `kernel.ir.deps` | Walk the dependency graph forward, reverse, or both, bounded by `max_depth`. Reads `deps-forward` / `deps-reverse` indexes. | v0.1 §7.6.17 | none material |
| 12 | `kernel.bridge.cross` | Cross an inside/outside bridge. The single primitive that touches the outside. Records cost actually consumed. | v0.1 §7.6.11 | v0.2 §4.4 (reads bridge from `ir/_kernel/bridge/*.md`); 2.7 Patch 4 (`bridge_status: quarantined` rejects with `BRIDGE_UNREACHABLE`) |
| 13 | `kernel.authorize` | Author an `_kernel.authorization` (I, R) — a standing or single-use authorization permitting a downstream bridge crossing or calibration-policy supersession. | v0.1 §7.6.12 | 2.8 Amendment 2 (extends to supersede-calibration-policy authorizations) |
| 14 | `kernel.gatekeeper.check` | Read-only check: is this resolver permitted to cross this bridge for this (I, R) given the supplied authorization? | v0.1 §7.6.13 | v0.2 §4.5 (reads `_kernel.bridge` for `requires_authorization`) |
| 15 | `kernel.selector.select` | Choose a resolver for a given intention. Reads cost and capability vectors from `_kernel.resolver` (I, R)s; produces an `_kernel.resolver-selection` event. | v0.1 §7.6.14 | v0.2 §4.6 (reads `_kernel.resolver`); v1.0 §5.1 (consults `kernel.voi` when calibration policy applies; emits optional `voi_consultation` field on selector events) |
| 16 | `kernel.event.get` | Read one tier 3 event by ULID, optionally with raw payload. | v0.1 §7.6.18 | none material |
| 17 | `kernel.ir.cancel` | Mark an (I, R) `status: cancelled`. Terminal: cancellation cascades to direct dependents (marked `stale`), drops pending outside-call ops against the cancelled (I, R), and is reversible only via supersede-with-replacement (a new (I, R) with `supersedes: <cancelled-id>`). | v1.1 §3.8 | Block 4.2 implements §5.2 transition rules; §3.8/§18.1 error descriptions pending reconciliation amendment. Reversibility implemented in Block 4.6 (Path A) — `kernel.ir.new` accepts `supersedes:` pointing at a cancelled target; see `tests/kernel/test_block_4_6_supersedes.py`. Generic `NOT_FOUND` used for id-lookup failures vs spec's `IR_NOT_FOUND` (F2 — preexisting taxonomy drift). |

## Removed in v1.1

`kernel.surrogate.train` — declared in v0.1 §7.7 as an interface stub, deferred per OPEN-Q-002, never implemented as an SDK op. **Removed from the registry in v1.1 §3.0.** v1.1's surrogate machinery (axiom 7) does not require an SDK operation: surrogate composition is a property of the resolver registry (`_kernel.resolver` records carrying `surrogate_of:` links), not a kernel-invoked operation. If a future block needs an SDK-level training op, it lands in its own block on its own merits.

## What is *not* an SDK operation

These appear in the spec body but are not SDK calls; they are kernel-internal resolvers, projection types, scopes, or wire conventions:

- `kernel.self`, `human-<primary-operator-id>` — vendored bridges, not operations.
- `kernel.selector`, `kernel.gatekeeper`, `kernel.calibrator`, `kernel.voi` — kernel-internal resolvers, registered as `_kernel.resolver` (I, R)s. The selector and gatekeeper are *invoked through* `kernel.selector.select` and `kernel.gatekeeper.check`; the calibrator and voi run as background concerns, not SDK calls.
- `_kernel.scope`, `_kernel.projection`, `_kernel.resolver`, `_kernel.bridge`, `_kernel.surrogate-lineage` — projection types declared by `kernel.ir.new`, not operations.
- `_kernel.tier3-event`, `.authorization`, `.resolver-selection`, `.capability-update` — operation-output projection types.
- `_kernel.prediction`, `_kernel.calibration-policy`, `_kernel.calibration-policy-proposal` — v1.0's prediction-economics projection types.
- `kernel.bridge.add`, `kernel.resolver.add` — **removed in v0.2.** Use `kernel.ir.new` with the appropriate `_kernel.*` projection type.
- `kernel.surrogate.train` — **removed in v1.1 §3.0** (was never implemented; see above).
- `kernel.outside.http` and other outside-call primitives — v1.1 §11 specifies these as a parallel category of primitives, structurally separate from the inside-op SDK. Implemented in Block 4.8 as `kernel.outside.http` per v1.1 §11; see `src/eightos/sdk/outside_http_op.py`.

## Errors (stable codes, per v0.1 §7.3)

`KERNEL_VERSION_MISMATCH`, `ALREADY_EXISTS`, `NOT_FOUND`, `SCHEMA_INVALID`, `INVALID_STATE`, `DEPENDENCY_BROKEN`, `AUTHORITY_INSUFFICIENT`, `AUTHORIZATION_REQUIRED`, `BRIDGE_UNREACHABLE`, `EVENT_WRITE_FAILED_AFTER_CROSSING`, `INDEX_DRIFT`, `ATOMICITY_FAILURE`, `CONFLICTING_PROJECTION_TARGETS` (added in v1.0.1-partial Amendment 1).

v1.1 §3.8 introduces cancel-specific codes used by `kernel.ir.cancel`: `IR_ALREADY_CANCELLED`, `IR_NOT_CANCELLABLE`, `CANCELLATION_AUTHORITY_INSUFFICIENT`, `LEASE_HELD`, `POLICY_DENIED`. Block 4.2 surfaced taxonomy drift between v1.1 §18.1's `IR_NOT_FOUND` and the codebase's pre-existing generic `NOT_FOUND` (Block 4.2 friction F2); the implementation uses generic `NOT_FOUND` pending taxonomy alignment.

## Reading order for new implementers

1. `8OS-KERNEL-SPEC-v0.2.md` — nine axioms (axiom 0 + 1–8), active. v0.1 (eight axioms) preserved for lineage.
2. `8OS-BLOCK-1-SPEC-v1_2.md` — active consolidated spec (the SDK operations, four-layer model, axiom-8 tightening of `kernel.reindex`, the implementation-gap section that names what's specified-but-not-yet-implemented).
3. (optional, for lineage) `8OS-BLOCK-1-SPEC-v1_1.md` — the v1.1 consolidation that v1.2 is layered on top of; useful when reading axiom-8-related diffs.
4. (optional, for lineage) `8OS-BLOCK-1-SPEC-v0.1.md` §7 — original wire format and op signatures; superseded but useful as a bottom-up reading.
5. (optional, for lineage) `8OS-BLOCK-1-SPEC.md` (v0.2), `BLOCK-2.7-SPEC-CORRECTIONS.md`, `BLOCK-2.8-SPEC-AMENDMENTS.md`, `8OS-BLOCK-1-SPEC-v1.0.md`, `8OS-BLOCK-1-SPEC-v1.0.1-PARTIAL.md` — the predecessor chain v1.1 consolidated.

This file (the SDK reference) is for navigating that chain quickly. It is not a substitute for reading the canonical spec.

---

*End of 8OS SDK Reference v1.1. Authored 2026-04-28. Updates when the canonical contract changes.*
