"""kernel.event.get — fetch a tier 3 event by id (Block 1 §7.6.18)."""

from __future__ import annotations

import json
from typing import Any

from .._events import find_event
from .._paths import event_raw_path
from ..errors import NOT_FOUND, KernelError
from ._common import repo_root_or_raise
from .ir_ops import _project_event_to_frontmatter


def get(payload: dict[str, Any]) -> dict[str, Any]:
    repo = repo_root_or_raise()
    event_id = payload["event_id"]
    include_raw = bool(payload.get("include_raw_payload", False))

    found = find_event(repo, event_id)
    if found is None:
        raise KernelError(NOT_FOUND, f"event {event_id!r} not found")
    _path, _line, ev = found

    raw_payload: Any = None
    raw_ref = ev.get("raw_payload_ref")
    if include_raw and raw_ref:
        rp_path = event_raw_path(repo, event_id)
        if rp_path.exists():
            raw_payload = json.loads(rp_path.read_text(encoding="utf-8"))

    promoted_to: str | None = None
    # A second JSONL line `{event_id, promoted_to, promoted_at}` may follow
    # the original; scan once more to find it.
    for _p, _l, line in _scan_promotion_markers(repo, event_id):
        promoted_to = line.get("promoted_to")
        break

    return {
        "data": {
            "event_id": event_id,
            "event_record": ev,
            "raw_payload": raw_payload,
            "promoted_to_ir_id": promoted_to,
            "ir_projection": _project_event_to_frontmatter(ev),
        },
        "event_id": None,
        "indexes_updated": [],
    }


def _scan_promotion_markers(repo, event_id: str):
    from .._events import iter_events

    for path, lineno, ev in iter_events(repo):
        if ev.get("event_id") == event_id and "promoted_to" in ev:
            yield path, lineno, ev
