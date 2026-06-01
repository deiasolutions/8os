"""v1.0.0 → v1.0.1-partial migration for 8OS repos.

Mechanical, idempotent. Safe to re-run on an already-migrated repo (no-op
when `.8os/version` already reads v1.0.1-partial and no records need work).

Two behaviors per `8OS-BLOCK-1-SPEC-v1.0.1-PARTIAL.md`:

1. **Subdirectory relocation (Amendment 1).** For each existing v1.0 record
   whose projection_types declare `target_subdirectory:` in the (refreshed)
   projection definition, move the file from
   `ir/<scope>/<id><filename_suffix>` to
   `ir/<scope>/<target_subdirectory>/<id><filename_suffix>`.

2. **`authored_via` backfill (Amendment 2).** For each existing record
   lacking `authored_via`, add it. Default `outside`. Records authored by
   `kernel.self` (per `authored_by`) backfill with `kernel.self`.

Phases:
  0 — pre-flight (version check)
  1 — refresh vendored bodies (folds in target_subdirectory + base schema additions)
  2 — relocate records to projection-declared subdirectories
  3 — backfill authored_via on records that lack it
  4 — emit migration event + reindex + bump .8os/version

Invoke with `uv run python scripts/migrate-v1.0-to-v1.0.1-partial.py [--repo <path>]`.
"""

from __future__ import annotations

import argparse
import sys
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Allow running as a script without installing the package.
_REPO_PARENT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_PARENT / "src"))

from eightos import KERNEL_BINARY_RESOLVER_ID, __version__ as KERNEL_VERSION  # noqa: E402
from eightos._atomic import (  # noqa: E402
    append_jsonl_line,
    atomic_write_text,
)
from eightos._events import make_event  # noqa: E402
from eightos._frontmatter import IRRecord, parse_file, serialize  # noqa: E402
from eightos._indexes import write_all  # noqa: E402
from eightos._paths import (  # noqa: E402
    dot8os,
    event_jsonl_path,
    ir_dir,
    kernel_projections_dir,
)
from eightos._projections import target_subdirectory_for  # noqa: E402
from eightos._time import now_iso  # noqa: E402
from eightos._yaml import dump_yaml  # noqa: E402
from eightos.sdk.init_op import (  # noqa: E402
    KERNEL_SELF_BRIDGE_ID,
    _VENDORED_PROJECTIONS,
    _version_tuple,
)

SOURCE_VERSION = "1.0.0"
TARGET_VERSION = KERNEL_VERSION  # binary owns the target (v1.0.1-partial)


@dataclass
class MigrationPlan:
    records_relocated: list[dict[str, str]] = field(default_factory=list)
    records_backfilled: list[dict[str, str]] = field(default_factory=list)
    bodies_refreshed: list[str] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def relocated(self, ir_id: str, old_path: str, new_path: str) -> None:
        self.records_relocated.append({"ir_id": ir_id, "old": old_path, "new": new_path})

    def backfilled(self, ir_id: str, value: str) -> None:
        self.records_backfilled.append({"ir_id": ir_id, "authored_via": value})

    def refreshed(self, ptype: str) -> None:
        self.bodies_refreshed.append(ptype)

    def warn(self, ir_id: str | None, kind: str, detail: str) -> None:
        self.warnings.append({"ir_id": ir_id, "kind": kind, "detail": detail})


# ---------------------------------------------------------------------------
# Phase 0 — pre-flight
# ---------------------------------------------------------------------------


def phase_0_preflight(repo: Path) -> tuple[bool, str]:
    """Return (already_migrated, current_version)."""
    version_file = dot8os(repo) / "version"
    if not version_file.exists():
        raise SystemExit(f"no .8os/version at {repo} — not an 8OS repo")
    current = version_file.read_text(encoding="utf-8").strip()
    if current == TARGET_VERSION:
        return (True, current)
    if current == SOURCE_VERSION:
        return (False, current)
    if _version_tuple(current) > _version_tuple(TARGET_VERSION):
        raise SystemExit(
            f"refusing to downgrade: repo at {current!r} is newer than "
            f"target {TARGET_VERSION!r}"
        )
    # Allow newer-binary-against-older-pre-1.0.0 only by explicit migration
    # chain; this script handles 1.0.0 → 1.0.1-partial only.
    raise SystemExit(
        f"unexpected .8os/version {current!r} — this migration handles "
        f"{SOURCE_VERSION!r} → {TARGET_VERSION!r} only; run the v0.1 → v0.2 "
        "migration first if needed"
    )


# ---------------------------------------------------------------------------
# Phase 1 — refresh vendored projection bodies
# ---------------------------------------------------------------------------


def phase_1_vendored_bodies(repo: Path, plan: MigrationPlan) -> None:
    """Rewrite `.8os/projections/_kernel/<type>.yml` from binary declarations.

    The bodies the binary now ships include `target_subdirectory:` on the
    three projection types from Amendment 1. Per Amendment 3 the binary
    owns vendored bodies across versions; this is the same refresh
    `kernel.init` upgrade-mode performs.
    """
    base = kernel_projections_dir(repo)
    base.mkdir(parents=True, exist_ok=True)
    for ptype, decl in _VENDORED_PROJECTIONS.items():
        target = base / f"{ptype}.yml"
        new_text = dump_yaml(decl["vendored_body"])
        if target.exists() and target.read_text(encoding="utf-8") == new_text:
            continue
        atomic_write_text(target, new_text)
        plan.refreshed(ptype)


# ---------------------------------------------------------------------------
# Phase 2 — relocate records to projection-declared subdirectories
# ---------------------------------------------------------------------------


def phase_2_relocate(repo: Path, plan: MigrationPlan) -> None:
    base = ir_dir(repo)
    if not base.exists():
        return
    # Snapshot the file list first; mutations during the walk would skip files.
    files = sorted(base.rglob("*.md"))
    for md in files:
        if not md.exists():
            continue  # already moved this run (idempotency)
        try:
            rec = parse_file(md)
        except Exception as exc:
            plan.warn(None, "parse-failure", f"{md.relative_to(repo).as_posix()}: {exc}")
            continue
        fm = rec.frontmatter
        ptypes = list(fm.get("projection_types") or [])
        if not ptypes:
            continue
        scope = fm.get("scope")
        if not scope or md.parent == md:
            continue
        try:
            subdir = target_subdirectory_for(repo, ptypes)
        except Exception as exc:
            plan.warn(fm.get("id"), "subdir-resolution-failure", str(exc))
            continue
        if subdir is None:
            continue
        # Records already in the correct subdirectory: idempotent skip.
        if md.parent.name == subdir:
            continue
        # Reject records that aren't directly under ir/<scope>/ — they're
        # children of an expanded parent and are positioned by parent path,
        # not by projection target_subdirectory. (Also true for v1.0 records.)
        scope_root = base / scope
        if md.parent != scope_root:
            plan.warn(
                fm.get("id"),
                "non-flat-position",
                f"record at {md.relative_to(repo).as_posix()} is not directly under "
                f"ir/{scope}/; skipping subdirectory relocation",
            )
            continue
        target_dir = scope_root / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / md.name
        if target.exists():
            plan.warn(
                fm.get("id"),
                "relocation-target-occupied",
                f"target {target.relative_to(repo).as_posix()} already exists; left "
                f"source {md.relative_to(repo).as_posix()} alone",
            )
            continue
        old_rel = str(md.relative_to(repo).as_posix())
        md.rename(target)
        plan.relocated(fm.get("id") or md.stem, old_rel, str(target.relative_to(repo).as_posix()))


# ---------------------------------------------------------------------------
# Phase 3 — backfill authored_via
# ---------------------------------------------------------------------------


def phase_3_backfill(repo: Path, plan: MigrationPlan) -> None:
    base = ir_dir(repo)
    if not base.exists():
        return
    for md in sorted(base.rglob("*.md")):
        try:
            rec = parse_file(md)
        except Exception as exc:
            plan.warn(None, "parse-failure", f"{md.relative_to(repo).as_posix()}: {exc}")
            continue
        fm = deepcopy(rec.frontmatter)
        current = fm.get("authored_via")
        if isinstance(current, str) and current.strip():
            continue
        backfill_value = _infer_authored_via(fm)
        fm["authored_via"] = backfill_value
        new_record = IRRecord(
            frontmatter=fm,
            intention_text=rec.intention_text,
            resolution_text=rec.resolution_text,
        )
        atomic_write_text(md, serialize(new_record))
        plan.backfilled(fm.get("id") or md.stem, backfill_value)


def _infer_authored_via(fm: dict[str, Any]) -> str:
    """Pick `kernel.self` for records with kernel-internal provenance markers,
    otherwise `outside`.

    Heuristic: a record is kernel-internal when authored_by is the kernel.self
    bridge id, the kernel binary resolver id, or the bare string "kernel".
    Foundational records authored by the operator's `human-<id>` bridge at
    init time are treated as external (the operator authored through their
    identity bridge, which is kernel.self from the kernel's vantage but
    here we honor the literal authored_by — `human-<id>` records that were
    crossed via `kernel.self` would have set authored_via at write time and
    so wouldn't reach this fallback).
    """
    author = fm.get("authored_by")
    if not isinstance(author, str):
        return "outside"
    kernel_internal_authors = {
        KERNEL_SELF_BRIDGE_ID,
        KERNEL_BINARY_RESOLVER_ID,
        # earlier kernel versions used a bare "kernel" resolver id
        "kernel",
        # historical kernel.binary@<version> markers from prior migrations
    }
    if author in kernel_internal_authors:
        return KERNEL_SELF_BRIDGE_ID
    if author.startswith("kernel.binary@"):
        return KERNEL_SELF_BRIDGE_ID
    return "outside"


# ---------------------------------------------------------------------------
# Phase 4 — finalize
# ---------------------------------------------------------------------------


def phase_4_finalize(repo: Path, plan: MigrationPlan) -> str | None:
    has_work = bool(
        plan.records_relocated or plan.records_backfilled or plan.bodies_refreshed
    )
    ts = now_iso()
    event_id: str | None = None
    if has_work:
        event = make_event(
            event_type="operation",
            ir_node_id=f"migration-v1.0-to-v1.0.1-partial-{_compact_ts(ts)}",
            ir_node_path_at_event="(migration)",
            resolver_id=KERNEL_BINARY_RESOLVER_ID,
            bridge_id=KERNEL_SELF_BRIDGE_ID,
            intention={
                "text": (
                    f"Migrate v{SOURCE_VERSION} repo to v{TARGET_VERSION} per "
                    "8OS-BLOCK-1-SPEC-v1.0.1-PARTIAL — fold in target_subdirectory "
                    "discipline (Amendment 1), backfill authored_via "
                    "(Amendment 2), refresh vendored bodies (Amendment 3)."
                ),
                "context_refs": [],
                "scope": "_ops",
                "depth": 0,
            },
            resolution={
                "text": (
                    f"Migration completed: {len(plan.records_relocated)} records "
                    f"relocated, {len(plan.records_backfilled)} records backfilled, "
                    f"{len(plan.bodies_refreshed)} vendored bodies refreshed, "
                    f"{len(plan.warnings)} warnings."
                ),
                "structured": {
                    "schema": "8os.migration.v1",
                    "from_version": SOURCE_VERSION,
                    "to_version": TARGET_VERSION,
                    "records_relocated": plan.records_relocated,
                    "records_backfilled": plan.records_backfilled,
                    "vendored_bodies_refreshed": plan.bodies_refreshed,
                    "warnings": plan.warnings,
                },
                "authority_level": "hard",
            },
            outcome="accepted",
            ts=ts,
        )
        append_jsonl_line(event_jsonl_path(repo, ts), event)
        event_id = event["event_id"]
    write_all(repo)
    atomic_write_text(dot8os(repo) / "version", TARGET_VERSION + "\n")
    return event_id


def _compact_ts(ts: str) -> str:
    return ts.replace(":", "").replace("-", "").replace(".", "").rstrip("Z").lower()


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def migrate(repo: Path) -> dict[str, Any]:
    plan = MigrationPlan()
    already, current = phase_0_preflight(repo)
    if already:
        return {
            "already_migrated": True,
            "current_version": current,
            "warnings": [],
            "records_relocated": [],
            "records_backfilled": [],
            "bodies_refreshed": [],
        }
    phase_1_vendored_bodies(repo, plan)
    phase_2_relocate(repo, plan)
    phase_3_backfill(repo, plan)
    event_id = phase_4_finalize(repo, plan)
    return {
        "already_migrated": False,
        "previous_version": current,
        "current_version": TARGET_VERSION,
        "event_id": event_id,
        "records_relocated": plan.records_relocated,
        "records_backfilled": plan.records_backfilled,
        "bodies_refreshed": plan.bodies_refreshed,
        "warnings": plan.warnings,
    }


def main() -> int:
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(
        description="Migrate 8OS repo from v1.0.0 to v1.0.1-partial."
    )
    ap.add_argument("--repo", type=Path, default=Path.cwd(), help="repo root (default: cwd)")
    args = ap.parse_args()

    result = migrate(args.repo)
    if result["already_migrated"]:
        print(f"already at {TARGET_VERSION} — no-op")
        return 0
    print(f"relocated: {len(result['records_relocated'])}")
    print(f"backfilled: {len(result['records_backfilled'])}")
    print(f"refreshed bodies: {len(result['bodies_refreshed'])}")
    print(f"warnings: {len(result['warnings'])}")
    for w in result["warnings"]:
        print(f"  [{w['kind']}] {w.get('ir_id') or '-'}: {w['detail']}")
    if result.get("event_id"):
        print(f"event: {result['event_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
