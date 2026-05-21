"""kernel.gatekeeper.check — read-only authorization gate (Block 1 §7.6.13)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .._frontmatter import parse_file
from .._paths import kernel_record_path, ops_category_dir
from .._time import now_iso
from ..errors import NOT_FOUND, KernelError
from ._common import repo_root_or_raise


def run(payload: dict[str, Any]) -> dict[str, Any]:
    repo = repo_root_or_raise()
    bid = payload["bridge_id"]
    rid = payload["resolver_id"]
    for_ir = payload["for_ir_id"]
    auth_id = payload.get("authorization_id")

    bridge_path = kernel_record_path(repo, "bridge", bid)
    if not bridge_path.exists():
        raise KernelError(NOT_FOUND, f"bridge {bid!r} not registered")
    resolver_path = kernel_record_path(repo, "resolver", rid)
    if not resolver_path.exists():
        raise KernelError(NOT_FOUND, f"resolver {rid!r} not registered")
    bridge_fm = parse_file(bridge_path).frontmatter

    if not bridge_fm.get("requires_authorization", False):
        return {
            "data": {
                "permitted": True,
                "reason": "bridge does not require authorization",
                "authorization_used": None,
                "valid_through": None,
            },
            "event_id": None,
            "indexes_updated": [],
        }

    if auth_id is not None:
        auth = _find_auth_record(repo, auth_id)
        if auth is None:
            return _denied(f"authorization {auth_id!r} not found")
        ok, reason, vt = _auth_valid_for(auth, bid, for_ir)
        if not ok:
            return _denied(reason)
        return {
            "data": {
                "permitted": True,
                "reason": reason,
                "authorization_used": auth_id,
                "valid_through": vt,
            },
            "event_id": None,
            "indexes_updated": [],
        }

    # No auth supplied: scan ops/authorization/ for any valid record matching.
    auth = _find_matching_auth(repo, bid, for_ir)
    if auth is None:
        return _denied("no valid authorization on file")
    ok, reason, vt = _auth_valid_for(auth, bid, for_ir)
    if not ok:
        return _denied(reason)
    return {
        "data": {
            "permitted": True,
            "reason": reason,
            "authorization_used": auth["id"],
            "valid_through": vt,
        },
        "event_id": None,
        "indexes_updated": [],
    }


def _denied(reason: str) -> dict[str, Any]:
    return {
        "data": {
            "permitted": False,
            "reason": reason,
            "authorization_used": None,
            "valid_through": None,
        },
        "event_id": None,
        "indexes_updated": [],
    }


def _find_auth_record(repo: Path, auth_id: str) -> dict[str, Any] | None:
    folder = ops_category_dir(repo, "authorization")
    if not folder.exists():
        return None
    for md in folder.glob("*.md"):
        rec = parse_file(md)
        if rec.frontmatter.get("id") == auth_id:
            return rec.frontmatter
    return None


def _find_matching_auth(repo: Path, bid: str, for_ir: str) -> dict[str, Any] | None:
    folder = ops_category_dir(repo, "authorization")
    if not folder.exists():
        return None
    candidates: list[dict[str, Any]] = []
    for md in folder.glob("*.md"):
        fm = parse_file(md).frontmatter
        a = fm.get("authorizes") or {}
        if a.get("bridge") != bid:
            continue
        if a.get("for_ir") not in (None, for_ir):
            continue
        candidates.append(fm)
    if not candidates:
        return None
    # Pick the most recently authored.
    return max(candidates, key=lambda fm: fm.get("authored_on", ""))


def _auth_valid_for(auth_fm: dict[str, Any], bid: str, for_ir: str) -> tuple[bool, str, str | None]:
    a = auth_fm.get("authorizes") or {}
    if a.get("bridge") != bid:
        return False, f"authorization is for bridge {a.get('bridge')!r}, not {bid!r}", None
    if a.get("for_ir") not in (None, for_ir):
        return False, f"authorization scoped to (I, R) {a.get('for_ir')!r}", None
    vt = auth_fm.get("valid_through")
    if vt is not None and vt < now_iso():
        return False, "authorization expired", vt
    return True, "valid authorization on file", vt
