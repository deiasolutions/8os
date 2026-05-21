"""Helpers shared across SDK operations.

The standard mutating-op execution sequence (Block 1 §7.5) lives here.
Handlers compose `mutating_op` to get input validation → state read → stage
writes → atomic commit → tier 3 event append → index regen → output
validation, without each op re-implementing the protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .._atomic import StagedFile, append_jsonl_line, commit_staged
from .._events import write_event
from .._indexes import INDEX_NAMES, write_all
from .._paths import event_jsonl_path, find_repo_root


@dataclass
class CommitPlan:
    """A planned multi-file mutation. Returned by an op's `plan()` step.

    `staged_files` are written atomically. `tier3_event` is appended after the
    staged files settle. `regenerate_indexes` controls whether the index
    pipeline runs (it always does for mutating ops other than reindex itself).
    `data` is the op's success-envelope `data` dict. `indexes_updated` is the
    list of index file basenames the op claims to have updated.
    """

    data: dict[str, Any]
    staged_files: list[StagedFile] = field(default_factory=list)
    tier3_event: dict[str, Any] | None = None
    regenerate_indexes: bool = True
    indexes_updated: list[str] = field(default_factory=lambda: list(INDEX_NAMES))


def commit(repo_root: Path, plan: CommitPlan) -> dict[str, Any]:
    """Apply a CommitPlan: write files, append event, regenerate indexes.

    Returns the handler-shape dict consumed by `_runner.run`.
    """
    if plan.staged_files:
        commit_staged(plan.staged_files)

    event_id: str | None = None
    if plan.tier3_event is not None:
        target = event_jsonl_path(repo_root, plan.tier3_event["ts"])
        append_jsonl_line(target, plan.tier3_event)
        event_id = plan.tier3_event["event_id"]

    if plan.regenerate_indexes:
        write_all(repo_root)

    return {
        "data": plan.data,
        "event_id": event_id,
        "indexes_updated": plan.indexes_updated,
    }


def repo_root_or_raise() -> Path:
    return find_repo_root()


__all__ = [
    "CommitPlan",
    "commit",
    "repo_root_or_raise",
    "StagedFile",
    "write_event",
]
