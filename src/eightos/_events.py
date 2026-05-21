"""Tier 3 event writing and reading.

A tier 3 event is one JSON object per line in
`.8os/events/YYYY/MM/DD/events.jsonl`. The schema is Block 1 §5.

`write_event` is the only sanctioned writer. It returns the event_id so the
calling op can include it in the success envelope and reference it from any
(I, R) record being authored.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from ._atomic import append_jsonl_line
from ._paths import event_jsonl_path, event_raw_path
from ._time import now_iso
from ._ulid import new_ulid


def make_event(
    *,
    event_type: str,
    ir_node_id: str,
    ir_node_path_at_event: str,
    resolver_id: str,
    bridge_id: str | None,
    intention: dict[str, Any],
    resolution: dict[str, Any] | None,
    cost_actual: dict[str, Any] | None = None,
    capability_assessment: dict[str, Any] | None = None,
    supersedes_event: str | None = None,
    outcome: str = "accepted",
    raw_payload_ref: str | None = None,
    event_id: str | None = None,
    ts: str | None = None,
    escalation_purpose: str | None = None,
    voi_consultation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct an event dict matching Block 1 §5 — does not write it.

    v1.0 §6.2 / §6.3 add two optional fields:
      - `escalation_purpose`: one of `decision | holdout | none`. Absent on
        v0.2-format events; absence treated as `none` for backward compat.
      - `voi_consultation`: present on `kernel.selector.select` events when
        VOI was consulted. Absent when no calibration policy was active.
    """
    event: dict[str, Any] = {
        "event_id": event_id or new_ulid(),
        "event_type": event_type,
        "ts": ts or now_iso(),
        "ir_node_id": ir_node_id,
        "ir_node_path_at_event": ir_node_path_at_event,
        "resolver_id": resolver_id,
        "bridge_id": bridge_id,
        "intention": intention,
        "resolution": resolution,
        "cost_actual": cost_actual or _zero_cost(),
        "capability_assessment": capability_assessment,
        "supersedes_event": supersedes_event,
        "outcome": outcome,
        "raw_payload_ref": raw_payload_ref,
    }
    if escalation_purpose is not None:
        event["escalation_purpose"] = escalation_purpose
    if voi_consultation is not None:
        event["voi_consultation"] = voi_consultation
    return event


def _zero_cost() -> dict[str, Any]:
    return {
        "clock_ms": 0,
        "coin_usd": 0,
        "carbon_g": 0,
        "model_name": None,
        "tokens_in": None,
        "tokens_out": None,
    }


def write_event(repo_root: Path, event: dict[str, Any]) -> Path:
    """Append `event` to its date-bucketed JSONL. Returns the JSONL path."""
    target = event_jsonl_path(repo_root, event["ts"])
    append_jsonl_line(target, event)
    return target


def write_raw_payload(repo_root: Path, event_id: str, payload: Any) -> Path:
    """Persist a large opaque payload at .8os/events/raw/<event-id>.json."""
    path = event_raw_path(repo_root, event_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def iter_events(repo_root: Path) -> Iterable[tuple[Path, int, dict[str, Any]]]:
    """Yield (jsonl_path, line_number, event_dict) for every tier 3 event.

    Walks `.8os/events/YYYY/MM/DD/*.jsonl` in deterministic order so that
    callers (indexer, surrogate trainer, audit) get reproducible iteration.
    """
    from ._paths import events_dir

    root = events_dir(repo_root)
    if not root.exists():
        return
    for year in sorted(p for p in root.iterdir() if p.is_dir() and p.name.isdigit()):
        for month in sorted(p for p in year.iterdir() if p.is_dir()):
            for day in sorted(p for p in month.iterdir() if p.is_dir()):
                for jsonl in sorted(day.glob("*.jsonl")):
                    with open(jsonl, encoding="utf-8") as f:
                        for i, line in enumerate(f, start=1):
                            line = line.strip()
                            if not line:
                                continue
                            yield jsonl, i, json.loads(line)


def find_event(repo_root: Path, event_id: str) -> tuple[Path, int, dict[str, Any]] | None:
    """Linear scan of tier 3 events for `event_id`. Returns first hit or None.

    For v0.1 this is acceptable; surrogate training and event.get are the
    only readers and both are infrequent. A future block can add an
    event-id index if scan cost becomes a real problem.
    """
    for path, lineno, ev in iter_events(repo_root):
        if ev.get("event_id") == event_id:
            return path, lineno, ev
    return None
