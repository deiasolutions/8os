---
authored_by: human-q88n
authored_on: '2026-04-29T20:00:00.000Z'
authored_via: human-q88n
authority_defaults:
  convention: []
  hard: []
  uncalibrated: []
authority_level: hard
collapsed_summary: 'Scope declaration: decomposition-strategy — Demo #3 (self-composition witness). Hosts the meta-program, the three strategy programs the meta emits, and the comparison intention.'
depends_on: []
display_name: Decomposition strategy demo
expanded_into: null
id: decomposition-strategy
kind: ir-node
parent: null
parent_scope: null
projection_types:
- _kernel.scope
resolution_event: null
resolved_at: '2026-04-29T20:00:00.000Z'
resolver: kernel.binary@1.1.0-dev.6
revalidate_trigger: null
scope: _kernel
status: resolved
superseded_by: null
supersedes: null
surrogate_of: null
tier: 1
valid_through: null
visibility_defaults:
- decomposition-strategy
visible_to:
- _kernel
---

# Intention

Scope `decomposition-strategy` — Demo #3 of the publish-track demo trio
(see `lsystem-demo` for Demo #1 and SCAN at `8os/ir/dogfood-scan/` for
Demo #2). Witnesses the substrate's self-composition property: a
PRISM-IR program (the meta-program) whose resolution is more PRISM-IR
programs (three decomposition strategies) that the same substrate then
runs.

This scope holds three classes of records authored across four phases:

1. The meta-program (`decomposition-meta`) — authored once at demo
   bootstrap; resolves with three child program emissions in
   `resolution_value` (Phase 1).
2. Three strategy programs (`strategy.token-count`,
   `strategy.structural`, `strategy.density`) — authored by the
   orchestrator from the meta-program's resolutions, via `kernel.ir.new`
   (Phase 2). Each is a tier-1 PRISM-IR program of the same shape as
   any other PRISM-IR program in the kernel.
3. The comparison intention — authored by the orchestrator after
   Phase 3; `depends_on` the three strategies' chunk records;
   resolution is the comparison artifact.

Configuration records (the deterministic decomposer for these
programs, the meta resolvers, the three chunker resolvers, this scope
declaration) live under `_kernel`. Operation outputs (resolver
selections, capability updates) live under `_ops`. This scope holds
tier-1 work only.

Authored by `human-q88n` per #NOKINGS — scope declaration is a
foundational decision and requires hard authority per OPEN-Q-015's
resolution.

## Reference

- `decomposition-strategy-demo/docs/contract.md` — Piece 1, the
  contract this scope hosts.
- `ir/decomposition-strategy/decomposition-meta.prism.md` — the
  meta-program (workload root for Phase 1).
