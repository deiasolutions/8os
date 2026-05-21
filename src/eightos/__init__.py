"""8OS — kernel of an intention-driven OS for software product development.

Block 2.9 dogfood cycle 1: this docstring extension is the subject change —
the predictor's view of "did anything plausibly break the test suite?"
"""

# The kernel binary version. Tracks the Block 1 representation spec the binary
# implements. Bumped from "0.1.0" → "1.0.0" in Block 2.9 to reflect Block 1 v1.0
# compliance (prediction-economics machinery vendored at init; new records get
# `kernel.binary@1.0.0` provenance, distinguishable from v0.1/v0.2 records).
# Bumped 1.0.0 → 1.0.1-partial in this amendment round to fold in subdirectory
# discipline, mandatory authored_via, and per-version body seal semantics
# (8OS-BLOCK-1-SPEC-v1.0.1-PARTIAL §0; resolves OPEN-Q-021/022/023). The
# `-partial` suffix marks that v1.0.1 also defers OPEN-Q-019/024/025; a
# future v1.0.1-full or v1.0.2 will fold those when their answers ship.
# Bumped 1.0.1-partial → 1.1.0-dev.1 in Block 4.1 — the first v1.1 schema
# addition: `domain` lifted to optional base frontmatter (8OS-BLOCK-1-SPEC v1.1
# §4.3; closes OPEN-Q-019). The `-dev.1` suffix marks this as the first
# pre-release on the v1.1 family; later v1.1 schema additions and the 17th op
# will land as -dev.2, -dev.3, etc., before any v1.1.0 release.
# Bumped 1.1.0-dev.1 → 1.1.0-dev.2 in Block 4.2 — the 17th op `kernel.ir.cancel`
# plus the `cancelled` status enum value (v1.1 §3.8, §5). Also removes the
# v0.1 `kernel.surrogate.train` interface stub per v1.1 §3.0 (registry composition
# changes 17 → 17 with surrogate.train out and cancel in).
# Bumped 1.1.0-dev.2 → 1.1.0-dev.3 in Block 4.3 — `data_classification` lifted
# to optional base frontmatter (v1.1 §4.2). Same mechanical pattern as Block
# 4.1's `domain` lift; `_kernel.scope` body gains `data_classification_default`.
# Bumped 1.1.0-dev.3 → 1.1.0-dev.4 in Block 4.4 — `visible_when` lifted to
# optional base frontmatter (v1.1 §4.4) plus the predicate evaluation engine
# at every read op (`kernel.ir.get` / `.list` / `.deps`). Closes the tier-A
# v1.1 base-field set; v1.1 housekeeping amendment is the natural next step.
# Bumped 1.1.0-dev.4 → 1.1.0-dev.5 in Block 4.6 — Path A implementation:
# `kernel.ir.new` accepts `supersedes:` for supersede-with-replacement of
# cancelled records (v1.1 §3.2 / BLOCK-4.5-SPEC-AMENDMENTS Amendment 4),
# plus `kernel.ir.list` `include_cancelled` filter (Appendix A item 7).
# Closes the v1.1 housekeeping queue; tier-A foundation plus Path A is now
# implementation-complete. Block 4.2's Test 12 unskips at this version.
# Bumped 1.1.0-dev.5 → 1.1.0-dev.6 in Block 4.7 — policy machinery bundle:
# `_kernel.role`, `_kernel.policy`, `_kernel.policy-evaluation` projection
# types (v1.1 §7.2-7.4); unified pre-commit pipeline (`op_pipeline.py`)
# implementing v1.1 §8.6 phases 2-3; CallerContext populated from bridge
# identity + role records (closes Block 4.4's roles + runtime placeholders);
# policy evaluation phase wired into `kernel.ir.cancel` and `kernel.ir.new`;
# `policy-evaluations` cache index added (v1.1 §3.17); cache invalidation
# on policy supersession (eager walk per Q-CACHE). Closes Block 4.2's
# policy-evaluation placeholder; reduces lease-check placeholder to "slot
# exists, data type pending Block 4.8."
# Bumped 1.1.0-dev.6 → 1.1.0-dev.7 in Block 4.8 — kernel.outside.http +
# `_kernel.lease`. New op `kernel.outside.http` (v1.1 §11) implementing
# the canonical outside-call primitive: pre-commit pipeline integration
# (lease check phase 2 + policy phase 3), urllib transport, payload and
# response hashing, optional sidecar storage, three-vector cost
# decomposition, expires_at gate. New projection `_kernel.lease` (v1.1
# §7.1) with vendored body declaring required frontmatter (lease_id,
# lease_for, held_by, lease_purpose, acquired_at). New phase-2 lease check
# in op_pipeline.py replaces Block 4.7's structural no-op. Two new
# indexes (v1.1 §3.17): `lease-holders` (lease target → active lease ids)
# and `payload-hash-to-events` (request payload SHA-256 → tier-3 event
# ids). Eight new error codes: OUTSIDE_UNREACHABLE, OUTSIDE_CALL_DENIED,
# EXPIRES_AT_PASSED, BUDGET_EXHAUSTED, RATE_LIMIT_EXHAUSTED,
# PAYLOAD_TOO_LARGE, LEASE_HELD, LEASE_EXPIRED. Closes Block 4.2's
# lease-check placeholder. kernel.outside.http is NOT counted among the
# SDK ops per §11.9; it's an outside-call primitive in the axiom-0
# outside category, dispatched through the same runner for uniformity.
# Bumped 1.1.0-dev.7 → 1.1.0-dev.8 in Block 5.0 (the v1.2 amendment cycle) —
# axiom 8 (Reflexivity) ratified into kernel spec v0.2; consequent Block-1
# spec corrections land in v1.2: §3.17 mode rename `mode: "full"` →
# `mode: "rebuild"` (no deprecation alias) and §3.17 tightening to mandate
# tier-3 event emission on rebuild via two-phase commit (regen → emit →
# regen). Code-side changes: `src/eightos/sdk/reindex_op.py` rebuild path
# now emits a tier-3 event (resolver_id: "kernel", bridge_id: "kernel.self",
# authority_level: hard) per axiom 8; reindex schemas updated to accept
# the new mode value and a non-null event_id on rebuild. Audit code-side
# verification (BLOCK-5.0-PHASE-A-PRIME-REPORT) confirmed the two
# principled bypasses (kernel.init bootstrap; op_pipeline policy-eval
# cache) preserve axiom-8 discipline by shape, atomicity, provenance,
# and event emission; both are now explicitly named carve-outs in kernel
# spec v0.2's "Axiom 8 — Reflexivity" section.
# Bumped 1.1.0-dev.8 → 1.2.0 in Block 5.0 closure (2026-05-03) — Phase B
# ratification of the v1.2 amendment cycle. The dev.8 binary IS the v1.2
# binary; no behavioral code change. Kernel spec v0.2 (axiom 8 ratified)
# and Block-1 spec v1.2 (§3.17 mode rename + tier-3 emission via two-phase
# commit) ratified the same day per docs/block-5.0-report.md.
__version__ = "1.2.0"

# Resolver id used when the kernel binary itself acts as the resolver — e.g.,
# the bootstrap (I, R) and other kernel-self-observed records authored through
# the `kernel.self` bridge. Version-suffixed so future audits can attribute
# records to the kernel that produced them without a side table. (Block 2.7
# OPEN-Q-008-RESOLVED, superseding v0.1's bare "kernel" answer in light of
# the cogito bridge mechanics introduced in v0.2 §2.4.)
KERNEL_BINARY_RESOLVER_ID = f"kernel.binary@{__version__}"
