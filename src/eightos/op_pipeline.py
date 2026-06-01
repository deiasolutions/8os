"""Policy machinery and unified op pre-commit pipeline (Block 4.7, v1.1 §8).

This module implements three things:

1. **Governance readers** — `read_roles_for_caller`, `read_policies_for_op`,
   `read_cached_evaluation`. These walk the kernel's record store via the
   existing index machinery to find applicable roles, policies, and cached
   evaluations.

2. **CallerContext population** — `build_caller_context` populates the
   `predicates.CallerContext` dataclass from the caller's `authored_via`
   bridge identity, role membership (via Piece 1's reader), and authority
   level (via the existing `_bridge_authority_level` helper). This closes
   Block 4.4's runtime CallerContext placeholder.

3. **Pre-commit pipeline** — `evaluate_op_pre_commit` runs v1.1 §8.6's
   phases 2-3 (lease check, policy evaluation) for ops that opt into it.
   Phases 1 (authority) and 4 (classification) remain in op handlers per
   Block 4.7's bounded-scope decision; the existing per-op patterns are
   pass-through-compatible with the pipeline's behavior.

Decisions locked in Block 4.7's pre-implementation question batch:

- Q-NEW-4 / op_signature: hash includes op_name + canonical op input +
  canonical caller context. Per-caller-per-op cache. Required for
  correctness when policies reference caller-identity leaves. Logged as
  finding F-CACHE-KEY for spec amendment.
- Q-NEW-5 / predicate semantics: inline policy-condition predicates use
  caller-context-only semantics (reuse Block 4.4's `predicates.py`
  engine verbatim). Policies needing op-input context use resolver-
  reference conditions per §8.7. Logged as finding F-PRED for spec
  amendment.
- Q-CACHE / invalidation: walk-on-supersession (eager). `kernel.ir.supersede`
  hooks into `invalidate_cache_for_policy` when superseding a `_kernel.policy`.
- Q-RESOLVER / dispatch: synchronous. Resolver-referenced policy
  conditions block until the resolver returns a decision.

Closed since Block 4.7:

- `_kernel.lease` projection type and the active phase-2 lease check
  landed in Block 4.8. The check now walks the `lease-holders` index,
  validates each candidate's `valid_through`, and rejects with
  `LEASE_HELD` when a non-holder attempts a write or exclusive op
  against a target under an active lease.
- `kernel.outside.http` landed in Block 4.8.

Out of scope for Block 4.7 (still pending):

- `_kernel.skill` (Block 4.9).
- Migrating existing op-specific authority/classification checks into
  the pipeline (a future cleanup block).
- The `payload_signature` predicate leaf (Q-PAYLOAD deferred).
- Classification-ordering machinery (Q-CLASS deferred; Block 4.4's
  `data_classification_at_most` continues to do string equality).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import predicates
from ._frontmatter import parse_file
from ._yaml import load_yaml_file
from .errors import (
    KernelError,
    LEASE_HELD,
    POLICY_DENIED,
    POLICY_REQUIRES_AUTHORIZATION,
)


_AUTHORITY_RANK = {"uncalibrated": 0, "convention": 1, "hard": 2}

# Block 4.8: ops that don't write state pass through the lease check
# without target extraction. List is conservative — additions to read-
# only ops can be appended without breaking existing call sites.
_NON_WRITE_OPS: frozenset[str] = frozenset({
    "kernel.ir.get",
    "kernel.ir.list",
    "kernel.ir.deps",
    "kernel.gatekeeper.check",
    "kernel.selector.select",
    "kernel.calibrator.update",
    "kernel.voi.score",
})

# Block 4.8: ops whose own subject IS a lease record bypass the lease
# check (otherwise authoring a lease would require already holding one,
# producing a chicken-and-egg deadlock). The bypass mirrors Block 4.7's
# _SKIP_POLICY_PHASE_PROJECTIONS pattern for the policy-evaluation
# projection itself.
_SKIP_LEASE_PHASE_PROJECTIONS: frozenset[str] = frozenset({
    "_kernel.lease",
})


# ---------------------------------------------------------------------------
# Governance readers
# ---------------------------------------------------------------------------


def _load_index(repo: Path, name: str) -> Any:
    p = repo / ".8os" / "index" / f"{name}.yml"
    if not p.exists():
        return {}
    return load_yaml_file(p) or {}


def _iso_in_future(iso_ts: Any) -> bool:
    """Return True iff the ISO-8601 timestamp is strictly after now (UTC).

    Tolerant: malformed or non-string values return False (treated as
    expired). Mirrors the same predicate used in `_indexes.py` for
    lease-holders index population; duplicated here to avoid importing
    from a sibling private module.
    """
    from datetime import datetime, timezone

    if not isinstance(iso_ts, str) or not iso_ts:
        return False
    try:
        if iso_ts.endswith("Z"):
            iso_ts = iso_ts[:-1] + "+00:00"
        ts = datetime.fromisoformat(iso_ts)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts > datetime.now(timezone.utc)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Lease readers (Block 4.8)
# ---------------------------------------------------------------------------


def read_active_leases_for_target(repo: Path, target: str) -> list[dict[str, Any]]:
    """Return frontmatter dicts of active `_kernel.lease` records on `target`.

    `target` is a scope id or (I, R) id. Reads the `lease-holders` index
    for fast lookup, then re-validates each candidate's `valid_through`
    at read time (the index may be stale by up to one reindex tick).
    Cancelled and superseded leases are excluded.
    """
    lease_idx = _load_index(repo, "lease-holders")
    lease_ids = list(lease_idx.get(target) or [])
    if not lease_ids:
        return []
    id_to_path = _load_index(repo, "id-to-path")
    out: list[dict[str, Any]] = []
    for lease_id in lease_ids:
        rel = id_to_path.get(lease_id)
        if not rel or "#L" in rel:
            continue
        try:
            rec = parse_file(repo / rel)
        except Exception:
            continue
        fm = rec.frontmatter
        if fm.get("status") in {"superseded", "cancelled"}:
            continue
        if not _iso_in_future(fm.get("valid_through")):
            continue
        out.append(fm)
    return out


def _caller_holds_lease(lease_fm: dict[str, Any], caller_id: str | None) -> bool:
    """True iff `caller_id` is the lease's holder per the `held_by` field.

    Held-by patterns from spec v1.1 §7.1:
        factory:<factory-id> | process:<process-id> | author:<author-string>

    For first landing, factory/process holders are matched by direct string
    equality with the caller's bridge identity; author holders are matched
    by trailing-segment compare. Future blocks add factory/process
    identity-resolution machinery.
    """
    if not caller_id:
        return False
    held_by = lease_fm.get("held_by")
    if not isinstance(held_by, str) or not held_by:
        return False
    if held_by.startswith("author:"):
        return held_by[len("author:"):] == caller_id
    if held_by.startswith("factory:") or held_by.startswith("process:"):
        # Match by direct equality OR by trailing segment if the caller_id
        # carries a matching prefix. Conservative: future identity-resolution
        # block can refine.
        return held_by == caller_id or held_by.split(":", 1)[1] == caller_id
    return held_by == caller_id


def _extract_lease_targets(
    repo: Path,
    op_name: str,
    op_input: dict[str, Any],
) -> list[str]:
    """Return the list of lease targets (scope-id or (I, R) id) the op writes against.

    For ops with `scope_id` in input: includes the scope.
    For ops with `ir_id` or `for_ir_id`: includes the target id AND its
    scope (resolved from id-to-path). Per §13.5, parent scopes are also
    walked; for first landing, parent scope walking is reduced to "the
    target's own scope" (one level). Multi-level parent walking is a
    future-block extension when scope hierarchy depth becomes a real
    concern.

    Skips ops whose own subject is `_kernel.lease` (per
    `_SKIP_LEASE_PHASE_PROJECTIONS`). Skips read-only ops in
    `_NON_WRITE_OPS`.
    """
    if op_name in _NON_WRITE_OPS:
        return []
    ptypes = op_input.get("projection_types") or []
    if any(pt in _SKIP_LEASE_PHASE_PROJECTIONS for pt in ptypes):
        return []

    targets: list[str] = []
    scope_id = op_input.get("scope_id")
    if isinstance(scope_id, str) and scope_id:
        targets.append(scope_id)

    target_ir = op_input.get("ir_id") or op_input.get("for_ir_id")
    if isinstance(target_ir, str) and target_ir:
        if target_ir not in targets:
            targets.append(target_ir)
        id_to_path = _load_index(repo, "id-to-path")
        rel = id_to_path.get(target_ir)
        if isinstance(rel, str) and "#L" not in rel:
            try:
                rec = parse_file(repo / rel)
                target_scope = rec.frontmatter.get("scope")
                if isinstance(target_scope, str) and target_scope and target_scope not in targets:
                    targets.append(target_scope)
            except Exception:
                # Tolerate missing/unreadable target; lease check passes
                # through. Authority and policy phases will catch any
                # real reachability problems.
                pass
    return targets


def _check_leases(
    repo: Path,
    op_name: str,
    op_input: dict[str, Any],
    caller_context: predicates.CallerContext,
) -> None:
    """Phase 2 of `evaluate_op_pre_commit`. Raises `LEASE_HELD` on conflict.

    For each lease target the op writes against, walk active leases. If any
    lease has `lease_purpose: write` or `exclusive` and the caller is not
    the holder, reject. `read` and `shared` purposes are coordination
    metadata, not enforced on writes.
    """
    targets = _extract_lease_targets(repo, op_name, op_input)
    if not targets:
        return
    for target in targets:
        leases = read_active_leases_for_target(repo, target)
        for lease_fm in leases:
            if _caller_holds_lease(lease_fm, caller_context.caller_id):
                continue
            purpose = lease_fm.get("lease_purpose")
            if purpose not in {"write", "exclusive"}:
                continue
            raise KernelError(
                LEASE_HELD,
                (
                    f"target {target!r} is under an active lease "
                    f"{lease_fm.get('id')!r} held by {lease_fm.get('held_by')!r} "
                    f"with lease_purpose {purpose!r}; "
                    f"caller {caller_context.caller_id!r} does not hold the lease."
                ),
                input_field="lease",
                offending_value=target,
                suggested_action=(
                    f"acquire a compatible lease, wait for "
                    f"{lease_fm.get('id')!r} to expire at "
                    f"{lease_fm.get('valid_through')!r}, or supersede the "
                    f"lease (only the holder may supersede)"
                ),
                extra_context={
                    "lease_id": lease_fm.get("id"),
                    "lease_for": lease_fm.get("lease_for"),
                    "held_by": lease_fm.get("held_by"),
                    "lease_purpose": purpose,
                    "valid_through": lease_fm.get("valid_through"),
                },
            )


def read_roles_for_caller(repo: Path, caller_id: str, scope: str | None = None) -> list[str]:
    """Return the list of `_kernel.role` ids the caller holds.

    Walks `projection-to-ids` for `_kernel.role` records, loads each, and
    returns the role ids whose `holders` list contains `caller_id`. When
    `scope` is provided, restricts to roles whose record `scope` equals
    `scope` (or whose `applies_to_scope` matches if such a field is added
    in a future amendment).
    """
    proj_idx = _load_index(repo, "projection-to-ids")
    role_ids = list(proj_idx.get("_kernel.role") or [])
    id_to_path = _load_index(repo, "id-to-path")
    out: list[str] = []
    for rid in role_ids:
        rel = id_to_path.get(rid)
        if not rel:
            continue
        try:
            rec = parse_file(repo / rel)
        except Exception:
            continue
        fm = rec.frontmatter
        if scope is not None and fm.get("scope") != scope:
            continue
        if fm.get("status") not in (None, "open", "resolved"):
            continue
        holders = fm.get("holders") or []
        if caller_id in holders:
            out.append(rid)
    return sorted(out)


def read_policies_for_op(
    repo: Path,
    op_name: str,
    scope: str | None = None,
    classification: str | None = None,
) -> list[dict[str, Any]]:
    """Return list of policy frontmatter dicts that apply to the op.

    Per Block 4.7 Q-NEW-2: scan-and-filter via `projection-to-ids`. Policies
    are small in number; the O(N) scan is acceptable. If scale demands
    later, a `policies-by-op` index can be added in a future block.

    Returns dicts in author order (oldest first per `authored_on`),
    matching v1.1 §8.5's evaluation-order requirement.
    """
    proj_idx = _load_index(repo, "projection-to-ids")
    policy_ids = list(proj_idx.get("_kernel.policy") or [])
    id_to_path = _load_index(repo, "id-to-path")
    candidates: list[tuple[str, dict[str, Any]]] = []
    for pid in policy_ids:
        rel = id_to_path.get(pid)
        if not rel:
            continue
        try:
            rec = parse_file(repo / rel)
        except Exception:
            continue
        fm = rec.frontmatter
        if fm.get("status") not in (None, "open", "resolved"):
            continue
        applies_to_op = fm.get("applies_to_op") or []
        if op_name not in applies_to_op:
            continue
        applies_to_scope = fm.get("applies_to_scope")
        if applies_to_scope is not None and scope is not None and applies_to_scope != scope:
            continue
        applies_to_classification = fm.get("applies_to_classification")
        if (
            applies_to_classification is not None
            and classification is not None
            and applies_to_classification != classification
        ):
            continue
        candidates.append((fm.get("authored_on") or "", fm))
    candidates.sort(key=lambda pair: pair[0])
    return [fm for _, fm in candidates]


def read_cached_evaluation(repo: Path, op_signature: str) -> dict[str, Any] | None:
    """Return the cached evaluation frontmatter dict if a valid one exists.

    Validity criteria:
    - The evaluation record exists and is loadable.
    - `valid_through` is null OR has not elapsed (compared against the
      kernel's wall clock).
    - All `policies_consulted` policies still resolve to records with
      status open or resolved (not superseded or cancelled).

    Returns the frontmatter dict on cache hit, None on miss or expired.
    """
    pe_idx = _load_index(repo, "policy-evaluations")
    eval_id = pe_idx.get(op_signature)
    if not eval_id:
        return None
    id_to_path = _load_index(repo, "id-to-path")
    rel = id_to_path.get(eval_id)
    if not rel:
        return None
    try:
        rec = parse_file(repo / rel)
    except Exception:
        return None
    fm = rec.frontmatter
    valid_through = fm.get("valid_through")
    if valid_through is not None:
        from ._time import now_iso

        if valid_through <= now_iso():
            return None
    # Lazy correctness check on top of the eager invalidation: confirm all
    # consulted policies are still current. (Eager invalidation should have
    # set valid_through to expired already, but defense-in-depth.)
    consulted = fm.get("policies_consulted") or []
    for pid in consulted:
        prel = id_to_path.get(pid)
        if not prel:
            return None
        try:
            prec = parse_file(repo / prel)
        except Exception:
            return None
        if prec.frontmatter.get("status") in ("superseded", "cancelled"):
            return None
    return fm


# ---------------------------------------------------------------------------
# CallerContext population (closes Block 4.4 runtime placeholder + roles placeholder)
# ---------------------------------------------------------------------------


def build_caller_context(
    repo: Path,
    authored_via: str,
    op_input: dict[str, Any],
) -> predicates.CallerContext:
    """Populate a CallerContext from caller bridge identity + role membership.

    `authored_via` is the bridge id the op flows through. The bridge's
    record carries the caller's `authority_level`; for the `outside`
    sentinel the authority is `uncalibrated`.

    `caller_id` is read from the op input's `authored_by` field (the
    most consistent caller-identity field across kernel ops). `caller_scope`
    is the op input's `scope_id` (when present). `caller_roles` is built
    by querying `_kernel.role` records' `holders` lists for `caller_id`.

    `caller_data_classification_at_most` is read from the op input's
    `data_classification` field if present (the caller declares the
    classification of the data they're handling); the kernel doesn't
    interpret the value beyond string-equality matching at predicate
    evaluation time.
    """
    caller_id = op_input.get("authored_by") or "unknown"
    caller_scope = op_input.get("scope_id")
    caller_authority = _bridge_authority_level(repo, authored_via)
    # Roles can live in any scope and grant cross-scope permissions; the
    # caller's identity (membership in the holders list) is what matters,
    # not the role record's scope. `read_roles_for_caller` is called
    # without a scope filter to surface all role memberships.
    caller_roles = read_roles_for_caller(repo, caller_id)
    classification = op_input.get("data_classification")
    return predicates.CallerContext(
        caller_id=caller_id,
        caller_scope=caller_scope,
        caller_roles=tuple(caller_roles),
        caller_authority_level=caller_authority,
        caller_data_classification_at_most=classification,
    )


def _bridge_authority_level(repo: Path, authored_via: str) -> str:
    """Resolve authority level for a bridge id, used when building a
    `CallerContext` for the policy phase.

    Unlike `ir_ops._bridge_authority_level` (which raises NOT_FOUND for
    unregistered bridges to enforce strict caller identity in cancel),
    this pipeline-side helper falls back to `uncalibrated` for unknown
    bridges. Rationale: the policy phase runs on every wired op and
    must not raise spuriously when a userspace caller invokes through
    a not-yet-registered bridge (e.g., factory tests authoring records
    via `authored_via: anthropic` before the bridge record is materialized).
    Strict enforcement of bridge registration belongs in op-specific
    authority checks; the pipeline's role is to populate caller context
    for predicate evaluation, not to police bridge presence.
    """
    if authored_via == "outside":
        return "uncalibrated"
    bridge_path = repo / "ir" / "_kernel" / "bridge" / f"{authored_via}.md"
    if not bridge_path.exists():
        return "uncalibrated"
    try:
        rec = parse_file(bridge_path)
    except Exception:
        return "uncalibrated"
    return rec.frontmatter.get("authority_level", "uncalibrated")


# ---------------------------------------------------------------------------
# op_signature hashing (Q-NEW-4 (a): op_name + input + caller_context)
# ---------------------------------------------------------------------------


def compute_op_signature(
    op_name: str,
    op_input: dict[str, Any],
    caller_context: predicates.CallerContext,
) -> str:
    """SHA-256 over (op_name, canonical op_input, canonical caller_context).

    Per Block 4.7 Q-NEW-4: caller context is included in the cache key.
    Policy decisions referencing caller-identity leaves (role,
    authority_level, scope, caller) require per-caller-per-op caching for
    correctness. Sharing the cache across callers would silently produce
    wrong answers when these leaves participate in evaluation.

    `authorization_id` is excluded from the hash: authorizations are
    per-call ephemera used for `defer` override at materialization time,
    not policy-decision inputs. Including `authorization_id` in the cache
    key would defeat caching for override retries.
    """
    cleaned_input = {k: v for k, v in op_input.items() if k != "authorization_id"}
    payload = {
        "op": op_name,
        "input": cleaned_input,
        "caller": {
            "id": caller_context.caller_id,
            "scope": caller_context.caller_scope,
            "roles": list(caller_context.caller_roles),
            "authority_level": caller_context.caller_authority_level,
            "classification_at_most": caller_context.caller_data_classification_at_most,
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Pre-commit pipeline (v1.1 §8.6 phases 2-3)
# ---------------------------------------------------------------------------


def _author_policy_evaluation(
    repo: Path,
    op_name: str,
    op_signature: str,
    consulted: list[str],
    decision: str,
    transforms: list[Any],
    follow_ups: list[Any],
    defer_to: str | None,
) -> str:
    """Atomically commit a `_kernel.policy-evaluation` (I, R) recording the
    cache entry for this evaluation. Returns the evaluation id.

    Bypasses `kernel.ir.new` to avoid recursive policy-phase invocation
    (the kernel's own evaluation cache writes are not policy-gated). Uses
    the same `commit_staged` + `append_jsonl_line` + `write_all` pattern
    as `kernel.selector.select`.

    Imports are local to avoid a circular dependency with `sdk.ir_ops`.
    """
    from ._atomic import StagedFile, append_jsonl_line, commit_staged
    from ._events import make_event
    from ._frontmatter import IRRecord, serialize
    from ._indexes import write_all
    from ._paths import event_jsonl_path, ops_category_dir
    from ._time import now_iso

    ts = now_iso()
    eval_id = f"eval-{op_signature[:16]}-{ts.replace(':', '').replace('-', '').replace('.', '')[:14]}"
    target = ops_category_dir(repo, "policy-evaluation") / f"{eval_id}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    fm = {
        "id": eval_id,
        "kind": "ir-node",
        "tier": 2,
        "projection_types": ["_kernel.policy-evaluation"],
        "collapsed_summary": f"policy evaluation for {op_name} ({decision})",
        "expanded_into": None,
        "parent": None,
        "scope": "_ops",
        "depends_on": list(consulted),
        "visible_to": ["_ops"],
        "resolved_at": ts,
        "valid_through": None,
        "revalidate_trigger": None,
        "status": "resolved",
        "resolver": "kernel",
        "resolution_event": None,
        "authored_by": "kernel",
        "authored_on": ts,
        "authority_level": "convention",
        "authored_via": "kernel.self",
        "supersedes": None,
        "superseded_by": None,
        "surrogate_of": None,
        # _kernel.policy-evaluation projection-declared fields
        "evaluation_id": eval_id,
        "op_signature": op_signature,
        "policies_consulted": list(consulted),
        "decision": decision,
        "transform_actions": list(transforms),
        "follow_up_actions": list(follow_ups),
        "defer_to_role": defer_to,
        "evaluated_at": ts,
    }
    record = IRRecord(
        frontmatter=fm,
        intention_text=f"Policy evaluation for {op_name} (signature {op_signature[:16]}…).",
        resolution_text=f"Combined decision: {decision}.",
    )
    op_event = make_event(
        event_type="operation",
        ir_node_id=eval_id,
        ir_node_path_at_event=str(target.relative_to(repo).as_posix()),
        resolver_id="kernel",
        bridge_id=None,
        intention={
            "text": f"Policy evaluation for {op_name}",
            "context_refs": list(consulted),
            "scope": "_ops",
            "depth": 0,
        },
        resolution={
            "text": f"Decision: {decision}",
            "structured": {
                "op_signature": op_signature,
                "policies_consulted": list(consulted),
                "decision": decision,
            },
            "authority_level": "convention",
        },
        outcome="accepted",
        ts=ts,
    )
    commit_staged([StagedFile(target, content_text=serialize(record))])
    append_jsonl_line(event_jsonl_path(repo, ts), op_event)
    write_all(repo)
    return eval_id


def evaluate_op_pre_commit(
    repo: Path,
    op_name: str,
    op_input: dict[str, Any],
    caller_context: predicates.CallerContext,
    *,
    authorization_id: str | None = None,
) -> dict[str, Any]:
    """Run §8.6 phases 2 (lease) + 3 (policy eval) for an op.

    Returns a dict describing the accumulated decision:

        {
          "decision": "allow" | "deny" | "transform" | "defer" | "follow-up",
          "policies_consulted": [<policy-id>, ...],
          "transform_actions": [...],
          "follow_up_actions": [...],
          "defer_to_role": <role-id> | None,
          "evaluation_id": <existing eval id if cache hit, else None>,
        }

    Raises:
    - `POLICY_DENIED` when any applicable policy decides `deny`.
    - `POLICY_REQUIRES_AUTHORIZATION` when a `defer` policy fires and no
      satisfying authorization is presented.

    Caller is responsible for honoring the returned decision: applying
    transforms, queuing follow-ups, and authoring the `_kernel.policy-
    evaluation` record (Piece 6 caller side; this helper returns the
    structured decision).

    Lease check (phase 2) is active as of Block 4.8: walks the
    `lease-holders` index for each target the op writes, validates each
    candidate lease's `valid_through`, and raises `LEASE_HELD` when a
    non-holder targets a record under an active write/exclusive lease.
    `read` and `shared` lease purposes are coordination metadata only.
    """
    # ---- Phase 2: lease check (Block 4.8) -------------------------------
    # Walk active `_kernel.lease` records covering the op's target scope or
    # (I, R) (and the parent scopes resolved from a target ir_id per §13.5).
    # Reject with LEASE_HELD when an active lease held by another writer
    # covers the target with lease_purpose `write` or `exclusive`. `read`
    # and `shared` leases are coordination metadata; not enforced for
    # writes. Skips when the index is empty (most repos most of the time).
    _check_leases(repo, op_name, op_input, caller_context)

    # ---- Phase 3: policy evaluation -------------------------------------
    classification = op_input.get("data_classification")
    scope = op_input.get("scope_id")
    policies = read_policies_for_op(repo, op_name, scope=scope, classification=classification)
    if not policies:
        # Per v1.1 §8.6: ops with no applicable policies skip step 3.
        return {
            "decision": "allow",
            "policies_consulted": [],
            "transform_actions": [],
            "follow_up_actions": [],
            "defer_to_role": None,
            "evaluation_id": None,
        }

    # Cache lookup
    op_signature = compute_op_signature(op_name, op_input, caller_context)
    cached = read_cached_evaluation(repo, op_signature)
    if cached is not None:
        return _materialize_decision(cached, op_signature, authorization_id, repo, caller_context)

    # Cache miss: evaluate each policy in author order; accumulate.
    consulted: list[str] = []
    transforms: list[Any] = []
    follow_ups: list[Any] = []
    defer_to: str | None = None
    final_decision = "allow"
    for policy_fm in policies:
        pid = policy_fm.get("id")
        if not pid:
            continue
        consulted.append(pid)
        condition = policy_fm.get("condition")
        decision = policy_fm.get("decision", "allow")
        matched = _evaluate_policy_condition(repo, condition, op_input, caller_context)
        if not matched:
            continue
        if decision == "deny":
            final_decision = "deny"
            break  # short-circuit per §8.5
        if decision == "transform":
            ta = policy_fm.get("transform_action")
            if ta is not None:
                transforms.append(ta)
            if final_decision == "allow":
                final_decision = "transform"
        elif decision == "defer":
            defer_to = policy_fm.get("defer_to")
            if final_decision == "allow":
                final_decision = "defer"
        elif decision == "follow-up":
            fua = policy_fm.get("follow_up_action")
            if fua is not None:
                follow_ups.append(fua)
            if final_decision == "allow":
                final_decision = "follow-up"
        # decision == "allow" leaves final_decision unchanged

    # Write the policy-evaluation cache record (always, regardless of
    # decision — the cache reflects what the policies decided, not what
    # the op did with the decision after override checks).
    eval_id = _author_policy_evaluation(
        repo,
        op_name,
        op_signature,
        consulted,
        final_decision,
        transforms,
        follow_ups,
        defer_to,
    )
    result = {
        "decision": final_decision,
        "policies_consulted": consulted,
        "transform_actions": transforms,
        "follow_up_actions": follow_ups,
        "defer_to_role": defer_to,
        "op_signature": op_signature,
        "evaluation_id": eval_id,
    }
    return _materialize_decision(result, op_signature, authorization_id, repo, caller_context)


def _evaluate_policy_condition(
    repo: Path,
    condition: Any,
    op_input: dict[str, Any],
    caller_context: predicates.CallerContext,
) -> bool:
    """Evaluate a policy condition. Inline predicate (dict) or resolver id (string).

    Per Block 4.7 Q-NEW-5: inline predicates use caller-context-only
    semantics (reuse `predicates.evaluate_predicate` verbatim). For
    resolver-referenced conditions, the resolver is dispatched
    synchronously per Q-RESOLVER and is expected to return a boolean.
    Resolver-referenced conditions are deferred at this binary because
    the dispatch path (factory tick) imports kernel internals and a
    full implementation would expand scope; instead the kernel logs the
    intent and treats the condition as `False` (policy doesn't match).
    A future block fills the dispatch in.
    """
    if condition is None:
        return False
    if isinstance(condition, dict):
        # Inline predicate. Reuse Block 4.4's engine.
        try:
            return predicates.evaluate_predicate(condition, caller_context)
        except Exception:
            return False
    if isinstance(condition, str):
        # Resolver reference. Synchronous dispatch (Q-RESOLVER (a)) is the
        # locked path; full implementation deferred for this block. Return
        # False so the policy doesn't fire (fail-safe).
        return False
    return False


def _materialize_decision(
    cached_or_fresh: dict[str, Any],
    op_signature: str,
    authorization_id: str | None,
    repo: Path,
    caller_context: predicates.CallerContext,
) -> dict[str, Any]:
    """Apply the decision: raise on deny, raise-or-allow on defer with override
    check, return decision dict on allow/transform/follow-up.

    `defer` interacts with `authorization_id`: when an authorization is
    presented and the authoring author holds the `defer_to` role, the
    decision is upgraded to `allow` (the override path). Otherwise
    `POLICY_REQUIRES_AUTHORIZATION` is raised.
    """
    decision = cached_or_fresh.get("decision", "allow")
    consulted = cached_or_fresh.get("policies_consulted") or []
    if decision == "deny":
        raise KernelError(
            POLICY_DENIED,
            f"op denied by policy (consulted: {consulted!r})",
            extra_context={
                "op_signature": op_signature,
                "policies_consulted": consulted,
            },
        )
    if decision == "defer":
        defer_to = cached_or_fresh.get("defer_to_role") or cached_or_fresh.get("defer_to")
        if authorization_id is not None and _authorization_satisfies(
            repo, authorization_id, defer_to
        ):
            return {
                **cached_or_fresh,
                "decision": "allow",
                "op_signature": op_signature,
                "override_authorization_id": authorization_id,
            }
        raise KernelError(
            POLICY_REQUIRES_AUTHORIZATION,
            f"op deferred to role {defer_to!r}; authorization required",
            extra_context={
                "op_signature": op_signature,
                "defer_to_role": defer_to,
                "policies_consulted": consulted,
            },
            suggested_action=(
                f"submit the op carrying authorization_id from a holder of "
                f"role {defer_to!r}"
            ),
        )
    return {**cached_or_fresh, "op_signature": op_signature}


def _authorization_satisfies(repo: Path, authorization_id: str, defer_to_role: str | None) -> bool:
    """Check whether an authorization permits the deferred op.

    Per v1.1 §8.4: a `defer` decision is overridden by an authorization
    from a holder of the deferred role. This check loads the
    authorization (I, R) and verifies its `authored_by` is in the
    deferred role's holders list.
    """
    if defer_to_role is None:
        return False
    id_to_path = _load_index(repo, "id-to-path")
    rel = id_to_path.get(authorization_id)
    if not rel:
        return False
    try:
        auth_rec = parse_file(repo / rel)
    except Exception:
        return False
    granter = auth_rec.frontmatter.get("authored_by")
    if not granter:
        return False
    role_holders = read_roles_for_caller(repo, granter)
    return defer_to_role in role_holders


# ---------------------------------------------------------------------------
# Cache invalidation on policy supersession (Q-CACHE (a) walk-on-supersession)
# ---------------------------------------------------------------------------


def invalidate_cache_for_policy(repo: Path, policy_id: str) -> list[str]:
    """Mark all `_kernel.policy-evaluation` records that consulted `policy_id`
    as expired by setting their `valid_through` to now-1s.

    Returns the list of evaluation ids whose `valid_through` was updated.

    Called by `kernel.ir.supersede` when a `_kernel.policy` record is
    superseded (Block 4.7 Q-CACHE (a) eager walk-on-supersession). Walks
    the `projection-to-ids` index for `_kernel.policy-evaluation`,
    inspects each record's `policies_consulted`, and rewrites the
    matching records on disk.
    """
    from ._frontmatter import serialize
    from ._time import now_iso

    proj_idx = _load_index(repo, "projection-to-ids")
    eval_ids = list(proj_idx.get("_kernel.policy-evaluation") or [])
    id_to_path = _load_index(repo, "id-to-path")
    expired_ts = now_iso()  # any iso string in the past works; using "now"
    invalidated: list[str] = []
    for eid in eval_ids:
        rel = id_to_path.get(eid)
        if not rel:
            continue
        try:
            rec = parse_file(repo / rel)
        except Exception:
            continue
        consulted = rec.frontmatter.get("policies_consulted") or []
        if policy_id not in consulted:
            continue
        # Set valid_through to a past timestamp. Reading this evaluation
        # later returns None (treated as expired). The record stays on
        # disk for audit; only the cache field is updated.
        rec.frontmatter["valid_through"] = expired_ts
        (repo / rel).write_text(serialize(rec), encoding="utf-8")
        invalidated.append(eid)
    return invalidated
