"""kernel.authorize — issue a bridge-crossing authorization (Block 1 §7.6.12)."""

from __future__ import annotations

from typing import Any

from .._atomic import StagedFile, append_jsonl_line, commit_staged
from .._events import make_event
from .._frontmatter import IRRecord, serialize
from .._indexes import write_all
from .._paths import event_jsonl_path, kernel_record_path, ops_category_dir
from .._time import now_iso
from ..errors import NOT_FOUND, KernelError
from ._common import repo_root_or_raise
from .ir_ops import _ensure_ops_scope


def run(payload: dict[str, Any]) -> dict[str, Any]:
    repo = repo_root_or_raise()
    bid = payload["bridge_id"]
    for_ir = payload.get("for_ir_id")
    scope_of_authority = payload["scope_of_authority"]
    valid_through = payload.get("valid_through")
    cost_ceiling = payload.get("cost_ceiling")
    author = payload["authored_by"]

    if not kernel_record_path(repo, "bridge", bid).exists():
        raise KernelError(NOT_FOUND, f"bridge {bid!r} not registered")

    ts = now_iso()
    _ensure_ops_scope(repo, author, ts)
    auth_id = f"auth-{int(_now_ms())}"
    target = ops_category_dir(repo, "authorization") / f"{auth_id}.md"

    record = IRRecord(
        frontmatter={
            "id": auth_id,
            "kind": "ir-node",
            "tier": 2,
            "projection_types": ["_kernel.authorization"],
            "collapsed_summary": f"Authorize {bid!r} ({scope_of_authority})",
            "expanded_into": None,
            "parent": None,
            "scope": "_ops",
            "depends_on": [for_ir] if for_ir else [],
            "visible_to": ["_ops"],
            "resolved_at": ts,
            "valid_through": valid_through,
            "revalidate_trigger": None,
            "status": "resolved",
            "resolver": "kernel",
            "resolution_event": None,
            "authored_by": author,
            "authored_on": ts,
            "authority_level": "convention",
            "authored_via": bid,
            "supersedes": None,
            "superseded_by": None,
            "surrogate_of": None,
            "authorizes": {
                "bridge": bid,
                "for_ir": for_ir,
                "scope_of_authority": scope_of_authority,
                "cost_ceiling": cost_ceiling,
            },
        },
        intention_text=f"Authorize bridge {bid!r} crossing for (I, R) {for_ir!r}.",
        resolution_text=f"Authorization issued at {ts}.",
    )

    op_event = make_event(
        event_type="operation",
        ir_node_id=auth_id,
        ir_node_path_at_event=str(target.relative_to(repo)),
        resolver_id="kernel",
        bridge_id=bid,
        intention={
            "text": f"Issue authorization {auth_id!r} for bridge {bid!r}.",
            "context_refs": [for_ir] if for_ir else [],
            "scope": "_ops",
            "depth": 0,
        },
        resolution={
            "text": f"Authorized at {ts}",
            "structured": {
                "authorization_id": auth_id,
                "bridge_id": bid,
                "for_ir": for_ir,
                "scope_of_authority": scope_of_authority,
                "valid_through": valid_through,
                "cost_ceiling": cost_ceiling,
            },
            "authority_level": "convention",
        },
        outcome="accepted",
        ts=ts,
    )
    commit_staged([StagedFile(target, content_text=serialize(record))])
    append_jsonl_line(event_jsonl_path(repo, ts), op_event)
    write_all(repo)
    return {
        "data": {
            "authorization_ir_id": auth_id,
            "path": str(target.relative_to(repo)),
            "valid_through": valid_through,
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


def _now_ms() -> float:
    import time

    return time.time() * 1000
