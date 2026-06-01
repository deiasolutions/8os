"""kernel.ir.* operations.

Block 1 §7.6.3–§7.6.8, plus get/list/deps from §7.6.15–§7.6.17.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .. import KERNEL_BINARY_RESOLVER_ID
from .._atomic import StagedFile, append_jsonl_line, atomic_write_text, commit_staged
from .._events import find_event, iter_events, make_event
from .._frontmatter import IRRecord, parse_file, serialize
from .._indexes import write_all
from .._paths import (
    event_jsonl_path,
    ir_collapsed_path,
    ir_dir,
    kernel_record_path,
    ops_category_dir,
    scope_dir,
)
from .._projections import (
    filename_suffix_for,
    target_subdirectory_for,
    validate_extensions,
)
from .._time import now_iso
from .._yaml import load_yaml_file
from .. import predicates
from ..errors import (
    ALREADY_EXISTS,
    AUTHORITY_INSUFFICIENT,
    CANCELLATION_AUTHORITY_INSUFFICIENT,
    DEPENDENCY_BROKEN,
    INVALID_STATE,
    IR_ALREADY_CANCELLED,
    IR_NOT_CANCELLABLE,
    IR_NOT_VISIBLE,
    IR_SUPERSEDES_TARGET_NOT_CANCELLED,
    NOT_FOUND,
    SCHEMA_INVALID,
    SCOPE_VIOLATION,
    VISIBILITY_PREDICATE_NOT_PERMITTED,
    KernelError,
)
from ._common import repo_root_or_raise

OPS_SCOPE = "_ops"
KERNEL_SCOPE = "_kernel"
TIER2_CATEGORIES = (
    "resolver-selection",
    "authorization",
    "capability-update",
    # v1.1 §7.4 (Block 4.7): policy-evaluation cache records are tier 2
    # operation-output records authored by the kernel during the policy-
    # evaluation phase. On-disk location: ir/_ops/policy-evaluation/<id>.md.
    "policy-evaluation",
)
# Projection types that imply the (I, R) lives under ir/_kernel/<category>/.
KERNEL_PROJECTION_TO_CATEGORY: dict[str, str] = {
    "_kernel.scope": "scope",
    "_kernel.projection": "projection",
    "_kernel.resolver": "resolver",
    "_kernel.bridge": "bridge",
    "_kernel.surrogate-lineage": "surrogate-lineage",
}


# ---- ir.new ----------------------------------------------------------------


def new(payload: dict[str, Any]) -> dict[str, Any]:
    repo = repo_root_or_raise()
    scope_id = payload["scope_id"]
    slug = payload["slug"]
    tier = int(payload["tier"])
    intention = payload["intention_text"]
    projection_types: list[str] = list(payload.get("projection_types") or [])
    parent_id = payload.get("parent_id")
    depends_on: list[str] = list(payload.get("depends_on") or [])
    authority = payload["authority_level"]
    author = payload["authored_by"]
    # v1.0.1-partial Amendment 2: authored_via is mandatory. The SDK layer
    # (`_runner._apply_sdk_defaults`) defaults this to `"outside"` for
    # non-internal callers; internal ops author records directly without
    # passing through ir.new's payload. Validated non-empty by the input
    # schema; defensively double-check here for tier 3 path callers and
    # future programmatic users that bypass the runner.
    authored_via = payload.get("authored_via")
    if not isinstance(authored_via, str) or not authored_via.strip():
        raise KernelError(
            SCHEMA_INVALID,
            "kernel.ir.new requires non-empty authored_via "
            "(v1.0.1-partial Amendment 2)",
            input_field="authored_via",
            offending_value=authored_via,
        )
    summary = payload.get("collapsed_summary") or _first_line(intention)
    extensions: dict[str, Any] = dict(payload.get("frontmatter_extensions") or {})
    stakes = payload.get("stakes")  # v1.0 §2.3: optional base frontmatter
    domain = payload.get("domain")  # v1.1 §4.3: optional base frontmatter
    if domain is not None and (not isinstance(domain, str) or not domain.strip()):
        raise KernelError(
            SCHEMA_INVALID,
            "kernel.ir.new domain, when supplied, must be a non-empty string "
            "(v1.1 §4.3); use null to omit",
            input_field="domain",
            offending_value=domain,
        )
    data_classification = payload.get("data_classification")  # v1.1 §4.2 (Block 4.3)
    if data_classification is not None and (
        not isinstance(data_classification, str) or not data_classification.strip()
    ):
        raise KernelError(
            SCHEMA_INVALID,
            "kernel.ir.new data_classification, when supplied, must be a "
            "non-empty string (v1.1 §4.2); use null to omit",
            input_field="data_classification",
            offending_value=data_classification,
        )
    # v1.1 axiom 4 / §4 (Block 4.8): optional valid_through lift. Same null-
    # vs-empty discipline as domain / data_classification (Block 4.5
    # Amendment 1). Records that observe expiration semantics include
    # `_kernel.lease` and `_kernel.policy-evaluation`.
    valid_through = payload.get("valid_through")
    if valid_through is not None and (
        not isinstance(valid_through, str) or not valid_through.strip()
    ):
        raise KernelError(
            SCHEMA_INVALID,
            "kernel.ir.new valid_through, when supplied, must be a non-empty "
            "ISO-8601 string (v1.1 axiom 4); use null to omit",
            input_field="valid_through",
            offending_value=valid_through,
        )
    # v1.1 §3.2 (Block 4.6 / BLOCK-4.5-SPEC-AMENDMENTS Amendment 4 — Path A):
    # optional `supersedes:` carries lineage backward to a cancelled record.
    # Validated against id-to-path and target status below (after id-to-path
    # is loaded). Empty string rejects at schema layer; defensive check here
    # for callers bypassing the runner.
    supersedes_target = payload.get("supersedes")
    if supersedes_target is not None and (
        not isinstance(supersedes_target, str) or not supersedes_target.strip()
    ):
        raise KernelError(
            SCHEMA_INVALID,
            "kernel.ir.new supersedes, when supplied, must be a non-empty "
            "string (v1.1 §3.2); use null to omit",
            input_field="supersedes",
            offending_value=supersedes_target,
        )
    visible_when = payload.get("visible_when")  # v1.1 §4.4 (Block 4.4)
    if visible_when is not None:
        # Structured shape validation lives in `eightos.predicates`. Raises
        # SCHEMA_INVALID with a path-into-the-predicate context on bad
        # shapes. The input schema only checks "object|null"; this call
        # checks the predicate's internal structure.
        predicates.validate_predicate(visible_when)
        # v1.1 §4.4: visibility predicates encode access control, which is
        # sovereignty-shaped — only hard-authored records may carry them.
        if authority != "hard":
            raise KernelError(
                VISIBILITY_PREDICATE_NOT_PERMITTED,
                f"visible_when predicates are permitted only on hard-"
                f"authored records (got authority_level={authority!r}). "
                "v1.1 §4.4: visibility predicates encode access control, "
                "which is sovereignty-shaped.",
                input_field="visible_when",
                offending_value=authority,
                suggested_action=(
                    "re-author with authority_level: hard, or omit "
                    "visible_when to use the default axiom-3 scope rules"
                ),
            )

    ts = now_iso()

    # ---- pre-flight checks --------------------------------------------------
    id_to_path = _load_index(repo, "id-to-path")
    if slug in id_to_path:
        raise KernelError(
            ALREADY_EXISTS,
            f"(I, R) id {slug!r} already exists at {id_to_path[slug]!r}",
            input_field="slug",
            offending_value=slug,
        )

    for dep in depends_on:
        if dep not in id_to_path:
            raise KernelError(
                DEPENDENCY_BROKEN,
                f"depends_on references unknown (I, R) id {dep!r}",
                input_field="depends_on",
                offending_value=dep,
            )

    if parent_id is not None and parent_id not in id_to_path:
        raise KernelError(
            NOT_FOUND,
            f"parent_id {parent_id!r} not found",
            input_field="parent_id",
            offending_value=parent_id,
        )

    # v1.1 §3.2 Path A (Block 4.6): validate supersedes target. Missing
    # target reuses generic NOT_FOUND per Block 4.6 Q1 / F1 (the existing
    # kernel pattern; v1.1 §18.1's IR_NOT_FOUND reading is treated as the
    # generic code, with the broader IR-prefixed migration deferred per
    # Block 4.4 F4). Wrong-state target raises the new code introduced
    # specifically for this path.
    if supersedes_target is not None:
        if supersedes_target not in id_to_path:
            raise KernelError(
                NOT_FOUND,
                f"supersedes target {supersedes_target!r} not found "
                "(v1.1 §3.2 supersede-with-replacement requires the "
                "cancelled target to exist on disk)",
                input_field="supersedes",
                offending_value=supersedes_target,
            )
        _supersedes_target_path = repo / id_to_path[supersedes_target]
        _supersedes_target_rec = parse_file(_supersedes_target_path)
        target_status = _supersedes_target_rec.frontmatter.get("status")
        if target_status != "cancelled":
            raise KernelError(
                IR_SUPERSEDES_TARGET_NOT_CANCELLED,
                f"supersedes target {supersedes_target!r} has status "
                f"{target_status!r}; supersede-with-replacement applies only "
                "to cancelled records (v1.1 §3.2 Path A). For superseding "
                "living records (open/resolved/stale), use kernel.ir.supersede.",
                input_field="supersedes",
                offending_value=supersedes_target,
                suggested_action=(
                    "use kernel.ir.supersede for living records, or omit "
                    "supersedes to author an unrelated record"
                ),
            )

    # ---- v0.2 §2.1: projection-declared frontmatter validation -------------
    validated_extensions = (
        validate_extensions(repo, projection_types, extensions)
        if projection_types
        else {}
    )

    # ---- v1.0 §2.1: reject cost_model: piecewise on resolver registrations -
    if "_kernel.resolver" in projection_types:
        cost_model = validated_extensions.get("cost_model")
        if cost_model == "piecewise":
            raise KernelError(
                INVALID_STATE,
                "cost_model: piecewise is reserved but not specified in v1.0; "
                "use fixed or linear-in-depth (v1.0 §2.1)",
                input_field="frontmatter_extensions.cost_model",
                offending_value=cost_model,
            )
        if cost_model == "linear-in-depth":
            if not validated_extensions.get("cost_per_depth_unit"):
                raise KernelError(
                    INVALID_STATE,
                    "cost_model: linear-in-depth requires cost_per_depth_unit "
                    "(v1.0 §2.1)",
                    input_field="frontmatter_extensions.cost_per_depth_unit",
                )

    # ---- v1.0 §3.2: calibration-policy ground_truth/proxy cross-field check -
    if "_kernel.calibration-policy" in projection_types:
        signal = validated_extensions.get("calibration_signal")
        if signal == "ground_truth" and not validated_extensions.get("ground_truth_resolver"):
            raise KernelError(
                INVALID_STATE,
                "calibration_signal: ground_truth requires non-null "
                "ground_truth_resolver (v1.0 §3.2)",
                input_field="frontmatter_extensions.ground_truth_resolver",
            )
        if signal == "proxy" and not validated_extensions.get("proxy_specification"):
            raise KernelError(
                INVALID_STATE,
                "calibration_signal: proxy requires proxy_specification "
                "(v1.0 §3.2)",
                input_field="frontmatter_extensions.proxy_specification",
            )

    # ---- v0.2 §2.3: _kernel scope hard-authority enforcement ---------------
    kernel_category = _kernel_category_for(projection_types)
    if scope_id == KERNEL_SCOPE or kernel_category is not None:
        if authority != "hard":
            raise KernelError(
                AUTHORITY_INSUFFICIENT,
                f"(I, R) authored into the _kernel scope requires authority_level: hard "
                f"(got {authority!r}). See spec §2.3.",
                input_field="authority_level",
                offending_value=authority,
                suggested_action="re-author with authority_level: hard via a hard-authority bridge",
                axiom_violated=6,
            )

    # ---- Policy evaluation phase (v1.1 §8.6, Block 4.7) -------------------
    # Skip when authoring `_kernel.policy-evaluation` records (those are
    # written by the pipeline itself and would cause infinite recursion).
    # Skip when authoring `_kernel.policy` / `_kernel.role` records (the
    # records that constitute the policy machinery — gating their authoring
    # by themselves is a footgun; the existing hard-authority check is the
    # gate). Other ops flow through the pipeline.
    _SKIP_POLICY_PHASE_PROJECTIONS = {
        "_kernel.policy-evaluation",
        "_kernel.policy",
        "_kernel.role",
    }
    if not any(p in _SKIP_POLICY_PHASE_PROJECTIONS for p in projection_types):
        from .. import op_pipeline as _pipeline

        caller_context = _pipeline.build_caller_context(
            repo,
            authored_via,
            {"authored_by": author, "scope_id": scope_id, "data_classification": data_classification},
        )
        _pipeline.evaluate_op_pre_commit(
            repo,
            "kernel.ir.new",
            {
                "scope_id": scope_id,
                "slug": slug,
                "tier": tier,
                "projection_types": projection_types,
                "data_classification": data_classification,
                "domain": domain,
            },
            caller_context,
            authorization_id=payload.get("authorization_id"),
        )

    # ---- resolve target path -----------------------------------------------
    if tier == 2:
        category = _tier2_category(projection_types)
        _ensure_ops_scope(repo, author, ts)
        target_path = ops_category_dir(repo, category) / f"{slug}.md"
        record_scope = OPS_SCOPE
    elif tier == 1:
        if kernel_category is not None:
            # v0.2: kernel-configuration (I, R)s live under ir/_kernel/<category>/.
            target_path = kernel_record_path(repo, kernel_category, slug)
            record_scope = KERNEL_SCOPE
        else:
            _require_scope_exists(repo, scope_id)
            record_scope = scope_id
            if parent_id is None:
                # v0.2 §2.2: filename suffix from projection.
                suffix = filename_suffix_for(repo, projection_types) if projection_types else ".md"
                # v1.0.1-partial Amendment 1: projection-declared subdirectory.
                subdir = (
                    target_subdirectory_for(repo, projection_types)
                    if projection_types
                    else None
                )
                base = scope_dir(repo, scope_id)
                if subdir is not None:
                    base = base / subdir
                    base.mkdir(parents=True, exist_ok=True)
                target_path = base / f"{slug}{suffix}"
            else:
                parent_relpath = id_to_path[parent_id]
                target_path = _child_path_under(repo, parent_relpath, slug)
    else:  # tier 3
        return _new_tier3(
            repo=repo,
            slug=slug,
            scope_id=scope_id,
            intention=intention,
            depends_on=depends_on,
            projection_types=projection_types,
            authority=authority,
            author=author,
            authored_via=authored_via,
            ts=ts,
            summary=summary,
        )

    relpath = str(target_path.relative_to(repo).as_posix())

    # Pre-allocate the operation event id; the new record references it as its
    # creation event (resolution_event stays null because the (I, R) is open).
    op_event = make_event(
        event_type="operation",
        ir_node_id=slug,
        ir_node_path_at_event=relpath,
        resolver_id="kernel",
        bridge_id=None,
        intention={
            "text": f"Create (I, R) {slug!r} in scope {scope_id!r} at tier {tier}.",
            "context_refs": depends_on,
            "scope": scope_id,
            "depth": 0,
        },
        resolution={
            "text": f"Created at {ts}.",
            "structured": {
                "ir_id": slug,
                "path": relpath,
                "tier": tier,
                "authored_by": author,
            },
            "authority_level": authority,
        },
        outcome="accepted",
        ts=ts,
    )

    fm: dict[str, Any] = {
        "id": slug,
        "kind": "ir-node",
        "tier": tier,
        "projection_types": projection_types,
        "collapsed_summary": summary,
        "expanded_into": None,
        "parent": parent_id,
        "scope": record_scope,
        "depends_on": depends_on,
        "visible_to": [record_scope],
        "resolved_at": None,
        "valid_through": valid_through,
        "revalidate_trigger": None,
        "status": "open",
        "resolver": None,
        "resolution_event": None,
        "authored_by": author,
        "authored_on": ts,
        "authority_level": authority,
        "authored_via": authored_via,
        # v1.1 §3.2 Path A (Block 4.6): when supersedes is non-null, this
        # record carries lineage backward to a cancelled target. The
        # cancelled target is unchanged (no superseded_by written there);
        # the lineage is unidirectional from the new record only. For the
        # living-record supersede flow (kernel.ir.supersede), this field
        # is set by that op's handler instead.
        "supersedes": supersedes_target,
        "superseded_by": None,
        "surrogate_of": None,
    }
    # v1.0 §2.3: stakes is an optional base field. Written only when provided
    # by the caller; absence means "stakes unknown" which VOI handles per §3.7.
    if stakes is not None:
        fm["stakes"] = stakes
    # v1.1 §4.3: domain is an optional base field. Written only when provided;
    # absence falls back to the scope's domain_default at policy-match time.
    if domain is not None:
        fm["domain"] = domain
    # v1.1 §4.2 (Block 4.3): data_classification is an optional base field.
    # Written only when provided; absence falls back to the scope's
    # data_classification_default at classification-policy-match time.
    # ---- policy evaluation placeholder (classification-based gating) ------
    # When `_kernel.policy` and the policy-evaluation phase land (v1.1 §8),
    # this is the plug-in point where a write-time policy can reject an
    # incoming `data_classification` per §11.7. CLASSIFICATION_VIOLATION is
    # already defined in errors.py for forward-compat.
    if data_classification is not None:
        fm["data_classification"] = data_classification
    # v1.1 §4.4 (Block 4.4): visible_when predicate. Validated for shape and
    # hard-authority above; written to fm only when non-None. Read-op
    # evaluation (kernel.ir.get / .list / .deps) consumes this field.
    if visible_when is not None:
        fm["visible_when"] = visible_when
    # v0.2 §2.1: projection-declared extensions merge in alongside base fields.
    fm.update(validated_extensions)
    record = IRRecord(frontmatter=fm, intention_text=intention, resolution_text=None)

    if target_path.exists():
        raise KernelError(
            ALREADY_EXISTS,
            f"target path {relpath!r} already occupied",
            input_field="slug",
            offending_value=slug,
        )

    commit_staged([StagedFile(target_path, content_text=serialize(record))])
    append_jsonl_line(event_jsonl_path(repo, ts), op_event)
    write_all(repo)

    # v1.0 §3.4: when a calibration-policy-proposal is authored, check
    # standing authorizations and dispatch the calibrator's approval if
    # any pre-grant matches. The dispatch authors a follow-on supersession
    # of the proposal carrying proposal_status: approved AND the actual
    # supersession on the target calibration policy. Append-only preserved:
    # the original pending proposal stays on disk.
    dispatched = None
    if "_kernel.calibration-policy-proposal" in projection_types:
        dispatched = _dispatch_proposal_approval(
            repo=repo,
            proposal_id=slug,
            proposal_fm=fm,
            authored_by=author,
        )

    out = {
        "data": {"ir_id": slug, "path": relpath, "tier": tier},
        "event_id": op_event["event_id"],
        "indexes_updated": [
            "id-to-path",
            "path-to-id",
            "scope-to-ids",
            "tier-to-ids",
            "projection-to-ids",
            "deps-forward",
            "deps-reverse",
            "_checksum",
        ],
    }
    if dispatched is not None:
        out["data"]["calibrator_dispatch"] = dispatched
    return out


def _dispatch_proposal_approval(
    *,
    repo: Path,
    proposal_id: str,
    proposal_fm: dict[str, Any],
    authored_by: str,
) -> dict[str, Any] | None:
    """v1.0 §3.4: check standing authorizations against a proposal; if matched,
    author both the approved-proposal supersession and the policy supersession.

    Returns a dict describing the dispatch (or None when no auth matched).
    Honors v1.0's append-only discipline (Q3 option ii — supersession chain).
    """
    from .. import calibration

    matched_auth = calibration.find_matching_authorization(repo, proposal_fm)
    if matched_auth is None:
        return None

    target_policy_id = proposal_fm.get("target_policy")
    proposed_changes = proposal_fm.get("proposed_changes") or {}

    # 1. Author the policy supersession first so we can cross-reference its id
    #    on the approved proposal record.
    policy_supersession_id = _author_policy_supersession(
        repo=repo,
        target_policy_id=target_policy_id,
        proposed_changes=proposed_changes,
        authored_by=authored_by,
        approved_via_authorization=matched_auth.get("id"),
        from_proposal=proposal_id,
    )

    # 2. Author the approved follow-on proposal (supersession chain) carrying
    #    proposal_status: approved and effective_supersession pointing at
    #    the policy supersession.
    approval_supersession_id = _author_proposal_approval_supersession(
        repo=repo,
        original_proposal_id=proposal_id,
        original_proposal_fm=proposal_fm,
        policy_supersession_id=policy_supersession_id,
        matched_authorization_id=matched_auth.get("id"),
        authored_by=authored_by,
    )

    return {
        "matched_authorization_id": matched_auth.get("id"),
        "approved_proposal_id": approval_supersession_id,
        "policy_supersession_id": policy_supersession_id,
    }


def _author_policy_supersession(
    *,
    repo: Path,
    target_policy_id: str,
    proposed_changes: dict[str, Any],
    authored_by: str,
    approved_via_authorization: str | None,
    from_proposal: str,
) -> str:
    """Author a `_kernel.calibration-policy` supersession applying proposed_changes.

    Built on top of v0.2's `kernel.ir.supersede` mechanics — the new (I, R)
    carries the same projection_type, takes the prior policy's frontmatter
    as a base, applies proposed_changes, and links via `supersedes`.
    """
    id_to_path = _load_index(repo, "id-to-path")
    if target_policy_id not in id_to_path:
        raise KernelError(
            NOT_FOUND,
            f"target_policy {target_policy_id!r} not found",
            input_field="target_policy",
        )
    old_relpath = id_to_path[target_policy_id]
    old_abs = repo / old_relpath
    old_rec = parse_file(old_abs)
    ts = now_iso()
    new_id = f"{target_policy_id}.s{int(_count_supersessions(repo, target_policy_id)) + 1}"
    new_abs = old_abs.parent / f"{new_id}{old_abs.suffix}" if not old_abs.name.endswith(".policy.md") else old_abs.parent / f"{new_id}.policy.md"

    new_fm = dict(old_rec.frontmatter)
    new_fm["id"] = new_id
    new_fm["status"] = "resolved"
    new_fm["supersedes"] = target_policy_id
    new_fm["superseded_by"] = None
    new_fm["authored_by"] = authored_by
    new_fm["authored_on"] = ts
    new_fm["resolved_at"] = ts
    # Apply proposed changes to projection-declared frontmatter.
    for k, v in (proposed_changes or {}).items():
        new_fm[k] = v
    # The policy_id frontmatter field must equal the (I, R)'s id per the
    # _kernel.calibration-policy projection's required_frontmatter.
    if "policy_id" in new_fm:
        new_fm["policy_id"] = new_id

    new_rec = IRRecord(
        frontmatter=new_fm,
        intention_text=old_rec.intention_text,
        resolution_text=(
            f"Calibration policy superseded at {ts} via approved proposal "
            f"{from_proposal!r} matched by standing authorization "
            f"{approved_via_authorization!r}."
        ),
    )

    old_rec.frontmatter["status"] = "superseded"
    old_rec.frontmatter["superseded_by"] = new_id

    op_event = make_event(
        event_type="operation",
        ir_node_id=new_id,
        ir_node_path_at_event=str(new_abs.relative_to(repo).as_posix()),
        resolver_id="kernel.calibrator",
        bridge_id=None,
        intention={
            "text": (
                f"Supersede calibration policy {target_policy_id!r} per "
                f"approved proposal {from_proposal!r}."
            ),
            "context_refs": [target_policy_id, from_proposal, approved_via_authorization or ""],
            "scope": old_rec.frontmatter.get("scope"),
            "depth": 0,
        },
        resolution={
            "text": f"Policy superseded at {ts}.",
            "structured": {
                "old_policy_id": target_policy_id,
                "new_policy_id": new_id,
                "from_proposal": from_proposal,
                "matched_authorization": approved_via_authorization,
            },
            "authority_level": "hard",
        },
        outcome="accepted",
        ts=ts,
    )

    commit_staged(
        [
            StagedFile(old_abs, content_text=serialize(old_rec)),
            StagedFile(new_abs, content_text=serialize(new_rec)),
        ]
    )
    append_jsonl_line(event_jsonl_path(repo, ts), op_event)
    write_all(repo)
    return new_id


def _author_proposal_approval_supersession(
    *,
    repo: Path,
    original_proposal_id: str,
    original_proposal_fm: dict[str, Any],
    policy_supersession_id: str,
    matched_authorization_id: str | None,
    authored_by: str,
) -> str:
    """Author a follow-on `_kernel.calibration-policy-proposal` (I, R) carrying
    proposal_status: approved and effective_supersession: <policy-supersession-id>,
    superseding the original pending proposal per Q3's supersession-chain decision.
    """
    id_to_path = _load_index(repo, "id-to-path")
    if original_proposal_id not in id_to_path:
        raise KernelError(NOT_FOUND, f"original proposal {original_proposal_id!r} missing")
    old_relpath = id_to_path[original_proposal_id]
    old_abs = repo / old_relpath
    old_rec = parse_file(old_abs)
    ts = now_iso()
    new_id = f"{original_proposal_id}.s{int(_count_supersessions(repo, original_proposal_id)) + 1}"
    suffix = ".proposal.md" if old_abs.name.endswith(".proposal.md") else old_abs.suffix
    new_abs = old_abs.parent / f"{new_id}{suffix}"

    new_fm = dict(old_rec.frontmatter)
    new_fm["id"] = new_id
    new_fm["status"] = "resolved"
    new_fm["supersedes"] = original_proposal_id
    new_fm["superseded_by"] = None
    new_fm["authored_by"] = authored_by
    new_fm["authored_on"] = ts
    new_fm["resolved_at"] = ts
    new_fm["proposal_id"] = new_id
    new_fm["proposal_status"] = "approved"
    new_fm["effective_supersession"] = policy_supersession_id

    new_rec = IRRecord(
        frontmatter=new_fm,
        intention_text=old_rec.intention_text,
        resolution_text=(
            f"Proposal approved at {ts} via standing authorization "
            f"{matched_authorization_id!r}; calibrator dispatched the policy "
            f"supersession at {policy_supersession_id!r}."
        ),
    )

    old_rec.frontmatter["status"] = "superseded"
    old_rec.frontmatter["superseded_by"] = new_id

    op_event = make_event(
        event_type="operation",
        ir_node_id=new_id,
        ir_node_path_at_event=str(new_abs.relative_to(repo).as_posix()),
        resolver_id="kernel.calibrator",
        bridge_id=None,
        intention={
            "text": (
                f"Approve proposal {original_proposal_id!r} via standing "
                f"authorization {matched_authorization_id!r}."
            ),
            "context_refs": [
                original_proposal_id,
                policy_supersession_id,
                matched_authorization_id or "",
            ],
            "scope": old_rec.frontmatter.get("scope"),
            "depth": 0,
        },
        resolution={
            "text": f"Approved at {ts}.",
            "structured": {
                "from_proposal": original_proposal_id,
                "approved_proposal": new_id,
                "matched_authorization": matched_authorization_id,
                "policy_supersession": policy_supersession_id,
            },
            "authority_level": "hard",
        },
        outcome="accepted",
        ts=ts,
    )

    commit_staged(
        [
            StagedFile(old_abs, content_text=serialize(old_rec)),
            StagedFile(new_abs, content_text=serialize(new_rec)),
        ]
    )
    append_jsonl_line(event_jsonl_path(repo, ts), op_event)
    write_all(repo)
    return new_id


def _new_tier3(
    *,
    repo: Path,
    slug: str,
    scope_id: str,
    intention: str,
    depends_on: list[str],
    projection_types: list[str],
    authority: str,
    author: str,
    authored_via: str,
    ts: str,
    summary: str,
) -> dict[str, Any]:
    """Tier 3 ir.new: record the (I, R) as a JSONL line + op event."""
    new_event = make_event(
        event_type="operation",
        ir_node_id=slug,
        ir_node_path_at_event=str(event_jsonl_path(repo, ts).relative_to(repo).as_posix()),
        resolver_id="kernel",
        bridge_id=authored_via,
        intention={
            "text": intention,
            "context_refs": depends_on,
            "scope": scope_id,
            "depth": 0,
        },
        resolution={
            "text": f"Created tier 3 (I, R) at {ts}.",
            "structured": {
                "ir_id": slug,
                "tier": 3,
                "summary": summary,
                "projection_types": projection_types,
                "authored_by": author,
            },
            "authority_level": authority,
        },
        outcome="accepted",
        ts=ts,
        event_id=slug,  # tier 3 (I, R) id == event id by construction
    )
    op_event = make_event(
        event_type="operation",
        ir_node_id=slug,
        ir_node_path_at_event=str(event_jsonl_path(repo, ts).relative_to(repo).as_posix()),
        resolver_id="kernel",
        bridge_id=authored_via,
        intention={
            "text": f"Create tier 3 (I, R) {slug!r}.",
            "context_refs": [slug],
            "scope": scope_id,
            "depth": 0,
        },
        resolution={
            "text": f"Created at {ts}.",
            "structured": {"ir_id": slug, "tier": 3},
            "authority_level": authority,
        },
        outcome="accepted",
        ts=ts,
    )
    target = event_jsonl_path(repo, ts)
    append_jsonl_line(target, new_event)
    append_jsonl_line(target, op_event)
    write_all(repo)
    return {
        "data": {
            "ir_id": slug,
            "path": f"{target.relative_to(repo).as_posix()}#L<append>",
            "tier": 3,
        },
        "event_id": op_event["event_id"],
        "indexes_updated": [
            "id-to-path",
            "path-to-id",
            "tier-to-ids",
            "resolver-to-events",
            "_checksum",
        ],
    }


def _tier2_category(projection_types: list[str]) -> str:
    """Resolve a tier 2 (I, R)'s on-disk category folder under ir/_ops/.

    Accepts both the v0.2 prefixed names (`_kernel.resolver-selection`,
    `_kernel.authorization`, `_kernel.capability-update`) and the historical
    unprefixed names. Returns the unprefixed folder name.
    """
    for ptype in projection_types:
        if ptype in TIER2_CATEGORIES:
            return ptype
        # Accept _kernel.<category> form as the canonical v0.2/v1.0 spelling.
        if ptype.startswith("_kernel.") and ptype.removeprefix("_kernel.") in TIER2_CATEGORIES:
            return ptype.removeprefix("_kernel.")
    raise KernelError(
        INVALID_STATE,
        f"tier 2 (I, R) requires one of projection_types {list(TIER2_CATEGORIES)!r} "
        f"(or their _kernel.* prefixed equivalents)",
        input_field="projection_types",
        offending_value=projection_types,
        suggested_action=f"add one of {list(TIER2_CATEGORIES)!r}",
    )


def _ensure_ops_scope(repo: Path, author: str, ts: str) -> None:
    """Materialize the `_ops` scope as a `_kernel.scope` (I, R) on first tier 2 write.

    v0.2 keeps the OPEN-Q-005 lazy-materialization decision but the on-disk
    artifact is now a kernel-configuration (I, R) at
    `ir/_kernel/scope/_ops.md` instead of `ir/_ops/_scope.yml`.
    """
    scope_record = kernel_record_path(repo, "scope", OPS_SCOPE)
    if not scope_record.exists():
        ops_record = IRRecord(
            frontmatter={
                "id": OPS_SCOPE,
                "kind": "ir-node",
                "tier": 1,
                "projection_types": ["_kernel.scope"],
                "collapsed_summary": "Scope declaration: Kernel Operations (_ops)",
                "expanded_into": None,
                "parent": None,
                "scope": KERNEL_SCOPE,
                "depends_on": [],
                "visible_to": [KERNEL_SCOPE],
                "resolved_at": ts,
                "valid_through": None,
                "revalidate_trigger": None,
                "status": "resolved",
                "resolver": KERNEL_BINARY_RESOLVER_ID,
                "resolution_event": None,
                "authored_by": author,
                "authored_on": ts,
                "authority_level": "hard",
                "authored_via": "kernel.self",
                "supersedes": None,
                "superseded_by": None,
                "surrogate_of": None,
                "parent_scope": None,
                "authority_defaults": {"hard": [], "convention": [], "uncalibrated": []},
                "visibility_defaults": [OPS_SCOPE],
                "display_name": "Kernel Operations",
            },
            intention_text=(
                "The `_ops` scope holds tier 2 kernel-authored operational records — "
                "resolver-selection, authorization, capability-update — produced as side "
                "effects of kernel ops. Materialized lazily on first tier 2 write per "
                "OPEN-Q-005 (preserved under v0.2 §1.4)."
            ),
            resolution_text=None,
        )
        scope_record.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(scope_record, serialize(ops_record))
    for cat in TIER2_CATEGORIES:
        ops_category_dir(repo, cat).mkdir(parents=True, exist_ok=True)


def _require_scope_exists(repo: Path, scope_id: str) -> None:
    """v0.2: scope existence is the presence of ir/_kernel/scope/<scope-id>.md."""
    if scope_id == OPS_SCOPE:
        return  # _ops materializes lazily via _ensure_ops_scope per OPEN-Q-005
    scope_record = kernel_record_path(repo, "scope", scope_id)
    if not scope_record.exists():
        raise KernelError(
            NOT_FOUND,
            f"scope {scope_id!r} not declared (no {scope_record.relative_to(repo).as_posix()})",
            input_field="scope_id",
            offending_value=scope_id,
            suggested_action="declare the scope via kernel.ir.new with projection_types: [_kernel.scope]",
        )


def _kernel_category_for(projection_types: list[str]) -> str | None:
    """Return the ir/_kernel/<category> for the projection types, or None.

    Raises SCOPE_VIOLATION if multiple projection types map to different
    kernel categories (the (I, R) can't live in two places).
    """
    found: set[str] = set()
    for ptype in projection_types:
        cat = KERNEL_PROJECTION_TO_CATEGORY.get(ptype)
        if cat is not None:
            found.add(cat)
    if not found:
        return None
    if len(found) > 1:
        raise KernelError(
            SCOPE_VIOLATION,
            f"projection_types map to multiple kernel categories: {sorted(found)!r}",
            input_field="projection_types",
        )
    return next(iter(found))


def _child_path_under(repo: Path, parent_relpath: str, child_slug: str) -> Path:
    """Resolve ir/<scope>/<parent>/<child>.md given the parent's current path.

    Parent must be expanded — its on-disk path ends in `/_node.md` — otherwise
    the child can't legally be written under it.
    """
    parent_abs = repo / parent_relpath
    if parent_abs.name != "_node.md":
        raise KernelError(
            INVALID_STATE,
            f"parent (I, R) at {parent_relpath!r} is collapsed; expand it before "
            "adding a child",
            input_field="parent_id",
            suggested_action="run kernel.ir.expand on the parent first",
        )
    return parent_abs.parent / f"{child_slug}.md"


# ---- Read-op visibility (Block 4.4 / v1.1 §4.4) ----------------------------


def _default_caller_context() -> predicates.CallerContext:
    """Build a default empty CallerContext for runtime read-op evaluation.

    Block 4.4 placeholder per discipline (B): the SDK runner does not yet
    surface caller identity / roles / classification context to read ops.
    Predicates referencing roles, scope, or caller identity therefore
    evaluate false at runtime in this binary; tests for composition
    semantics call `predicates.evaluate_predicate(...)` directly with
    fixture-supplied contexts.

    The three placeholders (roles, classification, runtime CallerContext)
    plug in together when the policy / role / classification-ordering work
    lands. See `eightos.predicates` module docstring.
    """
    return predicates.CallerContext()


def _is_visible(fm: dict[str, Any], ctx: predicates.CallerContext) -> bool:
    """True if the record has no `visible_when` or its predicate is true."""
    pred = fm.get("visible_when")
    if pred is None:
        return True
    return predicates.evaluate_predicate(pred, ctx)


# ---- ir.get ----------------------------------------------------------------


def get(payload: dict[str, Any]) -> dict[str, Any]:
    repo = repo_root_or_raise()
    requested_id = payload["ir_id"]
    view = payload.get("view", "collapsed")
    include_body = payload.get("include_body", True)

    id_to_path = _load_index(repo, "id-to-path")
    ir_id = _resolve_id_with_suffix(requested_id, id_to_path)
    if ir_id is None:
        raise KernelError(NOT_FOUND, f"no (I, R) with id {requested_id!r}")
    relpath = id_to_path[ir_id]

    if "#L" in relpath:
        # Tier 3 — read the JSONL line and project to (I, R) frontmatter shape.
        return _get_tier3(repo, ir_id, relpath, include_body)

    record = parse_file(repo / relpath)
    fm = record.frontmatter
    # v1.1 §4.4 (Block 4.4): visibility-predicate evaluation. Default empty
    # CallerContext at runtime per the placeholder discipline.
    if not _is_visible(fm, _default_caller_context()):
        raise KernelError(
            IR_NOT_VISIBLE,
            f"(I, R) {ir_id!r} is not visible to the current caller "
            "(visible_when predicate evaluated false)",
            input_field="ir_id",
            offending_value=ir_id,
        )
    intention_text = record.intention_text if include_body else None
    resolution_text = record.resolution_text if include_body else None

    children: list[dict[str, str]] | None = None
    subgraph: dict[str, Any] | None = None
    if view in ("expanded", "full") and (repo / relpath).name == "_node.md":
        children = _list_children(repo, relpath)
    if view == "full" and children is not None:
        subgraph = {"children": [_subgraph(repo, c["ir_id"]) for c in children]}

    return {
        "data": {
            "ir_id": ir_id,
            "path": relpath,
            "tier": int(fm.get("tier", 1)),
            "frontmatter": fm,
            "intention_text": intention_text,
            "resolution_text": resolution_text,
            "children": children,
            "subgraph": subgraph,
        },
        "event_id": None,
        "indexes_updated": [],
    }


def _get_tier3(repo: Path, ir_id: str, relpath: str, include_body: bool) -> dict[str, Any]:
    """Project a tier 3 event line into the (I, R) get-response shape."""
    found = find_event(repo, ir_id)
    if found is None:
        raise KernelError(NOT_FOUND, f"tier 3 event {ir_id!r} not present in JSONL stream")
    _path, _line, ev = found
    fm = _project_event_to_frontmatter(ev)
    return {
        "data": {
            "ir_id": ir_id,
            "path": relpath,
            "tier": 3,
            "frontmatter": fm,
            "intention_text": (ev.get("intention") or {}).get("text") if include_body else None,
            "resolution_text": (ev.get("resolution") or {}).get("text") if include_body else None,
            "children": None,
            "subgraph": None,
        },
        "event_id": None,
        "indexes_updated": [],
    }


def _list_children(repo: Path, parent_relpath: str) -> list[dict[str, str]]:
    """List child (I, R) records of an expanded parent (`_node.md`)."""
    parent_abs = repo / parent_relpath
    folder = parent_abs.parent
    out: list[dict[str, str]] = []
    for md in sorted(folder.glob("*.md")):
        if md.name == "_node.md":
            continue
        rec = parse_file(md)
        out.append(
            {
                "ir_id": rec.frontmatter["id"],
                "collapsed_summary": rec.frontmatter.get("collapsed_summary", ""),
            }
        )
    return out


def _subgraph(repo: Path, child_id: str) -> dict[str, Any]:
    """Recursively build a subgraph dict for full-view get."""
    id_to_path = _load_index(repo, "id-to-path")
    relpath = id_to_path.get(child_id)
    if relpath is None or "#L" in relpath:
        return {"ir_id": child_id, "children": []}
    rec = parse_file(repo / relpath)
    node = {
        "ir_id": child_id,
        "collapsed_summary": rec.frontmatter.get("collapsed_summary", ""),
        "children": [],
    }
    if (repo / relpath).name == "_node.md":
        for c in _list_children(repo, relpath):
            node["children"].append(_subgraph(repo, c["ir_id"]))
    return node


# ---- ir.list ---------------------------------------------------------------


def list_(payload: dict[str, Any]) -> dict[str, Any]:
    repo = repo_root_or_raise()
    scope_id = payload.get("scope_id")
    tiers = set(payload.get("tier") or [1])
    projection = payload.get("projection_type")
    statuses = set(payload.get("status") or [])
    valid_at = payload.get("valid_at")
    authored_by = payload.get("authored_by")
    authority_levels = set(payload.get("authority_level") or [])
    limit = int(payload.get("limit", 50))
    offset = int(payload.get("offset", 0))
    # v0.2 §4.2: --include-kernel toggles visibility of _kernel-scope records.
    include_kernel = bool(payload.get("include_kernel", False))
    # v1.1 §3.10 (Block 4.6 / BLOCK-4.5-SPEC-AMENDMENTS Appendix A item 7):
    # cancelled records are excluded by default to avoid surprising callers.
    # Explicit `status: ['cancelled']` overrides the gate (caller intent
    # wins per Block 4.6 Q2); when cancelled is in the requested status
    # filter, cancelled records pass regardless of include_cancelled.
    include_cancelled = bool(payload.get("include_cancelled", False))
    cancelled_explicitly_requested = "cancelled" in statuses

    rows: list[dict[str, Any]] = []
    base = ir_dir(repo)
    if base.exists():
        for md in sorted(base.rglob("*.md")):
            rec = parse_file(md)
            fm = rec.frontmatter
            tier = int(fm.get("tier", 1))
            if tier not in tiers:
                continue
            record_scope = fm.get("scope")
            if (
                not include_kernel
                and record_scope == KERNEL_SCOPE
                and scope_id != KERNEL_SCOPE
            ):
                continue
            if scope_id is not None and record_scope != scope_id:
                continue
            if projection is not None and projection not in (fm.get("projection_types") or []):
                continue
            if statuses and fm.get("status") not in statuses:
                continue
            # v1.1 §3.10 include_cancelled gate (Block 4.6): drop cancelled
            # records by default unless either the gate is open OR the
            # caller explicitly named cancelled in the status filter.
            if (
                fm.get("status") == "cancelled"
                and not include_cancelled
                and not cancelled_explicitly_requested
            ):
                continue
            if authored_by is not None and fm.get("authored_by") != authored_by:
                continue
            if authority_levels and fm.get("authority_level") not in authority_levels:
                continue
            if valid_at is not None and not _valid_at(fm, valid_at):
                continue
            # v1.1 §4.4 (Block 4.4): silent-filter records whose
            # visible_when predicate evaluates false. The total count
            # below reflects visible records only — invisible records are
            # treated as not-existent for this caller.
            if not _is_visible(fm, _default_caller_context()):
                continue
            rows.append(
                {
                    "ir_id": fm["id"],
                    "path": str(md.relative_to(repo).as_posix()),
                    "tier": tier,
                    "collapsed_summary": fm.get("collapsed_summary", ""),
                    "status": fm.get("status", "open"),
                }
            )

    if 3 in tiers:
        for jsonl_path, lineno, ev in iter_events(repo):
            if ev.get("event_type") not in ("operation", "resolution", "promotion", "assessment"):
                continue
            ev_id = ev.get("event_id")
            if not ev_id:
                continue
            scope = (ev.get("intention") or {}).get("scope")
            if scope_id is not None and scope != scope_id:
                continue
            if authored_by is not None and ev.get("resolver_id") != authored_by:
                continue
            if statuses and ev.get("outcome") not in statuses and "resolved" not in statuses:
                # tier 3 doesn't carry status; map outcome accepted -> resolved
                if not (ev.get("outcome") == "accepted" and "resolved" in statuses):
                    continue
            rows.append(
                {
                    "ir_id": ev_id,
                    "path": f"{jsonl_path.relative_to(repo).as_posix()}#L{lineno}",
                    "tier": 3,
                    "collapsed_summary": (ev.get("intention") or {}).get("text", "")[:140],
                    "status": "resolved" if ev.get("outcome") == "accepted" else "open",
                }
            )

    rows.sort(key=lambda r: r["ir_id"])
    total = len(rows)
    page = rows[offset : offset + limit]
    return {
        "data": {
            "results": page,
            "total_matching": total,
            "returned": len(page),
        },
        "event_id": None,
        "indexes_updated": [],
    }


def _valid_at(fm: dict[str, Any], at: str) -> bool:
    """A record is valid at `at` if resolved_at <= at and (no valid_through or valid_through > at)."""
    resolved_at = fm.get("resolved_at")
    if resolved_at is not None and resolved_at > at:
        return False
    valid_through = fm.get("valid_through")
    if valid_through is not None and valid_through <= at:
        return False
    return True


# ---- ir.resolve, expand, collapse, promote, supersede, deps ----------------


def resolve(payload: dict[str, Any]) -> dict[str, Any]:
    """ir.resolve — bind a resolution to an open (I, R)."""
    repo = repo_root_or_raise()
    ir_id = payload["ir_id"]
    resolver_id = payload["resolver_id"]
    resolution_text = payload["resolution_text"]
    cost_actual = payload["cost_actual"]
    bridge_id = payload.get("bridge_id")
    valid_through = payload.get("valid_through")
    revalidate_trigger = payload.get("revalidate_trigger")
    # authorization_id reserved for gatekeeper use; not enforced in v0.1

    id_to_path = _load_index(repo, "id-to-path")
    if ir_id not in id_to_path:
        raise KernelError(NOT_FOUND, f"no (I, R) with id {ir_id!r}")
    relpath = id_to_path[ir_id]
    if "#L" in relpath:
        raise KernelError(
            INVALID_STATE,
            "cannot resolve a tier 3 record via ir.resolve (use bridge.cross or ir.promote)",
            input_field="ir_id",
            offending_value=ir_id,
        )
    abspath = repo / relpath
    rec = parse_file(abspath)
    fm = rec.frontmatter
    if fm.get("status") not in ("open", None):
        raise KernelError(
            INVALID_STATE,
            f"(I, R) {ir_id!r} is not open (status={fm.get('status')!r})",
            input_field="ir_id",
        )
    if not kernel_record_path(repo, "resolver", resolver_id).exists():
        raise KernelError(
            NOT_FOUND,
            f"resolver {resolver_id!r} not registered "
            f"(no ir/_kernel/resolver/{resolver_id}.md)",
            input_field="resolver_id",
            offending_value=resolver_id,
        )

    # ---- policy evaluation placeholder (classification-based gating) ------
    # v1.1 §4.2 / §11.7: when `_kernel.policy` and the policy-evaluation
    # phase land (v1.1 §8), this is the plug-in point where a resolve-time
    # policy can gate the resolution by `data_classification`. The field on
    # the existing record is preserved automatically (resolve does not strip
    # frontmatter). CLASSIFICATION_VIOLATION is defined in errors.py for
    # forward-compat; not yet emitted from any path.

    ts = now_iso()
    event = make_event(
        event_type="resolution",
        ir_node_id=ir_id,
        ir_node_path_at_event=relpath,
        resolver_id=resolver_id,
        bridge_id=bridge_id,
        intention={
            "text": rec.intention_text,
            "context_refs": list(fm.get("depends_on") or []),
            "scope": fm.get("scope"),
            "depth": 0,
        },
        resolution={
            "text": resolution_text,
            "structured": {},
            "authority_level": fm.get("authority_level", "uncalibrated"),
        },
        cost_actual=cost_actual,
        outcome="accepted",
        ts=ts,
    )

    fm["status"] = "resolved"
    fm["resolved_at"] = ts
    fm["resolver"] = resolver_id
    fm["resolution_event"] = event["event_id"]
    # v1.0.1-partial Amendment 2: authored_via records the bridge through
    # which the (I, R) was authored, not resolved. Pre-amendment code
    # overwrote authored_via with the resolution-time bridge_id; preserve
    # the authoring bridge instead. Only fill when missing (legacy records
    # not yet migrated).
    if not fm.get("authored_via"):
        fm["authored_via"] = bridge_id or "outside"
    fm["valid_through"] = valid_through
    fm["revalidate_trigger"] = revalidate_trigger
    new_record = IRRecord(
        frontmatter=fm,
        intention_text=rec.intention_text,
        resolution_text=resolution_text,
    )
    commit_staged([StagedFile(abspath, content_text=serialize(new_record))])
    append_jsonl_line(event_jsonl_path(repo, ts), event)
    write_all(repo)

    return {
        "data": {
            "ir_id": ir_id,
            "ir_status": "resolved",
            "resolved_at": ts,
            "valid_through": valid_through,
            "resolution_event_id": event["event_id"],
        },
        "event_id": event["event_id"],
        "indexes_updated": ["temporal", "resolver-to-events", "_checksum"],
    }


def expand(payload: dict[str, Any]) -> dict[str, Any]:
    repo = repo_root_or_raise()
    ir_id = payload["ir_id"]
    id_to_path = _load_index(repo, "id-to-path")
    if ir_id not in id_to_path:
        raise KernelError(NOT_FOUND, f"no (I, R) with id {ir_id!r}")
    old_rel = id_to_path[ir_id]
    old_abs = repo / old_rel
    if old_abs.name == "_node.md":
        raise KernelError(INVALID_STATE, f"(I, R) {ir_id!r} is already expanded")
    if "#L" in old_rel:
        raise KernelError(INVALID_STATE, "cannot expand a tier 3 record")

    slug = old_abs.stem
    new_dir = old_abs.parent / slug
    new_abs = new_dir / "_node.md"
    if new_dir.exists():
        raise KernelError(ALREADY_EXISTS, f"target folder {new_dir.relative_to(repo).as_posix()} already exists")

    new_dir.mkdir(parents=True, exist_ok=False)
    os.replace(old_abs, new_abs)

    rec = parse_file(new_abs)
    rec.frontmatter["expanded_into"] = ir_id  # self-reference signals expansion
    atomic_write_text(new_abs, serialize(rec))

    new_rel = str(new_abs.relative_to(repo).as_posix())
    ts = now_iso()
    op_event = make_event(
        event_type="operation",
        ir_node_id=ir_id,
        ir_node_path_at_event=new_rel,
        resolver_id="kernel",
        bridge_id=None,
        intention={
            "text": f"Expand (I, R) {ir_id!r}.",
            "context_refs": [],
            "scope": rec.frontmatter.get("scope"),
            "depth": 0,
        },
        resolution={
            "text": f"Expanded {old_rel!r} -> {new_rel!r}",
            "structured": {"old_path": old_rel, "new_path": new_rel},
            "authority_level": rec.frontmatter.get("authority_level", "uncalibrated"),
        },
        outcome="accepted",
        ts=ts,
    )
    append_jsonl_line(event_jsonl_path(repo, ts), op_event)
    write_all(repo)
    return {
        "data": {"ir_id": ir_id, "old_path": old_rel, "new_path": new_rel},
        "event_id": op_event["event_id"],
        "indexes_updated": ["id-to-path", "path-to-id", "_checksum"],
    }


def collapse(payload: dict[str, Any]) -> dict[str, Any]:
    repo = repo_root_or_raise()
    ir_id = payload["ir_id"]
    id_to_path = _load_index(repo, "id-to-path")
    if ir_id not in id_to_path:
        raise KernelError(NOT_FOUND, f"no (I, R) with id {ir_id!r}")
    old_rel = id_to_path[ir_id]
    old_abs = repo / old_rel
    if old_abs.name != "_node.md":
        raise KernelError(INVALID_STATE, f"(I, R) {ir_id!r} is not expanded")

    folder = old_abs.parent
    siblings = [p for p in folder.iterdir() if p.name != "_node.md"]
    if siblings:
        raise KernelError(
            INVALID_STATE,
            f"cannot collapse (I, R) {ir_id!r} with non-empty children",
            input_field="ir_id",
            offending_value=ir_id,
            suggested_action="remove or relocate child (I, R)s before collapsing",
        )

    new_abs = folder.parent / f"{folder.name}.md"
    if new_abs.exists():
        raise KernelError(ALREADY_EXISTS, f"target {new_abs.relative_to(repo).as_posix()} occupied")

    rec = parse_file(old_abs)
    rec.frontmatter["expanded_into"] = None
    atomic_write_text(old_abs, serialize(rec))
    os.replace(old_abs, new_abs)
    folder.rmdir()

    new_rel = str(new_abs.relative_to(repo).as_posix())
    ts = now_iso()
    op_event = make_event(
        event_type="operation",
        ir_node_id=ir_id,
        ir_node_path_at_event=new_rel,
        resolver_id="kernel",
        bridge_id=None,
        intention={
            "text": f"Collapse (I, R) {ir_id!r}.",
            "context_refs": [],
            "scope": rec.frontmatter.get("scope"),
            "depth": 0,
        },
        resolution={
            "text": f"Collapsed {old_rel!r} -> {new_rel!r}",
            "structured": {"old_path": old_rel, "new_path": new_rel},
            "authority_level": rec.frontmatter.get("authority_level", "uncalibrated"),
        },
        outcome="accepted",
        ts=ts,
    )
    append_jsonl_line(event_jsonl_path(repo, ts), op_event)
    write_all(repo)
    return {
        "data": {"ir_id": ir_id, "old_path": old_rel, "new_path": new_rel},
        "event_id": op_event["event_id"],
        "indexes_updated": ["id-to-path", "path-to-id", "_checksum"],
    }


def promote(payload: dict[str, Any]) -> dict[str, Any]:
    """Promote a tier 3 event to a tier 1 or tier 2 (I, R) record."""
    repo = repo_root_or_raise()
    event_id = payload["event_id"]
    to_tier = int(payload["to_tier"])
    target_scope = payload["target_scope"]
    target_slug = payload["target_slug"]
    author = payload["authored_by"]
    authority = payload["authority_level"]

    found = find_event(repo, event_id)
    if found is None:
        raise KernelError(NOT_FOUND, f"event {event_id!r} not found in JSONL stream")
    jsonl_path, _line, ev = found

    id_to_path = _load_index(repo, "id-to-path")
    if target_slug in id_to_path:
        raise KernelError(ALREADY_EXISTS, f"target_slug {target_slug!r} already in use")
    if to_tier not in (1, 2):
        raise KernelError(INVALID_STATE, "to_tier must be 1 or 2", input_field="to_tier")

    ts = now_iso()
    intention = (ev.get("intention") or {}).get("text") or "(promoted from event)"
    resolution = (ev.get("resolution") or {}).get("text") or ""
    summary = intention.splitlines()[0][:140] if intention else "(promoted)"

    if to_tier == 1:
        _require_scope_exists(repo, target_scope)
        target_path = ir_collapsed_path(repo, target_scope, target_slug)
        scope_for_record = target_scope
    else:
        category = "resolver-selection"  # promotion target category not specified;
        # default to resolver-selection per common case; user may relocate
        _ensure_ops_scope(repo, author, ts)
        target_path = ops_category_dir(repo, category) / f"{target_slug}.md"
        scope_for_record = OPS_SCOPE

    record = IRRecord(
        frontmatter={
            "id": target_slug,
            "kind": "ir-node",
            "tier": to_tier,
            "projection_types": ["promoted-from-tier3"],
            "collapsed_summary": summary,
            "expanded_into": None,
            "parent": None,
            "scope": scope_for_record,
            "depends_on": [],
            "visible_to": [scope_for_record],
            "resolved_at": ts,
            "valid_through": None,
            "revalidate_trigger": None,
            "status": "resolved",
            "resolver": ev.get("resolver_id") or "kernel",
            "resolution_event": event_id,
            "authored_by": author,
            "authored_on": ts,
            "authority_level": authority,
            # v1.0.1-partial Amendment 2: authored_via mandatory. Derive from
            # the source event's bridge_id; default to `"outside"` when the
            # event carried no bridge (kernel-internal events without a
            # crossing).
            "authored_via": ev.get("bridge_id") or "outside",
            "supersedes": None,
            "superseded_by": None,
            "surrogate_of": None,
        },
        intention_text=intention,
        resolution_text=resolution,
    )

    relpath = str(target_path.relative_to(repo).as_posix())

    # Append the promotion marker on the source JSONL.
    marker = {"event_id": event_id, "promoted_to": target_slug, "promoted_at": ts}
    append_jsonl_line(jsonl_path, marker)

    op_event = make_event(
        event_type="promotion",
        ir_node_id=target_slug,
        ir_node_path_at_event=relpath,
        resolver_id="kernel",
        bridge_id=None,
        intention={
            "text": f"Promote event {event_id!r} to tier {to_tier} (I, R) {target_slug!r}.",
            "context_refs": [event_id],
            "scope": scope_for_record,
            "depth": 0,
        },
        resolution={
            "text": f"Promoted at {ts}",
            "structured": {"new_ir_id": target_slug, "from_event": event_id},
            "authority_level": authority,
        },
        outcome="accepted",
        ts=ts,
    )

    commit_staged([StagedFile(target_path, content_text=serialize(record))])
    append_jsonl_line(event_jsonl_path(repo, ts), op_event)
    write_all(repo)
    return {
        "data": {
            "new_ir_id": target_slug,
            "new_path": relpath,
            "promoted_from_event": event_id,
            "original_jsonl_marked": True,
        },
        "event_id": op_event["event_id"],
        "indexes_updated": [
            "id-to-path",
            "path-to-id",
            "scope-to-ids",
            "tier-to-ids",
            "projection-to-ids",
            "deps-forward",
            "deps-reverse",
            "_checksum",
        ],
    }


def supersede(payload: dict[str, Any]) -> dict[str, Any]:
    repo = repo_root_or_raise()
    old_id = payload["old_ir_id"]
    new_intention = payload["new_intention_text"]
    author = payload["authored_by"]
    reason = payload["reason"]

    id_to_path = _load_index(repo, "id-to-path")
    if old_id not in id_to_path:
        raise KernelError(NOT_FOUND, f"no (I, R) with id {old_id!r}")
    old_rel = id_to_path[old_id]
    if "#L" in old_rel:
        raise KernelError(INVALID_STATE, "cannot supersede a tier 3 record directly")
    old_abs = repo / old_rel
    old_rec = parse_file(old_abs)
    if old_rec.frontmatter.get("status") == "superseded":
        raise KernelError(INVALID_STATE, f"(I, R) {old_id!r} is already superseded")

    ts = now_iso()
    new_id = f"{old_id}.s{int(_count_supersessions(repo, old_id)) + 1}"
    if new_id in id_to_path:
        # extremely unlikely collision with an existing slug
        new_id = f"{old_id}.s{ts}"

    if old_abs.name == "_node.md":
        new_abs = old_abs.parent.parent / f"{new_id}.md"
    else:
        new_abs = old_abs.parent / f"{new_id}.md"

    new_fm = dict(old_rec.frontmatter)
    new_fm["id"] = new_id
    new_fm["status"] = "open"
    new_fm["supersedes"] = old_id
    new_fm["superseded_by"] = None
    new_fm["resolver"] = None
    new_fm["resolution_event"] = None
    new_fm["resolved_at"] = None
    new_fm["valid_through"] = None
    new_fm["authored_by"] = author
    new_fm["authored_on"] = ts
    new_record = IRRecord(
        frontmatter=new_fm,
        intention_text=new_intention,
        resolution_text=None,
    )

    old_rec.frontmatter["status"] = "superseded"
    old_rec.frontmatter["superseded_by"] = new_id

    op_event = make_event(
        event_type="operation",
        ir_node_id=new_id,
        ir_node_path_at_event=str(new_abs.relative_to(repo).as_posix()),
        resolver_id="kernel",
        bridge_id=None,
        intention={
            "text": f"Supersede {old_id!r} with {new_id!r}: {reason}",
            "context_refs": [old_id],
            "scope": old_rec.frontmatter.get("scope"),
            "depth": 0,
        },
        resolution={
            "text": f"Superseded at {ts}",
            "structured": {"old_ir_id": old_id, "new_ir_id": new_id, "reason": reason},
            "authority_level": old_rec.frontmatter.get("authority_level", "convention"),
        },
        outcome="accepted",
        ts=ts,
    )

    commit_staged(
        [
            StagedFile(old_abs, content_text=serialize(old_rec)),
            StagedFile(new_abs, content_text=serialize(new_record)),
        ]
    )
    append_jsonl_line(event_jsonl_path(repo, ts), op_event)
    write_all(repo)

    # v1.1 §8.5 (Block 4.7 Q-CACHE): when a `_kernel.policy` record is
    # superseded, walk the policy-evaluations cache and expire any
    # evaluations that consulted the superseded policy. Eager invalidation
    # so subsequent ops re-evaluate against the new policy. The cache
    # records stay on disk for audit; only `valid_through` is rewritten.
    if "_kernel.policy" in (old_rec.frontmatter.get("projection_types") or []):
        from .. import op_pipeline as _pipeline
        _pipeline.invalidate_cache_for_policy(repo, old_id)
        write_all(repo)

    return {
        "data": {
            "old_ir_id": old_id,
            "new_ir_id": new_id,
            "new_path": str(new_abs.relative_to(repo).as_posix()),
        },
        "event_id": op_event["event_id"],
        "indexes_updated": [
            "id-to-path",
            "path-to-id",
            "scope-to-ids",
            "tier-to-ids",
            "projection-to-ids",
            "deps-forward",
            "deps-reverse",
            "_checksum",
        ],
    }


# ---- ir.cancel (Block 4.2 / v1.1 §3.8) ------------------------------------

# Authority hierarchy per v1.1: hard > convention > uncalibrated.
_AUTHORITY_RANK = {"uncalibrated": 0, "convention": 1, "hard": 2}


def _bridge_authority_level(repo: Path, authored_via: str) -> str:
    """Resolve the authority_level conveyed by `authored_via`.

    `"outside"` (the v1.0.1-partial Amendment 2 default for non-internal
    SDK callers) maps to `uncalibrated` — the floor authority. Other
    bridge ids resolve via their `_kernel.bridge` (I, R) record. Unknown
    bridges fail closed by raising NOT_FOUND.
    """
    if authored_via == "outside":
        return "uncalibrated"
    bridge_path = kernel_record_path(repo, "bridge", authored_via)
    if not bridge_path.exists():
        raise KernelError(
            NOT_FOUND,
            f"bridge {authored_via!r} (referenced via authored_via) is not registered",
            input_field="authored_via",
            offending_value=authored_via,
        )
    bridge_rec = parse_file(bridge_path)
    return bridge_rec.frontmatter.get("authority_level", "uncalibrated")


def cancel(payload: dict[str, Any]) -> dict[str, Any]:
    """v1.1 §3.8 — Mark an (I, R) `status: cancelled` and cascade to dependents.

    Cancellation is terminal. The transition (target frontmatter mutation +
    cascade staling of one-hop dependents + tier 3 cancellation event) is
    a single atomic commit.

    Spec contradiction note: v1.1 §18.1 describes IR_NOT_CANCELLABLE as
    rejecting `superseded` OR `stale` targets, but v1.1 §5.2's transition
    table permits stale → cancelled. This implementation follows §5.2 as
    binding (the more recent and explicit statement of permitted
    transitions); only `superseded` is rejected. See block-4.2 report.
    """
    repo = repo_root_or_raise()
    ir_id = payload["ir_id"]
    cancelled_by = payload["cancelled_by"]
    reason = payload.get("reason")
    cascade_flag = payload.get("cascade", True)
    authored_via = payload["authored_via"]
    authorization_id = payload.get("authorization_id")

    # ---- 1. Lookup target ------------------------------------------------
    id_to_path = _load_index(repo, "id-to-path")
    if ir_id not in id_to_path:
        raise KernelError(
            NOT_FOUND,
            f"no (I, R) with id {ir_id!r}",
            input_field="ir_id",
            offending_value=ir_id,
        )
    rel = id_to_path[ir_id]
    if "#L" in rel:
        raise KernelError(
            INVALID_STATE,
            f"cannot cancel a tier 3 record directly ({ir_id!r})",
            input_field="ir_id",
            offending_value=ir_id,
        )
    abs_path = repo / rel
    rec = parse_file(abs_path)
    current_status = rec.frontmatter.get("status")

    # ---- 2. Status check -------------------------------------------------
    if current_status == "cancelled":
        raise KernelError(
            IR_ALREADY_CANCELLED,
            f"(I, R) {ir_id!r} is already cancelled; cancellation is terminal",
            input_field="ir_id",
            offending_value=ir_id,
        )
    if current_status == "superseded":
        # Per v1.1 §5.2: superseded → anything is forbidden (terminal).
        # The §18.1 error description names `stale` as also non-cancellable,
        # but §5.2's transition table explicitly permits stale → cancelled.
        # §5.2 wins — see block-4.2 report.
        raise KernelError(
            IR_NOT_CANCELLABLE,
            f"(I, R) {ir_id!r} is superseded; supersession chain is forward-only "
            "(per v1.1 §5.2). Supersede again or accept the chain.",
            input_field="ir_id",
            offending_value=ir_id,
            suggested_action="cancellation of superseded records is forbidden by §5.2",
        )

    # ---- 3. Authority check (v1.1 §3.8 — caller authority ≥ target) ------
    target_authority = rec.frontmatter.get("authority_level", "uncalibrated")
    caller_authority = _bridge_authority_level(repo, authored_via)
    if _AUTHORITY_RANK.get(caller_authority, 0) < _AUTHORITY_RANK.get(target_authority, 0):
        raise KernelError(
            CANCELLATION_AUTHORITY_INSUFFICIENT,
            f"caller authority {caller_authority!r} (via {authored_via!r}) is below "
            f"target authority {target_authority!r}",
            input_field="authored_via",
            offending_value=authored_via,
            suggested_action=(
                "re-author the cancel through a bridge whose authority_level meets "
                "or exceeds the target's"
            ),
        )

    # ---- 4. Lease check — slot exists, no-op until Block 4.8 -------------
    # v1.1 §3.8 specifies LEASE_HELD rejection by default when the target
    # is under a held lease. Block 4.7 wired the lease-check phase into
    # the unified pipeline (`op_pipeline.evaluate_op_pre_commit`) but
    # `_kernel.lease` itself is not implemented; the phase is structurally
    # a no-op until Block 4.8 ships the projection type.

    # ---- 5. Policy evaluation phase (v1.1 §8.6, Block 4.7) ---------------
    # Closes Block 4.2's policy-evaluation placeholder. Reads applicable
    # `_kernel.policy` records, evaluates conditions against the populated
    # CallerContext (caller_id from authored_by, caller_roles from
    # `_kernel.role` lookups, caller_authority_level from the bridge),
    # writes a `_kernel.policy-evaluation` cache record, raises on deny
    # or defer-without-authorization-override.
    from .. import op_pipeline as _pipeline

    caller_context = _pipeline.build_caller_context(
        repo,
        authored_via,
        {"authored_by": cancelled_by, "scope_id": rec.frontmatter.get("scope")},
    )
    _pipeline.evaluate_op_pre_commit(
        repo,
        "kernel.ir.cancel",
        {
            "ir_id": ir_id,
            "cancelled_by": cancelled_by,
            "scope_id": rec.frontmatter.get("scope"),
            "data_classification": rec.frontmatter.get("data_classification"),
        },
        caller_context,
        authorization_id=authorization_id,
    )

    ts = now_iso()
    cancelled_scope = rec.frontmatter.get("scope")

    # ---- 6. Status transition on target ---------------------------------
    rec.frontmatter["status"] = "cancelled"
    rec.frontmatter["cancelled_at"] = ts
    rec.frontmatter["cancelled_by"] = cancelled_by
    rec.frontmatter["cancelled_reason"] = reason

    staged: list[StagedFile] = [StagedFile(abs_path, content_text=serialize(rec))]

    # ---- 7. Cascade — one hop, scope-bounded, skip-no-emit on stale/cancelled
    affected_dependents = 0
    if cascade_flag:
        deps_reverse = _load_index(repo, "deps-reverse")
        for dep_id in deps_reverse.get(ir_id) or []:
            if dep_id not in id_to_path:
                continue
            dep_rel = id_to_path[dep_id]
            if "#L" in dep_rel:
                # tier 3 events are immutable; cascade does not touch them
                continue
            dep_abs = repo / dep_rel
            dep_rec = parse_file(dep_abs)
            dep_status = dep_rec.frontmatter.get("status")
            # Skip already-stale or already-cancelled dependents silently
            # (no status mutation, no event). Audit-completeness alternative
            # is OPEN-Q-032 (deferred).
            if dep_status in ("stale", "cancelled"):
                continue
            # Scope visibility (axiom 3): dependent's `visible_to` must
            # include the cancelled record's scope for the cascade to
            # reach it.
            dep_visible_to = dep_rec.frontmatter.get("visible_to") or []
            if cancelled_scope not in dep_visible_to:
                continue
            dep_rec.frontmatter["status"] = "stale"
            dep_rec.frontmatter["staled_at"] = ts
            dep_rec.frontmatter["staled_by"] = "kernel.self"
            dep_rec.frontmatter["staled_reason"] = (
                f"cascade from cancellation of {ir_id!r}"
            )
            staged.append(StagedFile(dep_abs, content_text=serialize(dep_rec)))
            affected_dependents += 1

    # ---- 8. Pending op drop — Block 4.2 placeholder ----------------------
    # v1.1 §3.8 specifies dropping queued outside-call ops against the
    # cancelled (I, R) with IR_CANCELLED. The new `kernel.outside.http`
    # primitive (v1.1 §11) is the queue source; it is not yet implemented
    # in this binary. The existing `kernel.bridge.cross` is synchronous
    # (no queue), so there is nothing to drop here today. When
    # kernel.outside.http lands, this is the plug-in point: query the
    # queue for pending ops referencing `ir_id`, drop each with
    # IR_CANCELLED, increment `dropped_pending_ops`, and emit one tier 3
    # event per drop. For now, the count is structurally zero.
    dropped_pending_ops = 0

    # ---- 9. Tier 3 cancellation event -----------------------------------
    op_event = make_event(
        event_type="operation",
        ir_node_id=ir_id,
        ir_node_path_at_event=str(abs_path.relative_to(repo).as_posix()),
        resolver_id="kernel",
        bridge_id=authored_via if authored_via != "outside" else None,
        intention={
            "text": (
                f"Cancel (I, R) {ir_id!r}" + (f": {reason}" if reason else "")
            ),
            "context_refs": [ir_id],
            "scope": cancelled_scope,
            "depth": 0,
        },
        resolution={
            "text": f"Cancelled at {ts}",
            "structured": {
                "ir_id": ir_id,
                "cancelled_by": cancelled_by,
                "reason": reason,
                "cascade": cascade_flag,
                "affected_dependents": affected_dependents,
                "dropped_pending_ops": dropped_pending_ops,
            },
            "authority_level": caller_authority,
        },
        outcome="accepted",
        ts=ts,
    )

    commit_staged(staged)
    append_jsonl_line(event_jsonl_path(repo, ts), op_event)
    write_all(repo)
    return {
        "data": {
            "ir_id": ir_id,
            "ir_status_after": "cancelled",
            "affected_dependents": affected_dependents,
            "dropped_pending_ops": dropped_pending_ops,
            "cancellation_event_id": op_event["event_id"],
        },
        "event_id": op_event["event_id"],
        "indexes_updated": [
            "id-to-path",
            "path-to-id",
            "scope-to-ids",
            "tier-to-ids",
            "projection-to-ids",
            "temporal",
            "deps-forward",
            "deps-reverse",
            "_checksum",
        ],
    }


def deps(payload: dict[str, Any]) -> dict[str, Any]:
    repo = repo_root_or_raise()
    ir_id = payload["ir_id"]
    direction = payload.get("direction", "forward")
    max_depth = int(payload.get("max_depth", 5))
    tier_filter = set(payload.get("tier_filter") or [])

    id_to_path = _load_index(repo, "id-to-path")
    if ir_id not in id_to_path:
        raise KernelError(NOT_FOUND, f"no (I, R) with id {ir_id!r}")

    forward = _load_index(repo, "deps-forward")
    reverse = _load_index(repo, "deps-reverse")

    def neighbors(node: str, dirn: str) -> list[str]:
        out: list[str] = []
        if dirn in ("forward", "both"):
            out.extend(forward.get(node, []) or [])
        if dirn in ("reverse", "both"):
            out.extend(reverse.get(node, []) or [])
        return out

    visited: dict[str, dict[str, Any]] = {}
    truncated = False
    frontier = [(ir_id, 0, [])]
    depth_reached = 0
    ctx = _default_caller_context()
    while frontier:
        node, depth, via = frontier.pop(0)
        if depth > max_depth:
            truncated = True
            continue
        if node in visited:
            continue
        depth_reached = max(depth_reached, depth)
        if tier_filter:
            tier = _tier_of(repo, node, id_to_path)
            if tier is not None and tier not in tier_filter:
                continue
        # v1.1 §4.4 (Block 4.4): terminate the closure walk at invisible
        # nodes. The invisible record is not surfaced AND its children are
        # not enumerated — visibility-blocked nodes terminate this branch.
        # Per spec: "invisible (I, R)s are not surfaced in transitive
        # closures even when on the dependency path."
        node_rel = id_to_path.get(node)
        if node_rel and "#L" not in node_rel:
            try:
                node_rec = parse_file(repo / node_rel)
            except Exception:
                node_rec = None
            if node_rec is not None and not _is_visible(node_rec.frontmatter, ctx):
                continue
        visited[node] = {"ir_id": node, "depth": depth, "via": via}
        for n in neighbors(node, direction):
            frontier.append((n, depth + 1, via + [node]))

    graph = sorted(visited.values(), key=lambda r: (r["depth"], r["ir_id"]))
    return {
        "data": {
            "ir_id": ir_id,
            "direction": direction,
            "depth_reached": depth_reached,
            "graph": graph,
            "truncated": truncated,
        },
        "event_id": None,
        "indexes_updated": [],
    }


# ---- shared helpers --------------------------------------------------------


def _load_index(repo: Path, name: str) -> dict[str, Any]:
    path = repo / ".8os" / "index" / f"{name}.yml"
    if not path.exists():
        return {}
    return load_yaml_file(path) or {}


def _project_event_to_frontmatter(ev: dict[str, Any]) -> dict[str, Any]:
    """Render a tier 3 event line in (I, R) frontmatter shape (Block 1 §1.4 / §5)."""
    return {
        "id": ev.get("event_id"),
        "kind": "ir-node",
        "tier": 3,
        "projection_types": ["tier3-event"],
        "collapsed_summary": (ev.get("intention") or {}).get("text", "")[:140],
        "expanded_into": None,
        "parent": None,
        "scope": (ev.get("intention") or {}).get("scope"),
        "depends_on": list((ev.get("intention") or {}).get("context_refs") or []),
        "visible_to": [(ev.get("intention") or {}).get("scope")] if (ev.get("intention") or {}).get("scope") else [],
        "resolved_at": ev.get("ts"),
        "valid_through": None,
        "revalidate_trigger": None,
        "status": "resolved" if ev.get("outcome") == "accepted" else "open",
        "resolver": ev.get("resolver_id"),
        "resolution_event": ev.get("event_id"),
        "authored_by": ev.get("resolver_id"),
        "authored_on": ev.get("ts"),
        "authority_level": (ev.get("resolution") or {}).get("authority_level", "uncalibrated"),
        "authored_via": ev.get("bridge_id"),
        "supersedes": ev.get("supersedes_event"),
        "superseded_by": None,
        "surrogate_of": None,
    }


def _count_supersessions(repo: Path, ir_id: str) -> int:
    """Count how many supersession-derived siblings already exist for ir_id."""
    id_to_path = _load_index(repo, "id-to-path")
    return sum(1 for k in id_to_path if k.startswith(f"{ir_id}.s"))


def _tier_of(repo: Path, ir_id: str, id_to_path: dict[str, str]) -> int | None:
    relpath = id_to_path.get(ir_id)
    if relpath is None:
        return None
    if "#L" in relpath:
        return 3
    try:
        rec = parse_file(repo / relpath)
        return int(rec.frontmatter.get("tier", 1))
    except Exception:
        return None


def _first_line(text: str) -> str:
    """Default collapsed_summary: the first non-empty line of intention_text, ≤140 chars."""
    for ln in text.splitlines():
        ln = ln.strip()
        if ln:
            return ln[:140]
    return text[:140]


def _resolve_id_with_suffix(
    requested: str, id_to_path: dict[str, str]
) -> str | None:
    """v0.2 §4.3: ir.get accepts both `<slug>` and `<slug>.<suffix>` forms.

    Direct hit wins. If not found and the requested string contains a `.`,
    strip the suffix and check again — supports `expense-approval.prism`
    resolving to id `expense-approval` (suffix from PRISM-IR projection).
    """
    if requested in id_to_path:
        return requested
    if "." in requested:
        bare = requested.rsplit(".", 1)[0]
        if bare in id_to_path:
            return bare
    return None
