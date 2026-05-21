# Claude Code instructions for 8OS

## Public vs. private file layout

This repo enforces a strict public/private split:

- **Public** (committed, pushed to GitHub): `src/`, `tests/`, `scripts/`, `docs/`, `ir/`, `.8os/`, top-level config. Specs, code, kernel data, demos, the canonical overview, the article, open-questions.
- **Private** (gitignored, never pushed): everything under `private/`. Working notes, plans, audits, build-state, drafting lineage, block-closure reports, session inbox, day-to-day journals, substrate-contract internals.

When writing internal artifacts during a Claude Code session — build-state, plans, audits, working notes, drafting lineage, session resume docs, anything in "how the sauce is made" voice — write to `private/<appropriate-subdir>/`. Never under `docs/`.

When in doubt: ask. Default to `private/`.

A `.githooks/pre-commit` hook hard-blocks staging anything under `private/` or working-doc patterns under `docs/`. Wire it into a fresh clone with: `git config core.hooksPath .githooks`.

The "Read first" and "On session start" sections below reference files under `private/`. These exist on the author's working disk but are not present in fresh public clones — that's by design.

## On session start (resume posture)

Before doing anything else in this repo — even before reading the specs in §"Read first" below — find and read the most recent build-state doc. That's the canonical "where we are" reference, written explicitly to be the resume point across sessions.

Build-state docs live at `private/build-state/YYYY-MM-DD[-suffix].md` (gitignored — author's disk only). The most recent one supersedes its predecessors (each carries an explicit `Supersedes:` header naming the prior build-state). To find the latest:

```bash
ls -1t private/build-state/*.md | head -1
```

Read that file in full. It captures: what closed in the most recent session, the current state snapshot (binary version, active specs, test/lint state, tip-of-main commit), the queued next-step options with size estimates, and an explicit "Resume point for next session" subsection.

After reading the latest build-state, summarize what you found before doing any new work — give the user a brief "where we are / what's queued" summary so they can confirm you're grounded before committing to a direction. Don't read older build-state docs unless lineage context is specifically needed.

The build-state docs are the source of truth for cross-session continuity. The §"Read first" specs below are the source of truth for what the kernel and substrate *are*; the build-state is the source of truth for what we just *did* and what's next.

## Read first
Before doing anything in this repo, read these spec files in full:
- `docs/spec/8OS-KERNEL-SPEC-v0.2.md` — **active kernel spec.** Ratified 2026-05-03 (Block 5.0 closure). Nine axioms (axiom 0 + 1–8). v0.2 ratifies axiom 8 (Reflexivity) per the v1.2 amendment cycle (Block 5.0); names the bootstrap and policy-evaluation cache as the two structural carve-outs.
- `docs/spec/8OS-KERNEL-SPEC-v0.1.md` — superseded by v0.2; preserved for lineage.
- `docs/spec/8OS-BLOCK-1-SPEC-v1_2.md` — **active representation spec.** Ratified 2026-05-03 (Block 5.0 closure). v1.2 amendment cycle: §3.17 mode rename (`mode: "full"` → `mode: "rebuild"`, no deprecation alias), §3.17 tightening to mandate tier-3 event emission on rebuild via two-phase commit (axiom 8), and axiom-8 cross-references in §4.6 and §6.4. Binary is at v1.2.0.
- `docs/spec/8OS-BLOCK-1-SPEC-v1_1.md` — superseded by v1.2; preserved for lineage. v1.1 architectural commitment folded v1.0.1-partial's amendments plus OPEN-Q-019.
- `docs/spec/8OS-BLOCK-1-SPEC-v1.0.1-PARTIAL.md` — predecessor to v1.1; preserved.
- `docs/spec/8OS-BLOCK-1-SPEC-v1.0.md` — the v1.0.0 representation base; preserved.
- `docs/spec/8OS-BLOCK-1-SPEC.md` and `docs/spec/8OS-BLOCK-1-SPEC-v0.1.md` — superseded representations; reference only when reading historical context.
- `docs/spec/PRISM-IR-SPEC-v1.1.md` — the projection format the kernel must continue to host correctly.
- `docs/spec/BLOCK-2.7-SPEC-CORRECTIONS.md` — the spec-clarification batch that ratified v0.2's amendments.
- `docs/spec/BLOCK-2.8-SPEC-AMENDMENTS.md` — v1.0's amendment batch (proposal_status rename, _kernel.authorization extension).
- `docs/spec/drafts/AXIOM-8-AMENDMENT-PROPOSAL-v0_1.md` — the axiom-8 proposal (ratified into kernel spec v0.2).
- `docs/spec/drafts/AXIOM-8-AUDIT-v0_1.md` — spec-side audit; headline: axiom 8 lands additively in v1.2.
- `private/reports/block-5.0-phase-a-prime-report.md` — code-side audit verification; documents the two principled bypasses (bootstrap, policy-eval cache) and the two-phase commit pattern for §3.17 tightening.
- `private/reports/block-5.0-report.md` — **Block 5.0 closure record.** Ratification of the v1.2 amendment cycle on 2026-05-03; cites the dev.7→dev.8 implementation commit, the docs cleanup commit, and the closure resolutions of OPEN-Q-A1 through A4.
- `private/internal/8OS-SUBSTRATE-CONTRACT-v0_2.md` — **active substrate contract.** Eight commitments and eight gaps; v0.2 admitted cost-symmetry as the eighth commitment in Block 5.1. v0.1 preserved for lineage.

These define the **nine-axiom kernel** (eight content axioms 1–8 plus axiom 0 as cosmology) and the **SDK operation contract**. v0.2 trimmed `kernel.resolver.add` and `kernel.bridge.add` (replacing them with `kernel.ir.new` against the appropriate `_kernel.*` projection types); v1.1 added `kernel.ir.cancel` and removed the v0.1 `kernel.surrogate.train` interface stub. v1.2 ratified axiom 8 and tightened `kernel.reindex` rebuild mode. Binary is at **v1.2.0** (Block 5.0 ratified 2026-05-03). They are the source of truth. Do not invent behavior the specs don't authorize.

## Stack
- Python 3.13
- `uv` for dependency management
- `pytest` for tests
- `ruff` for linting
- `hatchling` build backend

## Layout
- `src/eightos/` — kernel package
- `src/eightos/cli.py` — CLI entry point (`8os` command)
- `src/eightos/sdk/` — SDK operation implementations (one module per operation group)
- `src/eightos/schemas/` — JSON Schema definitions for all SDK operations (input + output, versioned)
- `tests/` — pytest tests, mirroring src layout
- `docs/spec/` — the immutable specs; never modify
- `docs/open-questions.md` — log gaps you find in the spec; don't ask the user about gaps the spec should answer

## Wire format
Subprocess: JSON in on stdin, JSON out on stdout, structured errors on stderr with stable error codes per the spec. Validate every input and output against the relevant schema in `src/eightos/schemas/`.

## Discipline
- If a question's answer is in the spec, re-read the spec.
- If a real gap exists in the spec, log it in `docs/open-questions.md` with your best-guess implementation marked as a guess; do not block on the user.
- Indexes are committed per regeneration discipline γ. CI must reject PRs where committed indexes don't match what regeneration would produce.
- Every (I, R) is tier 1, 2, or 3. No exceptions, no second class of citizen.

## v0.2 essentials (do not violate)

- **Kernel-configuration is content.** Resolvers, bridges, projection definitions, scope declarations, surrogate-lineage records all live as (I, R) records under `ir/_kernel/<category>/<id>.md` with `projection_types: [_kernel.<type>]`. There are no typed configuration ops; everything goes through `kernel.ir.new`.
- **Configuration is content, not typed ops.** v0.1's `kernel.resolver.add` and `kernel.bridge.add` are removed in v0.2. Do not add wrappers; do not re-introduce them.
- **Nine kernel projection types.** Five configuration (`_kernel.scope`, `.projection`, `.resolver`, `.bridge`, `.surrogate-lineage`) plus four operation-output (`_kernel.tier3-event`, `.authorization`, `.resolver-selection`, `.capability-update`). All `_kernel.*` prefixed.
- **Two vendored bridges at init.** `kernel.self` (the kernel binary's own existence claim — the *cogito*) and `human-<primary-operator-id>` (the human's sovereignty per #NOKINGS). `kernel.self` authors `_kernel`-scope foundational records; the human bridge authors the user scope.
- **Authority foundations.** Both bridges are real bridges with real provenance — neither is a magic exception. The kernel and the human are co-equal foundations of the project's authority graph (spec §2.4).
- **Foundational record read-only-after-bootstrap.** The `_kernel` scope declaration and the nine vendored kernel projection-type definitions are sealed after init. Amendable only via `kernel.ir.supersede` authored by humans with hard authority through their identity bridge (spec §4.1).
- **Projection-declared frontmatter extensions** are honored by `kernel.ir.new` per §2.1. **Filename suffix from projection** is honored per §2.2. **`_kernel` scope writes** require `authority_level: hard` per §2.3.

## v1.0.1-partial essentials (do not violate)

- **Projection-declared subdirectory discipline.** Projection definitions may declare `target_subdirectory:` in their body schema. `kernel.ir.new` writes records to `ir/<scope>/<target_subdirectory>/<id><filename_suffix>` when present, else flat. Multiple projection_types declaring conflicting subdirectories raise `CONFLICTING_PROJECTION_TARGETS`. Three vendored bodies declare it: `_kernel.prediction → _predictions`, `_kernel.calibration-policy → _calibration-policies`, `_kernel.calibration-policy-proposal → _calibration-proposals`.
- **Mandatory `authored_via`.** Every (I, R) carries a non-empty `authored_via`. `kernel.ir.new` requires it as input; the SDK boundary (`_runner._apply_sdk_defaults`) defaults missing values to `"outside"`. Internal kernel ops (init, migration, selector tier 2 records, kernel.self self-events) supply `"kernel.self"` explicitly. `kernel.reindex --check` enforces presence — records lacking it are rejected as `SCHEMA_INVALID`.
- **Per-version body seal.** Vendored projection bodies (`.8os/projections/_kernel/<type>.yml`) are sealed within a single kernel version; sealed against user edits, refreshed across kernel versions on `kernel.init` upgrade-mode. Two binaries with the same version string MUST ship identical vendored bodies. Body amendments require a kernel version bump.

## v1.2 essentials (active architectural commitment; binary at v1.2.0; Block 5.0 closed 2026-05-03)

- **Active specs are kernel v0.2 + Block-1 v1.2, both ratified 2026-05-03.** Block 5.0 (the v1.2 amendment cycle) ratified axiom 8 (Reflexivity) into kernel spec v0.2 and landed the consequent corrections in Block-1 spec v1.2: §3.17 mode rename and tightening, axiom-8 cross-refs in §4.6 / §6.4. Binary is at v1.2.0. See `private/reports/block-5.0-report.md` for the closure record.
- **Axiom 8 — Reflexivity.** Every kernel claim about its own state is an (I, R) on the kernel's graph, subject to all other axioms. Two principled carve-outs are named in kernel spec v0.2: **bootstrap** (`kernel.init` cannot validate against schemas it is authoring) and **policy-evaluation cache** (`op_pipeline._author_policy_evaluation` cannot run the policy phase without unbounded recursion). Both preserve (I, R) shape, hard authority, `authored_via: kernel.self`, atomic commit, and tier-3 event emission. New kernel-internal ops with similar bypass needs MUST be documented as named carve-outs.
- **`kernel.reindex` mode is `"rebuild"`** (v1.2 §3.17, Block 5.0). The rename is hard — v1.2+ binaries reject `mode: "full"` with `SCHEMA_INVALID`. The CLI flag remains `--rebuild`. `mode: "check"` is unchanged.
- **`kernel.reindex` rebuild emits a tier-3 event** via two-phase commit (v1.2 §3.17): phase 1 regenerates indexes from records; phase 2 appends the rebuild event (resolver_id `"kernel"`, bridge_id `"kernel.self"`, authority `hard`, structured payload includes `input_set_hash` and `indexes_written`); phase 2b re-runs `write_all` so events-derived indexes reflect the new event. A subsequent `mode: "check"` finds no drift.

## v1.1 essentials (preserved at v1.2)

- **`domain` is optional base frontmatter** (v1.1 §4.3, Block 4.1). Every (I, R) may declare `domain: string|null`; scope-default inheritance via `domain_default` on `_kernel.scope` records. Empty-string `domain` is `SCHEMA_INVALID`. `find_active_policy` resolves the effective domain (record-level → scope default → null) before matching `applies_to_domain`.
- **SDK operation set** (v1.1 §3, preserved at v1.2). v1.0.1-partial's operations preserved verbatim plus `kernel.ir.cancel` (v1.1 §3.8, Block 4.2) and the `cancelled` status enum value (v1.1 §5). v0.1's `kernel.surrogate.train` interface stub is removed in v1.1 §3.0; the registry has `surrogate.train` out and `cancel` in.
- **Other v1.1 architecture not yet implemented:** skills (`_kernel.skill`), three-cost decomposition (`resolver_cost`/`kernel_cost`/`factory_cost`), bridge queues / payload hashing inside `kernel.outside.http`, delayed-activation state, `_simulation.alterverse-store`, DuckDB+vss storage, bridges-as-PRISM-IR programs. Each lands in its own block. Block 4.8 closed `kernel.outside.http` + `_kernel.lease`; Block 5.0 closed axiom 8.
