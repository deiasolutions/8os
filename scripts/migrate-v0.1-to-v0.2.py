"""v0.1.0 → v0.2 migration for 8OS repos.

Mechanical, idempotent. Safe to re-run on an already-migrated repo (no-op
after the .8os/version bump in phase 4).

Phases (per BLOCK-2.7-SPEC-CORRECTIONS plan):
  0 — pre-flight (version check, operator-id resolution)
  1 — structural conversions (.8os/resolvers, bridges, projections, ir/<scope>/_scope.yml → ir/_kernel/...)
  2 — vendored kernel content (nine projections, three resolvers, two bridges)
  3 — frontmatter migration of existing tier-1 records (Patches 3/4/5, OPEN-Q-008-RESOLVED, OPEN-Q-012)
  4 — migration event + reindex + version bump (last write)

Invoke with `uv run python scripts/migrate-v0.1-to-v0.2.py [--operator-id <id>] [--repo <path>]`.
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

from eightos import KERNEL_BINARY_RESOLVER_ID  # noqa: E402
from eightos._atomic import (  # noqa: E402
    StagedFile,
    append_jsonl_line,
    atomic_write_text,
    commit_staged,
)
from eightos._events import make_event  # noqa: E402
from eightos._frontmatter import IRRecord, parse_file, serialize  # noqa: E402
from eightos._indexes import write_all  # noqa: E402
from eightos._paths import (  # noqa: E402
    bridges_dir,
    dot8os,
    ensure_dir,
    event_jsonl_path,
    ir_dir,
    kernel_category_dir,
    kernel_projections_dir,
    kernel_record_path,
    projections_dir,
    resolvers_dir,
)
from eightos._time import now_iso  # noqa: E402
from eightos._yaml import dump_yaml, load_yaml_file  # noqa: E402
from eightos.sdk.init_op import (  # noqa: E402
    KERNEL_SCOPE_ID,
    _KERNEL_INTERNAL_RESOLVERS,
    _VENDORED_PROJECTIONS,
    _kernel_self_endpoint,
    _vendor_projection_bodies,
    _vendor_schemas,
)

KERNEL_SELF_BRIDGE_ID = "kernel.self"
TARGET_VERSION = "0.2.0"

# Projection-type rename table (Patch 3).
PROJECTION_TYPE_RENAMES = {
    "tier3-event": "_kernel.tier3-event",
    "authorization": "_kernel.authorization",
    "resolver-selection": "_kernel.resolver-selection",
    "capability-update": "_kernel.capability-update",
}

# v0.1 outside_type → v0.2 bridge_type translation. v0.2's bridge_type is a
# coarser enum; multiple v0.1 values map to "api" or "script".
OUTSIDE_TYPE_TRANSLATION = {
    "llm-api": "api",
    "external-service": "api",
    "human-reviewer": "human",
    "physics-sim": "simulation",
    "sensor": "sensor",
    "cpu-instruction": "script",
    "other": "other",
}


@dataclass
class MigrationPlan:
    """Accumulator for what the migration changes. Becomes the migration
    event's `resolution.structured` payload (stable schema documented at the
    `_emit_migration_event` callsite below).
    """

    records_created: list[str] = field(default_factory=list)
    records_removed: list[str] = field(default_factory=list)
    records_rewritten: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def created(self, record_id: str) -> None:
        self.records_created.append(record_id)

    def removed(self, path: str) -> None:
        self.records_removed.append(path)

    def rewrote(self, record_id: str, fields_changed: list[str]) -> None:
        self.records_rewritten.append({"id": record_id, "fields_changed": sorted(set(fields_changed))})

    def warn(self, record_id: str | None, type_: str, detail: str) -> None:
        self.warnings.append({"record_id": record_id, "type": type_, "detail": detail})


# ---------------------------------------------------------------------------
# Phase 0 — pre-flight
# ---------------------------------------------------------------------------


def phase_0_preflight(repo: Path, operator_id_flag: str | None, plan: MigrationPlan) -> tuple[str, bool]:
    """Verify the repo state and resolve the operator id.

    Returns (operator_id, already_migrated). When already_migrated is True,
    callers should skip subsequent phases — the script is a no-op.
    """
    version_file = dot8os(repo) / "version"
    if not version_file.exists():
        raise SystemExit(f"no .8os/version at {repo} — not an 8OS repo")
    current_version = version_file.read_text(encoding="utf-8").strip()
    if current_version == TARGET_VERSION:
        return ("", True)
    if current_version != "0.1.0":
        raise SystemExit(
            f"unexpected .8os/version {current_version!r} — migration handles 0.1.0 → {TARGET_VERSION} only"
        )

    # Resolve operator id. CLI flag wins over inferred (refinement 2).
    inferred_op_id = _infer_operator_id_from_bootstrap(repo)
    if operator_id_flag and inferred_op_id and operator_id_flag != inferred_op_id:
        plan.warn(
            None,
            "operator-id-discrepancy",
            f"--operator-id={operator_id_flag!r} overrides inferred id {inferred_op_id!r} from v0.1 bootstrap (I, R)",
        )
    operator_id = operator_id_flag or inferred_op_id
    if not operator_id:
        raise SystemExit(
            "could not determine primary_operator_id — pass --operator-id, or ensure the v0.1 "
            "bootstrap (I, R) at ir/<scope>/000-bootstrap.md carries an authored_by"
        )
    return (operator_id, False)


def _infer_operator_id_from_bootstrap(repo: Path) -> str | None:
    """Find a v0.1 000-bootstrap.md and return its authored_by, if any."""
    if not ir_dir(repo).exists():
        return None
    for bootstrap in ir_dir(repo).rglob("000-bootstrap.md"):
        try:
            fm = parse_file(bootstrap).frontmatter
        except Exception:
            continue
        author = fm.get("authored_by")
        if isinstance(author, str) and author:
            return author
    return None


# ---------------------------------------------------------------------------
# Phase 1 — structural conversions
# ---------------------------------------------------------------------------


def phase_1_structural(repo: Path, operator_id: str, plan: MigrationPlan) -> None:
    """Move v0.1 typed configuration files to v0.2 (I, R) records.

    Order: scopes (1.1) → resolvers (1.2) → bridges (1.3) → projections (1.4).
    Scopes first because subsequent kernel-config records reference _kernel as
    their scope; the directory structure needs to exist.
    """
    ts = now_iso()
    _phase_1_1_scopes(repo, operator_id, ts, plan)
    _phase_1_2_resolvers(repo, operator_id, ts, plan)
    _phase_1_3_bridges(repo, operator_id, ts, plan)
    _phase_1_4_projections(repo, operator_id, ts, plan)


def _migration_base_frontmatter(
    *,
    record_id: str,
    projection_type: str,
    summary: str,
    ts: str,
    operator_id: str,
    authority: str = "hard",
) -> dict[str, Any]:
    """Base 8OS frontmatter for a record authored by the migration itself.

    Migration is a kernel-self-observation: the kernel observing what it just
    did to its own representation. Provenance follows the cogito pattern —
    authored_by/authored_via point at kernel.self; resolver is the version-
    suffixed binary id (OPEN-Q-008-RESOLVED).
    """
    return {
        "id": record_id,
        "kind": "ir-node",
        "tier": 1,
        "projection_types": [projection_type],
        "collapsed_summary": summary,
        "expanded_into": None,
        "parent": None,
        "scope": KERNEL_SCOPE_ID,
        "depends_on": [],
        "visible_to": [KERNEL_SCOPE_ID],
        "resolved_at": ts,
        "valid_through": None,
        "revalidate_trigger": None,
        "status": "resolved",
        "resolver": KERNEL_BINARY_RESOLVER_ID,
        "resolution_event": None,
        "authored_by": KERNEL_SELF_BRIDGE_ID,
        "authored_on": ts,
        "authority_level": authority,
        "authored_via": KERNEL_SELF_BRIDGE_ID,
        "supersedes": None,
        "superseded_by": None,
        "surrogate_of": None,
    }


def _phase_1_1_scopes(repo: Path, operator_id: str, ts: str, plan: MigrationPlan) -> None:
    """ir/<scope>/_scope.yml → ir/_kernel/scope/<scope-id>.md"""
    if not ir_dir(repo).exists():
        return
    staged: list[StagedFile] = []
    for scope_yml in sorted(ir_dir(repo).glob("*/_scope.yml")):
        scope_id = scope_yml.parent.name
        target = kernel_record_path(repo, "scope", scope_id)
        if target.exists():
            continue  # idempotent
        body_doc = load_yaml_file(scope_yml) or {}
        fm = _migration_base_frontmatter(
            record_id=scope_id,
            projection_type="_kernel.scope",
            summary=f"Scope declaration: {body_doc.get('display_name', scope_id)}",
            ts=ts,
            operator_id=operator_id,
        )
        # Projection-declared extensions (§3.1).
        fm["parent_scope"] = body_doc.get("parent_scope")
        fm["authority_defaults"] = body_doc.get(
            "authority_defaults", {"hard": [], "convention": [], "uncalibrated": []}
        )
        fm["visibility_defaults"] = body_doc.get("visibility_defaults", [scope_id])
        record = IRRecord(
            frontmatter=fm,
            intention_text=body_doc.get("description") or f"Scope {scope_id!r}.",
            resolution_text=None,
        )
        staged.append(StagedFile(target, content_text=serialize(record)))
        plan.created(scope_id)
        plan.removed(str(scope_yml.relative_to(repo).as_posix()))
    if staged:
        commit_staged(staged)
        # Remove the source files only after the targets commit successfully.
        for scope_yml in sorted(ir_dir(repo).glob("*/_scope.yml")):
            scope_id = scope_yml.parent.name
            if kernel_record_path(repo, "scope", scope_id).exists():
                scope_yml.unlink()


def _phase_1_2_resolvers(repo: Path, operator_id: str, ts: str, plan: MigrationPlan) -> None:
    src = resolvers_dir(repo)
    if not src.exists():
        return
    staged: list[StagedFile] = []
    for yml in sorted(src.glob("*.yml")):
        rid = yml.stem
        target = kernel_record_path(repo, "resolver", rid)
        if target.exists():
            continue
        doc = load_yaml_file(yml) or {}
        fm = _migration_base_frontmatter(
            record_id=rid,
            projection_type="_kernel.resolver",
            summary=f"Resolver: {doc.get('display_name', rid)}",
            ts=ts,
            operator_id=operator_id,
        )
        fm["resolver_id"] = rid
        fm["display_name"] = doc.get("display_name") or rid
        fm["bridge"] = doc.get("bridge")
        fm["cost"] = _flatten_v01_cost(doc.get("cost") or {})
        fm["capability"] = _list_to_map_capability(doc.get("capability") or [])
        if doc.get("model_name"):
            fm["model_name"] = doc["model_name"]
        record = IRRecord(
            frontmatter=fm,
            intention_text=f"Migrated resolver {rid!r} from v0.1 .8os/resolvers/{rid}.yml.",
            resolution_text=None,
        )
        staged.append(StagedFile(target, content_text=serialize(record)))
        plan.created(rid)
        plan.removed(str(yml.relative_to(repo).as_posix()))
    if staged:
        commit_staged(staged)
        for yml in sorted(src.glob("*.yml")):
            rid = yml.stem
            if kernel_record_path(repo, "resolver", rid).exists():
                yml.unlink()
        if not any(src.iterdir()):
            src.rmdir()


def _flatten_v01_cost(v01_cost: dict[str, Any]) -> dict[str, Any]:
    """v0.1 nested cost (axis → {unit, declared, measured_p50, measured_p95}) → v0.2 flat."""

    def _declared(block: Any, default: float = 0.0) -> float:
        if isinstance(block, dict):
            v = block.get("declared")
            return float(v) if isinstance(v, (int, float)) else default
        return default

    return {
        "clock_ms": _declared(v01_cost.get("clock")),
        "coin_usd": _declared(v01_cost.get("coin")),
        "carbon_g": _declared(v01_cost.get("carbon")),
        "currency": "USD",
    }


def _list_to_map_capability(v01_cap: list[Any]) -> dict[str, Any]:
    """v0.1 [{domain, sigma, pi, alpha, rho}] → v0.2 {<domain>: {sigma, pi, alpha, rho}}."""
    out: dict[str, Any] = {}
    for entry in v01_cap:
        if not isinstance(entry, dict):
            continue
        domain = entry.get("domain")
        if not isinstance(domain, str):
            continue
        out[domain] = {
            "sigma": _strip_sample_n(entry.get("sigma")),
            "pi": _strip_sample_n(entry.get("pi")),
            "alpha": _strip_sample_n(entry.get("alpha")),
            "rho": _strip_sample_n(entry.get("rho")),
        }
    return out


def _strip_sample_n(block: Any) -> dict[str, Any]:
    if not isinstance(block, dict):
        return {"declared": None, "measured": None}
    return {
        "declared": block.get("declared"),
        "measured": block.get("measured"),
    }


def _phase_1_3_bridges(repo: Path, operator_id: str, ts: str, plan: MigrationPlan) -> None:
    src = bridges_dir(repo)
    if not src.exists():
        return
    staged: list[StagedFile] = []
    for yml in sorted(src.glob("*.yml")):
        bid = yml.stem
        target = kernel_record_path(repo, "bridge", bid)
        if target.exists():
            continue
        doc = load_yaml_file(yml) or {}
        # v0.1 outside_type → v0.2 bridge_type. Unknown → "other" with warning.
        v01_type = doc.get("outside_type")
        bridge_type = OUTSIDE_TYPE_TRANSLATION.get(v01_type, "other")
        if v01_type and v01_type not in OUTSIDE_TYPE_TRANSLATION:
            plan.warn(bid, "unknown-outside-type", f"v0.1 outside_type {v01_type!r} mapped to bridge_type 'other'")

        # cost_envelope: derived from default_cost p50 if present; else null with warning.
        default_cost = doc.get("default_cost") or {}
        cost_envelope = {
            "clock_ms_max": default_cost.get("clock_ms_p50"),
            "coin_usd_max": default_cost.get("coin_usd_p50"),
            "carbon_g_max": default_cost.get("carbon_g_p50"),
        }
        used_defaults = all(v is None for v in cost_envelope.values())
        if used_defaults:
            plan.warn(
                bid,
                "default-cost-envelope",
                "v0.1 had no default_cost; cost_envelope written with null upper bounds. Human review recommended.",
            )

        # scope_of_authority: not in v0.1; default "session" with warning.
        scope_of_authority = "session"
        plan.warn(
            bid,
            "default-scope-of-authority",
            "v0.1 did not declare scope_of_authority; defaulted to 'session'. Human review recommended.",
        )

        # Override: bridges with default-filled fields get authority_level uncalibrated.
        authority = "uncalibrated" if used_defaults else "hard"

        fm = _migration_base_frontmatter(
            record_id=bid,
            projection_type="_kernel.bridge",
            summary=f"Bridge: {doc.get('display_name', bid)}",
            ts=ts,
            operator_id=operator_id,
            authority=authority,
        )
        fm["bridge_id"] = bid
        fm["display_name"] = doc.get("display_name") or bid
        fm["bridge_type"] = bridge_type
        fm["requires_authorization"] = bool(doc.get("requires_authorization"))
        fm["scope_of_authority"] = scope_of_authority
        fm["cost_envelope"] = cost_envelope
        if doc.get("endpoint") is not None:
            fm["endpoint"] = doc["endpoint"]
        # v0.1 status (active|deprecated|quarantined) → v0.2 bridge_status (Patch 4).
        # v0.2 adds 'removed' to the enum but v0.1 had no equivalent value.
        if doc.get("status"):
            fm["bridge_status"] = doc["status"]
        record = IRRecord(
            frontmatter=fm,
            intention_text=f"Migrated bridge {bid!r} from v0.1 .8os/bridges/{bid}.yml.",
            resolution_text=None,
        )
        staged.append(StagedFile(target, content_text=serialize(record)))
        plan.created(bid)
        plan.removed(str(yml.relative_to(repo).as_posix()))
    if staged:
        commit_staged(staged)
        for yml in sorted(src.glob("*.yml")):
            bid = yml.stem
            if kernel_record_path(repo, "bridge", bid).exists():
                yml.unlink()
        if not any(src.iterdir()):
            src.rmdir()


def _phase_1_4_projections(repo: Path, operator_id: str, ts: str, plan: MigrationPlan) -> None:
    """Project-declared .8os/projections/<id>.yml → ir/_kernel/projection/<id>.md."""
    src = projections_dir(repo)
    if not src.exists():
        return
    staged: list[StagedFile] = []
    for yml in sorted(src.glob("*.yml")):
        # Only the top-level project-declared projections; the _kernel/ subdir
        # is vendored bodies (see _phase_2_vendored_projections).
        if yml.parent.name != "projections":
            continue
        pid = yml.stem
        target = kernel_record_path(repo, "projection", pid)
        if target.exists():
            continue
        body_doc = load_yaml_file(yml) or {}
        # Block 2.5 era ad hoc projection yamls used `file_extension`; v0.2
        # standardized on `filename_suffix` (Block 2.5 OPEN-Q-012, §3.2). Translate.
        if "file_extension" in body_doc and "filename_suffix" not in body_doc:
            body_doc["filename_suffix"] = body_doc.pop("file_extension")
            plan.warn(
                pid,
                "field-rename",
                "v0.1-era projection field 'file_extension' renamed to 'filename_suffix' to match v0.2 §3.2",
            )
        fm = _migration_base_frontmatter(
            record_id=pid,
            projection_type="_kernel.projection",
            summary=f"Projection definition: {pid}",
            ts=ts,
            operator_id=operator_id,
        )
        fm["projection_id"] = pid
        fm["display_name"] = body_doc.get("display_name") or pid
        # Embed the v0.1 body as a YAML fenced block so load_projection_body
        # can find it (resolution order: vendored body, then (I, R) body).
        fenced_body = "```yaml\n" + dump_yaml(body_doc).rstrip() + "\n```\n"
        record = IRRecord(
            frontmatter=fm,
            intention_text=f"Migrated projection {pid!r} from v0.1 .8os/projections/{pid}.yml.\n\n{fenced_body}",
            resolution_text=None,
        )
        staged.append(StagedFile(target, content_text=serialize(record)))
        plan.created(pid)
        plan.removed(str(yml.relative_to(repo).as_posix()))
    if staged:
        commit_staged(staged)
        for yml in sorted(src.glob("*.yml")):
            if yml.parent.name != "projections":
                continue
            pid = yml.stem
            if kernel_record_path(repo, "projection", pid).exists():
                yml.unlink()


# ---------------------------------------------------------------------------
# Phase 2 — vendored kernel content
# ---------------------------------------------------------------------------


def phase_2_vendored(repo: Path, operator_id: str, plan: MigrationPlan) -> None:
    ts = now_iso()
    _phase_2_1_projections(repo, operator_id, ts, plan)
    _phase_2_2_internal_resolvers(repo, operator_id, ts, plan)
    _phase_2_3_vendored_bridges(repo, operator_id, ts, plan)
    _phase_2_4_purge_legacy_vendored_bodies(repo, plan)
    _phase_2_5_refresh_schemas(repo, plan)


def _phase_2_1_projections(repo: Path, operator_id: str, ts: str, plan: MigrationPlan) -> None:
    """Add the nine vendored _kernel.* projection-definition (I, R)s."""
    # First, refresh the vendored body files (Patch 3 added four prefixed
    # bodies; the v0.1 unprefixed bodies are deleted in phase 2.4).
    _vendor_projection_bodies(repo)

    # Ensure the _kernel scope (I, R) exists. Some v0.1 repos used a user
    # scope literally named 'kernel' (no underscore); the reserved _kernel is
    # always added by migration regardless.
    _kernel_scope_target = kernel_record_path(repo, "scope", KERNEL_SCOPE_ID)
    staged: list[StagedFile] = []
    if not _kernel_scope_target.exists():
        fm = _migration_base_frontmatter(
            record_id=KERNEL_SCOPE_ID,
            projection_type="_kernel.scope",
            summary="Reserved kernel-configuration scope.",
            ts=ts,
            operator_id=operator_id,
        )
        fm["parent_scope"] = None
        fm["authority_defaults"] = {"hard": ["kernel.self"], "convention": [], "uncalibrated": []}
        fm["visibility_defaults"] = [KERNEL_SCOPE_ID]
        rec = IRRecord(
            frontmatter=fm,
            intention_text="The reserved scope for kernel-configuration (I, R) records (§1.4).",
            resolution_text=None,
        )
        staged.append(StagedFile(_kernel_scope_target, content_text=serialize(rec)))
        plan.created(KERNEL_SCOPE_ID)

    # Add the nine projection-definition (I, R)s.
    for ptype, decl in _VENDORED_PROJECTIONS.items():
        target = kernel_record_path(repo, "projection", ptype)
        if target.exists():
            continue
        fm = _migration_base_frontmatter(
            record_id=ptype,
            projection_type="_kernel.projection",
            summary=f"Projection definition: {decl['display_name']}",
            ts=ts,
            operator_id=operator_id,
        )
        fm["projection_id"] = ptype
        fm["display_name"] = decl["display_name"]
        body = decl["vendored_body"]
        fenced = "```yaml\n" + dump_yaml(body).rstrip() + "\n```\n"
        rec = IRRecord(
            frontmatter=fm,
            intention_text=decl["body"] + "\n\n" + fenced,
            resolution_text=None,
        )
        staged.append(StagedFile(target, content_text=serialize(rec)))
        plan.created(ptype)
    if staged:
        commit_staged(staged)


def _phase_2_2_internal_resolvers(repo: Path, operator_id: str, ts: str, plan: MigrationPlan) -> None:
    staged: list[StagedFile] = []
    for rid, decl in _KERNEL_INTERNAL_RESOLVERS.items():
        target = kernel_record_path(repo, "resolver", rid)
        if target.exists():
            continue
        fm = _migration_base_frontmatter(
            record_id=rid,
            projection_type="_kernel.resolver",
            summary=f"Kernel-internal resolver: {decl['display_name']}",
            ts=ts,
            operator_id=operator_id,
        )
        fm["resolver_id"] = rid
        fm["display_name"] = decl["display_name"]
        fm["bridge"] = None  # kernel-internal resolvers are pure-inside.
        fm["cost"] = decl["cost"]
        fm["capability"] = decl["capability"]
        rec = IRRecord(
            frontmatter=fm,
            intention_text=decl["body"],
            resolution_text=None,
        )
        staged.append(StagedFile(target, content_text=serialize(rec)))
        plan.created(rid)
    if staged:
        commit_staged(staged)


def _phase_2_3_vendored_bridges(repo: Path, operator_id: str, ts: str, plan: MigrationPlan) -> None:
    """Add kernel.self and human-<operator_id> bridges."""
    staged: list[StagedFile] = []
    # kernel.self
    self_target = kernel_record_path(repo, "bridge", KERNEL_SELF_BRIDGE_ID)
    if not self_target.exists():
        fm = _migration_base_frontmatter(
            record_id=KERNEL_SELF_BRIDGE_ID,
            projection_type="_kernel.bridge",
            summary="The kernel's *cogito* — self-observation bridge (§2.4, §3.4).",
            ts=ts,
            operator_id=operator_id,
        )
        fm["bridge_id"] = KERNEL_SELF_BRIDGE_ID
        fm["display_name"] = "Kernel Self-Observation"
        fm["bridge_type"] = "other"
        fm["requires_authorization"] = False
        fm["scope_of_authority"] = "persistent"
        fm["cost_envelope"] = {"clock_ms_max": 0, "coin_usd_max": 0, "carbon_g_max": 0}
        fm["endpoint"] = _kernel_self_endpoint()
        fm["bridge_status"] = "active"
        rec = IRRecord(
            frontmatter=fm,
            intention_text=(
                "kernel.self is the bridge through which the kernel binary records "
                "observations about its own state. Vendored at init/migration; "
                "grounded in the kernel's own existence (§2.4)."
            ),
            resolution_text=None,
        )
        staged.append(StagedFile(self_target, content_text=serialize(rec)))
        plan.created(KERNEL_SELF_BRIDGE_ID)

    # human-<operator_id>
    human_id = f"human-{operator_id}"
    human_target = kernel_record_path(repo, "bridge", human_id)
    if not human_target.exists():
        fm = _migration_base_frontmatter(
            record_id=human_id,
            projection_type="_kernel.bridge",
            summary=f"Human identity bridge for operator {operator_id!r}.",
            ts=ts,
            operator_id=operator_id,
        )
        fm["bridge_id"] = human_id
        fm["display_name"] = f"Human Identity ({operator_id})"
        fm["bridge_type"] = "human"
        fm["requires_authorization"] = False
        fm["scope_of_authority"] = "persistent"
        fm["cost_envelope"] = {"clock_ms_max": None, "coin_usd_max": None, "carbon_g_max": None}
        fm["endpoint"] = {"identity": operator_id}
        fm["bridge_status"] = "active"
        rec = IRRecord(
            frontmatter=fm,
            intention_text=(
                f"The bridge through which the human {operator_id!r} authors records "
                "into their own scopes. Grounded in the human's identity per #NOKINGS (§2.4)."
            ),
            resolution_text=None,
        )
        staged.append(StagedFile(human_target, content_text=serialize(rec)))
        plan.created(human_id)

    if staged:
        commit_staged(staged)


def _phase_2_5_refresh_schemas(repo: Path, plan: MigrationPlan) -> None:
    """Refresh .8os/sdk/schemas/ from the current eightos.schemas package.

    v0.2 trims v0.1's eighteen ops to sixteen (kernel.bridge.add and
    kernel.resolver.add removed). The dev's .8os/sdk/schemas/ inherited
    Block 2.5's v0.1-init artifacts, including schemas for the removed ops.
    Clear and re-vendor so the on-disk schema set matches the running kernel.
    """
    schemas_path = dot8os(repo) / "sdk" / "schemas"
    if schemas_path.exists():
        for f in sorted(schemas_path.glob("*.json")):
            f.unlink()
            plan.removed(str(f.relative_to(repo).as_posix()))
    _vendor_schemas(repo)


def _phase_2_4_purge_legacy_vendored_bodies(repo: Path, plan: MigrationPlan) -> None:
    """Remove the v0.1 unprefixed body files from .8os/projections/_kernel/.

    The v0.2 bodies are written with _kernel. prefix by _vendor_projection_bodies
    in phase 2.1; the v0.1 unprefixed siblings are now stale.
    """
    legacy_names = {"tier3-event.yml", "authorization.yml", "resolver-selection.yml", "capability-update.yml"}
    base = kernel_projections_dir(repo)
    if not base.exists():
        return
    for name in legacy_names:
        p = base / name
        if p.exists():
            p.unlink()
            plan.removed(str(p.relative_to(repo).as_posix()))


# ---------------------------------------------------------------------------
# Phase 3 — frontmatter migration of existing tier-1 records
# ---------------------------------------------------------------------------


def phase_3_frontmatter(repo: Path, plan: MigrationPlan) -> None:
    """Walk every (I, R) under ir/ and apply Patches 3/4/5 + OPEN-Q-008/012."""
    if not ir_dir(repo).exists():
        return

    # First pass: per-record frontmatter rewrites (3.1–3.4).
    # Second pass: id/cross-reference rewrites for slug-suffix transitions (3.5).
    suffix_rewrites: dict[str, str] = {}  # old_id → new_id

    # Build suffix table from now-vendored projection definitions.
    suffix_by_projection = _suffix_by_projection_type(repo)

    md_files = sorted(ir_dir(repo).rglob("*.md"))
    for md in md_files:
        if md.name.startswith("_"):
            continue
        rec = parse_file(md)
        fm = deepcopy(rec.frontmatter)
        changed: list[str] = []

        # 3.1: projection_types renames (Patch 3).
        ptypes = fm.get("projection_types") or []
        if isinstance(ptypes, list):
            new_ptypes = [PROJECTION_TYPE_RENAMES.get(p, p) for p in ptypes]
            if new_ptypes != ptypes:
                fm["projection_types"] = new_ptypes
                changed.append("projection_types")
                ptypes = new_ptypes

        # 3.2: bridge_type → authored_via (Patch 5). MUST run before 3.4.
        # Skip for _kernel.bridge records — their `bridge_type` is the
        # projection-declared category (api|human|...), legitimately coexisting
        # with the base `authored_via` field. Patch 5's rename targets v0.1
        # records where `bridge_type` was the misleadingly-named base field.
        is_kernel_bridge_record = "_kernel.bridge" in (fm.get("projection_types") or [])
        if "bridge_type" in fm and not is_kernel_bridge_record:
            if "authored_via" in fm and fm["authored_via"] != fm["bridge_type"]:
                plan.warn(
                    fm.get("id"),
                    "frontmatter-collision",
                    "both bridge_type and authored_via present with different values; left untouched",
                )
            else:
                fm["authored_via"] = fm.pop("bridge_type")
                changed.append("bridge_type→authored_via")

        # 3.3: status → bridge_status, but ONLY for _kernel.bridge records.
        if "_kernel.bridge" in (fm.get("projection_types") or []):
            # The base frontmatter has its own `status` field (lifecycle). Bridges
            # also (in v0.1) carried bridge availability under bare `status`. The
            # base lifecycle status for a migrated kernel-config record is
            # "resolved"; any non-lifecycle value is the bridge availability that
            # needs Patch 4 namespacing. Heuristic: if `status` is one of the v0.1
            # bridge values (active|deprecated|quarantined), namespace it.
            v01_bridge_status_values = {"active", "deprecated", "quarantined"}
            current = fm.get("status")
            if current in v01_bridge_status_values and "bridge_status" not in fm:
                fm["bridge_status"] = current
                fm["status"] = "resolved"  # bring lifecycle back to its expected value
                changed.append("status→bridge_status")

        # 3.4: conditional resolver rewrite (OPEN-Q-008-RESOLVED).
        # MUST run after 3.2 because it reads the renamed authored_via.
        if fm.get("authored_via") == KERNEL_SELF_BRIDGE_ID and fm.get("resolver") == "kernel":
            fm["resolver"] = KERNEL_BINARY_RESOLVER_ID
            changed.append("resolver→kernel.binary@version")

        # 3.5: detect slug-suffix transition (the rewrite happens in pass 2).
        new_id = _suffix_stripped_id(fm.get("id"), ptypes, suffix_by_projection)
        if new_id is not None and new_id != fm.get("id"):
            old_id = fm["id"]
            if old_id in suffix_rewrites and suffix_rewrites[old_id] != new_id:
                raise SystemExit(
                    f"slug-suffix ambiguity for {old_id!r}: multiple new ids ({suffix_rewrites[old_id]!r} and {new_id!r})"
                )
            suffix_rewrites[old_id] = new_id

        if changed:
            new_record = IRRecord(
                frontmatter=fm,
                intention_text=rec.intention_text,
                resolution_text=rec.resolution_text,
            )
            atomic_write_text(md, serialize(new_record))
            plan.rewrote(fm.get("id") or md.stem, changed)

    # Second pass: rewrite ids and cross-references for slug-suffix transitions.
    if suffix_rewrites:
        for md in md_files:
            if md.name.startswith("_"):
                continue
            rec = parse_file(md)
            fm = deepcopy(rec.frontmatter)
            changed: list[str] = []
            if fm.get("id") in suffix_rewrites:
                old_id = fm["id"]
                fm["id"] = suffix_rewrites[old_id]
                changed.append("id")
            for ref_field in ("parent", "expanded_into", "supersedes", "superseded_by"):
                if fm.get(ref_field) in suffix_rewrites:
                    fm[ref_field] = suffix_rewrites[fm[ref_field]]
                    changed.append(ref_field)
            deps = fm.get("depends_on") or []
            if isinstance(deps, list):
                new_deps = [suffix_rewrites.get(d, d) for d in deps]
                if new_deps != deps:
                    fm["depends_on"] = new_deps
                    changed.append("depends_on")
            if changed:
                new_record = IRRecord(
                    frontmatter=fm,
                    intention_text=rec.intention_text,
                    resolution_text=rec.resolution_text,
                )
                atomic_write_text(md, serialize(new_record))
                plan.rewrote(fm["id"], changed)


def _suffix_by_projection_type(repo: Path) -> dict[str, str]:
    """{<projection-id>: <filename_suffix>} for every projection definition on disk."""
    out: dict[str, str] = {}
    proj_dir = kernel_category_dir(repo, "projection")
    if not proj_dir.exists():
        return out
    for md in proj_dir.glob("*.md"):
        try:
            rec = parse_file(md)
        except Exception:
            continue
        body_text = (rec.intention_text or "") + ("\n" + (rec.resolution_text or ""))
        body_doc = _extract_yaml_body(body_text)
        if body_doc is None:
            continue
        suffix = body_doc.get("filename_suffix")
        ptype = body_doc.get("projection_id") or rec.frontmatter.get("id")
        if isinstance(ptype, str) and isinstance(suffix, str) and suffix and suffix != ".md":
            out[ptype] = suffix
    return out


def _extract_yaml_body(text: str) -> dict[str, Any] | None:
    """Mirror of _projections._extract_yaml_body (kept local to avoid a private import)."""
    from eightos._yaml import load_yaml

    in_fence = False
    lines: list[str] = []
    for ln in text.splitlines():
        s = ln.strip()
        if not in_fence and s in ("```yaml", "```yml"):
            in_fence = True
            continue
        if in_fence and s == "```":
            break
        if in_fence:
            lines.append(ln)
    if not lines:
        return None
    parsed = load_yaml("\n".join(lines))
    return parsed if isinstance(parsed, dict) else None


def _suffix_stripped_id(
    record_id: Any,
    projection_types: list[str],
    suffix_by_projection: dict[str, str],
) -> str | None:
    """Return the suffix-stripped id, or None if no suffix applies.

    Refinement 1: longest-matching-suffix wins. If multiple equal-length
    suffixes match, abort — the migration refuses to silently pick.
    """
    if not isinstance(record_id, str):
        return None
    candidates: list[tuple[int, str]] = []  # (suffix_length, new_id)
    for ptype in projection_types:
        suffix = suffix_by_projection.get(ptype)
        if not suffix:
            continue
        # filename_suffix is e.g. ".prism.md"; the id-side suffix is ".prism".
        id_suffix = suffix.removesuffix(".md")
        if not id_suffix:
            continue
        if record_id.endswith(id_suffix):
            new_id = record_id[: -len(id_suffix)]
            candidates.append((len(id_suffix), new_id))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x[0], x[1]))
    longest_len = candidates[0][0]
    longest_matches = [c for c in candidates if c[0] == longest_len]
    if len({c[1] for c in longest_matches}) > 1:
        raise SystemExit(
            f"ambiguous slug-suffix transitions for {record_id!r}: "
            f"multiple equal-length suffixes match different new ids: {sorted({c[1] for c in longest_matches})!r}. "
            "Resolve by hand."
        )
    return longest_matches[0][1]


# ---------------------------------------------------------------------------
# Phase 4 — migration event + reindex + version bump
# ---------------------------------------------------------------------------


def phase_4_finalize(repo: Path, operator_id: str, plan: MigrationPlan) -> str:
    """Emit the migration event, reindex, bump version. Returns the event id."""
    ts = now_iso()
    event = _emit_migration_event(repo, operator_id, ts, plan)
    write_all(repo)
    # Last write — the version bump is the idempotency anchor for re-runs.
    atomic_write_text(dot8os(repo) / "version", TARGET_VERSION + "\n")
    return event["event_id"]


def _emit_migration_event(repo: Path, operator_id: str, ts: str, plan: MigrationPlan) -> dict[str, Any]:
    """Compose and append the tier 3 migration event.

    Stable schema for resolution.structured (refinement 3 — versioned for
    future audit tooling):

        {
            "schema": "8os.migration.v1",
            "from_version": "0.1.0",
            "to_version": "0.2.0",
            "records_created": [<id>, ...],
            "records_removed": [<path>, ...],
            "records_rewritten": [{"id": <id>, "fields_changed": [<field>, ...]}, ...],
            "warnings": [{"record_id": <id-or-null>, "type": <kind>, "detail": <str>}, ...]
        }
    """
    structured = {
        "schema": "8os.migration.v1",
        "from_version": "0.1.0",
        "to_version": TARGET_VERSION,
        "records_created": sorted(plan.records_created),
        "records_removed": sorted(plan.records_removed),
        "records_rewritten": sorted(plan.records_rewritten, key=lambda r: r["id"]),
        "warnings": plan.warnings,
    }
    event = make_event(
        event_type="operation",
        ir_node_id="migration-v0.1-to-v0.2",
        ir_node_path_at_event="(migration)",
        resolver_id=KERNEL_BINARY_RESOLVER_ID,
        bridge_id=KERNEL_SELF_BRIDGE_ID,
        intention={
            "text": "Migrate v0.1.0 repo to v0.2.",
            "context_refs": [],
            "scope": "_ops",
            "depth": 0,
        },
        resolution={
            "text": (
                f"Migration completed: {len(plan.records_created)} records created, "
                f"{len(plan.records_removed)} files removed, "
                f"{len(plan.records_rewritten)} records rewritten, "
                f"{len(plan.warnings)} warnings."
            ),
            "structured": structured,
            "authority_level": "hard",
        },
        outcome="accepted",
        ts=ts,
    )
    append_jsonl_line(event_jsonl_path(repo, ts), event)
    return event


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def migrate(repo: Path, *, operator_id: str | None = None) -> dict[str, Any]:
    """Run the full migration. Returns a summary dict (the migration event payload)."""
    plan = MigrationPlan()
    op_id, already = phase_0_preflight(repo, operator_id, plan)
    if already:
        return {"already_migrated": True, "warnings": [], "records_created": [], "records_removed": [], "records_rewritten": []}
    # Ensure the kernel-category dirs exist before any phase writes into them.
    for cat in ("scope", "projection", "resolver", "bridge", "surrogate-lineage"):
        ensure_dir(kernel_category_dir(repo, cat))
    phase_1_structural(repo, op_id, plan)
    phase_2_vendored(repo, op_id, plan)
    phase_3_frontmatter(repo, plan)
    event_id = phase_4_finalize(repo, op_id, plan)
    return {
        "already_migrated": False,
        "event_id": event_id,
        "records_created": plan.records_created,
        "records_removed": plan.records_removed,
        "records_rewritten": plan.records_rewritten,
        "warnings": plan.warnings,
    }


def main() -> int:
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="Migrate 8OS repo from v0.1.0 to v0.2.")
    ap.add_argument("--repo", type=Path, default=Path.cwd(), help="repo root (default: cwd)")
    ap.add_argument("--operator-id", default=None, help="primary_operator_id; overrides bootstrap-inferred id")
    args = ap.parse_args()

    result = migrate(args.repo, operator_id=args.operator_id)
    if result["already_migrated"]:
        print(f"already at {TARGET_VERSION} — no-op")
        return 0
    print(f"created: {len(result['records_created'])}")
    print(f"removed: {len(result['records_removed'])}")
    print(f"rewrote: {len(result['records_rewritten'])}")
    print(f"warnings: {len(result['warnings'])}")
    for w in result["warnings"]:
        print(f"  [{w['type']}] {w.get('record_id') or '-'}: {w['detail']}")
    print(f"event: {result['event_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
