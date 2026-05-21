"""Repo discovery and canonical path constructors."""

from __future__ import annotations

import os
from pathlib import Path

from .errors import INVALID_STATE, KernelError

DOT_EIGHTOS = ".8os"
IR = "ir"
OPS = "_ops"
KERNEL = "_kernel"

# Categories under ir/_kernel/ (v0.2 §1.1).
KERNEL_CATEGORIES: tuple[str, ...] = (
    "scope",
    "projection",
    "resolver",
    "bridge",
    "surrogate-lineage",
)


def find_repo_root(cwd: Path | None = None) -> Path:
    """Walk up from cwd looking for .8os/version. Raise INVALID_STATE if missing.

    The kernel is bound to a directory once init has run; until then there is no
    repo. Operations other than init must run inside an initialized repo.
    """
    start = (cwd or Path.cwd()).resolve()
    here = start
    while True:
        if (here / DOT_EIGHTOS / "version").exists():
            return here
        if here.parent == here:
            raise KernelError(
                INVALID_STATE,
                f"No initialized 8os repo found at or above {start}. "
                "Run `8os init` first.",
                suggested_action="Run `8os init` in the repo root.",
            )
        here = here.parent


def dot8os(root: Path) -> Path:
    return root / DOT_EIGHTOS


def staging_dir(root: Path, op_id: str) -> Path:
    return dot8os(root) / ".staging" / op_id


def index_dir(root: Path) -> Path:
    return dot8os(root) / "index"


def schemas_dir(root: Path) -> Path:
    return dot8os(root) / "sdk" / "schemas"


def resolvers_dir(root: Path) -> Path:
    return dot8os(root) / "resolvers"


def bridges_dir(root: Path) -> Path:
    return dot8os(root) / "bridges"


def projections_dir(root: Path) -> Path:
    return dot8os(root) / "projections"


def kernel_projections_dir(root: Path) -> Path:
    return projections_dir(root) / "_kernel"


def surrogates_dir(root: Path) -> Path:
    return dot8os(root) / "surrogates"


def events_dir(root: Path) -> Path:
    return dot8os(root) / "events"


def events_raw_dir(root: Path) -> Path:
    return events_dir(root) / "raw"


def event_jsonl_path(root: Path, ts_iso: str) -> Path:
    """Return canonical path for the daily JSONL file for a timestamp.

    `.8os/events/YYYY/MM/DD/events.jsonl`. Single file per day; sharding is a
    future concern.
    """
    date_part = ts_iso[:10]  # YYYY-MM-DD
    y, m, d = date_part.split("-")
    return events_dir(root) / y / m / d / "events.jsonl"


def event_raw_path(root: Path, event_id: str) -> Path:
    return events_raw_dir(root) / f"{event_id}.json"


def ir_dir(root: Path) -> Path:
    return root / IR


def scope_dir(root: Path, scope_id: str) -> Path:
    return ir_dir(root) / scope_id


def scope_yml_path(root: Path, scope_id: str) -> Path:
    return scope_dir(root, scope_id) / "_scope.yml"


def ir_collapsed_path(root: Path, scope_id: str, slug: str) -> Path:
    return scope_dir(root, scope_id) / f"{slug}.md"


def ir_expanded_node_path(root: Path, scope_id: str, slug: str) -> Path:
    return scope_dir(root, scope_id) / slug / "_node.md"


def ir_child_path(
    root: Path, scope_id: str, parent_slug: str, child_slug: str
) -> Path:
    return scope_dir(root, scope_id) / parent_slug / f"{child_slug}.md"


def ops_category_dir(root: Path, category: str) -> Path:
    """ir/_ops/<category>/ — tier 2 records authored by the kernel."""
    return ir_dir(root) / OPS / category


# ---- v0.2 kernel-configuration paths ---------------------------------------


def kernel_scope_dir(root: Path) -> Path:
    """ir/_kernel/ — reserved kernel-configuration scope (v0.2 §1.4)."""
    return ir_dir(root) / KERNEL


def kernel_category_dir(root: Path, category: str) -> Path:
    """ir/_kernel/<category>/ where category is scope|projection|resolver|bridge|surrogate-lineage."""
    return kernel_scope_dir(root) / category


def kernel_record_path(root: Path, category: str, record_id: str) -> Path:
    """ir/_kernel/<category>/<id>.md — projection-definition / resolver / bridge / scope / lineage (I, R)."""
    return kernel_category_dir(root, category) / f"{record_id}.md"


def ensure_dir(p: Path) -> None:
    os.makedirs(p, exist_ok=True)
