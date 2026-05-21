"""Factory walker — find dispatchable leaves in a scope's (I, R) graph.

Block 3 Piece 2 (rewritten from Piece 1). The walker reads (I, R)
records under `ir/<scope>/**/*.md` and returns the subset that are
dispatchable leaves: open-status work intentions whose dependencies
are all resolved, that are not kernel-configuration records.

A dispatchable leaf is identified by:
- `status == "open"`
- `expanded_into` is null (an expanded parent is not a leaf — it has
  children that compose its resolution; see the graph-producing
  resolver branch in tick.py for why this matters under Block 3
  Piece 5's pattern β. Without this filter, after a decomposer
  dispatch authors children under the parent and `kernel.ir.expand`
  flips the parent's `expanded_into` from null to its own id, the
  walker would otherwise re-pick the parent as a leaf and re-dispatch
  the decomposer indefinitely.)
- every record in `depends_on` exists in this scope and has
  `status == "resolved"`
- `projection_types` is disjoint from any `_kernel.*` projection
  type (configuration AND operation-output). The factory dispatches
  resolvers against work intentions only; system-internal records
  (configurations, predictions, capability-updates, selections,
  events, authorizations, calibration policies / proposals) are
  not work and must not get a resolver run against them.

  This is broader than the user's Piece 2 go-ahead note 3.3, which
  classified `_kernel.prediction` and `_kernel.calibration-policy`
  as walkable. During implementation we found that walking them
  caused the calibration-policy record itself to be treated as a
  dispatchable leaf (active policy = self → predictor dispatched
  against it), and per-batch holdout precomputation included a
  spurious entry for the policy. The broader exclusion is the
  conservative-correct fix; it reflects "this is system metadata,
  not user work." If a future block needs to walk operation-output
  records (e.g., a calibrator re-dispatching against a stale
  prediction), refine the filter then.

Note: the walker does NOT filter by any "this leaf has a resolver
pointer" check. Intentions don't carry a pre-set resolver field
under v1.0 — `resolver` (base frontmatter) is set by
`kernel.ir.resolve` at resolution time, and `resolver_id` is a
projection extension that only appears on resolver records (see
OPEN-Q-027). The factory's tick calls `kernel.selector.select` per
leaf to dynamically pick which resolver to dispatch.

Piece 1 had an extra `resolver_id`-presence filter in this function
that was a fixture-masked bug; it filtered out every real intention
because real intentions don't carry that field, but the Piece 1
synthetic intentions did carry the same wrong field, so the tests
passed against the bug. Corrected here as a load-bearing prerequisite
for Piece 2's selector-driven dispatch.

Operation-output projection types — `_kernel.tier3-event`,
`_kernel.authorization`, `_kernel.resolver-selection`,
`_kernel.capability-update`, `_kernel.prediction`,
`_kernel.calibration-policy`, `_kernel.calibration-policy-proposal`
— are walkable by the projection-types filter; whether they actually
get dispatched is up to the selector at tick time.

`depends_on` resolution is local to the scope being walked. A leaf
whose depends_on chain references records in other scopes will fail
closed (treated as not-yet-resolved). Cross-scope dependency walks
are out of scope for Block 3 Piece 2.
"""

from __future__ import annotations

from pathlib import Path

from .._frontmatter import IRRecord, parse_file
from .._paths import ir_dir

KERNEL_CONFIGURATION_PROJECTION_TYPES: frozenset[str] = frozenset(
    {
        # v0.2 configuration projections (five).
        "_kernel.scope",
        "_kernel.projection",
        "_kernel.resolver",
        "_kernel.bridge",
        "_kernel.surrogate-lineage",
        # v0.2 operation-output projections (four). Records of these
        # types are emitted by ops; the factory should not dispatch a
        # resolver against them.
        "_kernel.tier3-event",
        "_kernel.authorization",
        "_kernel.resolver-selection",
        "_kernel.capability-update",
        # v1.0 projections — calibration-policy is configuration in
        # spirit (declares the active policy for a scope/domain);
        # prediction and calibration-policy-proposal are operation
        # outputs. None should be dispatched as work intentions.
        "_kernel.calibration-policy",
        "_kernel.calibration-policy-proposal",
        "_kernel.prediction",
    }
)


def find_dispatchable_leaves(repo: Path, scope: str) -> list[IRRecord]:
    """Return (I, R)s in `ir/<scope>/` that are ready to dispatch this tick.

    A record is a dispatchable leaf iff:
    - `status == "open"`
    - `projection_types` is disjoint from
      `KERNEL_CONFIGURATION_PROJECTION_TYPES`
    - every record in `depends_on` exists in this scope and has
      `status == "resolved"`
    """
    scope_dir = ir_dir(repo) / scope
    if not scope_dir.exists():
        return []

    records_by_id: dict[str, IRRecord] = {}
    for path in sorted(scope_dir.rglob("*.md")):
        try:
            rec = parse_file(path)
        except Exception:
            continue  # Skip unparseable files (e.g., non-(I, R) markdown).
        rid = rec.frontmatter.get("id")
        if rid:
            records_by_id[rid] = rec

    leaves: list[IRRecord] = []
    for rec in records_by_id.values():
        if _is_dispatchable_leaf(rec, records_by_id):
            leaves.append(rec)
    return leaves


def _is_dispatchable_leaf(rec: IRRecord, all_records: dict[str, IRRecord]) -> bool:
    fm = rec.frontmatter
    if fm.get("status") != "open":
        return False
    if fm.get("expanded_into") is not None:
        return False
    ptypes = set(fm.get("projection_types") or [])
    if ptypes & KERNEL_CONFIGURATION_PROJECTION_TYPES:
        return False
    for dep_id in fm.get("depends_on") or []:
        dep = all_records.get(dep_id)
        if dep is None or dep.frontmatter.get("status") != "resolved":
            return False
    return True
