"""kernel.init — bootstrap a self-describing 8OS v1.0 kernel.

v0.2 §3 + §3.6 + v1.0 §3 + §4: init authors a fully populated `_kernel` scope
containing twelve vendored projection-definition (I, R)s (nine from v0.2 plus
three added in v1.0: `_kernel.prediction`, `_kernel.calibration-policy`,
`_kernel.calibration-policy-proposal`), four kernel-internal resolver (I, R)s
(three from v0.2 plus `kernel.voi` added in v1.0), two vendored bridges
(`kernel.self` for the kernel's *cogito*, `human-<operator>` for the human's
sovereignty per #NOKINGS), the `_kernel` scope declaration itself, and the
user-supplied primary scope declaration. A seed bootstrap (I, R) under the
user scope records the init event and proves the kernel can describe its own
bootstrap.

Authority foundations (v0.2 §2.4):
- The kernel binary observes itself running and authors `_kernel`-scope
  records through the `kernel.self` bridge.
- The human running init authors the user scope through their own identity
  bridge (`human-<primary-operator-id>`).
Both are real bridge crossings producing real provenance. Neither is a
magic exception. The two are co-equal foundations of the project's
authority graph.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

from .. import KERNEL_BINARY_RESOLVER_ID, __version__ as KERNEL_VERSION
from .._atomic import StagedFile, append_jsonl_line, atomic_write_text, commit_staged
from .._events import make_event
from .._frontmatter import IRRecord, serialize
from .._indexes import write_all
from .._paths import (
    KERNEL_CATEGORIES,
    dot8os,
    event_jsonl_path,
    events_dir,
    events_raw_dir,
    index_dir,
    ir_collapsed_path,
    ir_dir,
    kernel_category_dir,
    kernel_projections_dir,
    kernel_record_path,
    kernel_scope_dir,
    projections_dir,
    schemas_dir,
)
from .._time import now_iso
from .._validation import all_schema_filenames, load_schema
from .._yaml import dump_yaml
from ..errors import ALREADY_EXISTS, KERNEL_VERSION_MISMATCH, KernelError


BOOTSTRAP_SLUG = "000-bootstrap"
KERNEL_SCOPE_ID = "_kernel"
KERNEL_SELF_BRIDGE_ID = "kernel.self"


def run(payload: dict[str, Any]) -> dict[str, Any]:
    project_name = payload["project_name"]
    user_scope_id = payload["primary_scope_id"]
    operator = payload["primary_operator_id"]
    requested_version = payload["kernel_version"]

    if requested_version != KERNEL_VERSION:
        raise KernelError(
            KERNEL_VERSION_MISMATCH,
            f"requested kernel version {requested_version} does not match "
            f"this kernel binary version {KERNEL_VERSION}",
            input_field="kernel_version",
            offending_value=requested_version,
            suggested_action=f"use kernel_version {KERNEL_VERSION!r}",
        )

    repo = Path.cwd().resolve()
    version_path = dot8os(repo) / "version"

    # v1.0 §7.2: re-running init against an initialized repo is idempotent —
    # noop when the repo already matches the binary, upgrade-mode when the
    # binary is newer than the repo (folds in new vendored content without
    # touching existing user content).
    if version_path.exists():
        existing = version_path.read_text(encoding="utf-8").strip()
        if _version_tuple(existing) > _version_tuple(KERNEL_VERSION):
            raise KernelError(
                KERNEL_VERSION_MISMATCH,
                f"repo version {existing!r} is newer than kernel binary "
                f"version {KERNEL_VERSION!r}; cannot downgrade in place",
                input_field="kernel_version",
                offending_value=KERNEL_VERSION,
                suggested_action=(
                    f"upgrade the kernel binary to >= {existing}, or operate "
                    "on a different repo"
                ),
            )
        # Version equal or older. Single path: compute deltas, apply only
        # if any. Pure noop when nothing to do.
        return _run_upgrade(repo, existing_version=existing)

    ts = now_iso()
    human_bridge_id = f"human-{operator}"

    # ---- skeleton ----------------------------------------------------------
    _ensure_skeleton(repo)
    _vendor_schemas(repo)
    _vendor_projection_bodies(repo)

    # ---- bootstrap event (pre-allocate id so the bootstrap (I, R) refs it) -
    bootstrap_relpath = str(
        ir_collapsed_path(repo, user_scope_id, BOOTSTRAP_SLUG).relative_to(repo).as_posix()
    )
    event = make_event(
        event_type="operation",
        ir_node_id=BOOTSTRAP_SLUG,
        ir_node_path_at_event=bootstrap_relpath,
        resolver_id=KERNEL_SELF_BRIDGE_ID,
        bridge_id=KERNEL_SELF_BRIDGE_ID,
        intention={
            "text": (
                f"Initialize the 8OS v0.2 kernel for project {project_name!r} "
                f"at version {KERNEL_VERSION} with primary scope {user_scope_id!r} "
                f"and primary operator {operator!r}."
            ),
            "context_refs": [],
            "scope": user_scope_id,
            "depth": 0,
        },
        resolution={
            "text": f"Kernel v0.2 initialized at {ts}.",
            "structured": {
                "project_name": project_name,
                "primary_scope_id": user_scope_id,
                "primary_operator_id": operator,
                "kernel_version": KERNEL_VERSION,
                "vendored_bridges": [KERNEL_SELF_BRIDGE_ID, human_bridge_id],
                "vendored_projections": list(_VENDORED_PROJECTIONS.keys()),
                "vendored_resolvers": list(_KERNEL_INTERNAL_RESOLVERS.keys()),
            },
            "authority_level": "hard",
        },
        outcome="accepted",
        ts=ts,
    )
    event_id = event["event_id"]

    # ---- stage every foundational (I, R) ----------------------------------
    self_endpoint = _kernel_self_endpoint()

    staged: list[StagedFile] = []

    # 1. kernel.self bridge first — the cogito grounds itself by being
    #    written. Its existence is the first authority claim the kernel
    #    can make.
    staged.append(
        _stage_bridge(
            repo,
            bridge_id=KERNEL_SELF_BRIDGE_ID,
            display_name="Kernel Self-Observation Bridge (the cogito)",
            bridge_type="other",
            endpoint=self_endpoint,
            requires_authorization=False,
            scope_of_authority="persistent",
            cost_envelope={"clock_ms_max": 0, "coin_usd_max": 0, "carbon_g_max": 0},
            authored_by=KERNEL_SELF_BRIDGE_ID,
            authored_on=ts,
            authority_level="hard",
            body=(
                "The `kernel.self` bridge records the kernel binary's observations "
                "about its own state. The bridge endpoint encodes the kernel binary's "
                "identity (version, build identifier, checksum). This is the kernel's "
                "*cogito* — the existence claim that grounds the project's authority "
                "graph from the kernel side. See spec §2.4 and §3.4."
            ),
        )
    )

    # 2. _kernel scope (I, R), authored through kernel.self.
    staged.append(
        _stage_scope(
            repo,
            scope_id=KERNEL_SCOPE_ID,
            display_name="Kernel Configuration Scope",
            parent_scope=None,
            authored_by=KERNEL_SELF_BRIDGE_ID,
            authored_on=ts,
            authority_level="hard",
            body=(
                "The reserved kernel-configuration scope. Holds projection-definition, "
                "resolver, bridge, and surrogate-lineage (I, R)s for the kernel itself. "
                "Authoring requires `authority_level: hard`. See spec §1.4 and §2.3."
            ),
        )
    )

    # 3. The nine vendored projection-definition (I, R)s.
    for ptype, decl in _VENDORED_PROJECTIONS.items():
        staged.append(
            _stage_projection(
                repo,
                projection_id=ptype,
                display_name=decl["display_name"],
                authored_by=KERNEL_SELF_BRIDGE_ID,
                authored_on=ts,
                authority_level="hard",
                body=decl["body"],
            )
        )

    # 4. The three kernel-internal resolver (I, R)s.
    for rid, decl in _KERNEL_INTERNAL_RESOLVERS.items():
        staged.append(
            _stage_resolver(
                repo,
                resolver_id=rid,
                display_name=decl["display_name"],
                bridge=None,
                cost=decl["cost"],
                capability=decl["capability"],
                model_name=None,
                authored_by=KERNEL_SELF_BRIDGE_ID,
                authored_on=ts,
                authority_level="hard",
                body=decl["body"],
            )
        )

    # 5. human-<operator> bridge — the human's identity asserted as sovereign.
    staged.append(
        _stage_bridge(
            repo,
            bridge_id=human_bridge_id,
            display_name=f"Human Identity Bridge for {operator}",
            bridge_type="human",
            endpoint=operator,
            requires_authorization=False,
            scope_of_authority="persistent",
            cost_envelope={"clock_ms_max": 0, "coin_usd_max": 0, "carbon_g_max": 0},
            authored_by=KERNEL_SELF_BRIDGE_ID,
            authored_on=ts,
            authority_level="hard",
            body=(
                f"The identity bridge for human {operator!r}. The human's authority "
                "is grounded in their existence as the project's sovereign per "
                "#NOKINGS. This bridge is vendored at init by `kernel.self` so that "
                "the human's first authoring action — declaring the user scope — "
                "has a real bridge to author through. See spec §2.4 and §3.4."
            ),
        )
    )

    # 6. User scope (I, R), authored through the human bridge.
    staged.append(
        _stage_scope(
            repo,
            scope_id=user_scope_id,
            display_name=project_name,
            parent_scope=None,
            authored_by=human_bridge_id,
            authored_on=ts,
            authority_level="hard",
            body=(
                f"Primary user-content scope for project {project_name!r}. "
                f"Authored at init by {operator!r} through the {human_bridge_id!r} bridge."
            ),
        )
    )

    # 7. Bootstrap (I, R) under the user scope — the seed of user content,
    #    recording the init event itself.
    bootstrap_record = IRRecord(
        frontmatter={
            "id": BOOTSTRAP_SLUG,
            "kind": "ir-node",
            "tier": 1,
            "projection_types": [],
            "collapsed_summary": (
                f"Initialize the 8OS v0.2 kernel for project {project_name!r}."
            ),
            "expanded_into": None,
            "parent": None,
            "scope": user_scope_id,
            "depends_on": [],
            "visible_to": [user_scope_id],
            "resolved_at": ts,
            "valid_through": None,
            "revalidate_trigger": None,
            "status": "resolved",
            "resolver": KERNEL_BINARY_RESOLVER_ID,
            "resolution_event": event_id,
            "authored_by": human_bridge_id,
            "authored_on": ts,
            "authority_level": "hard",
            "authored_via": KERNEL_SELF_BRIDGE_ID,
            "supersedes": None,
            "superseded_by": None,
            "surrogate_of": None,
        },
        intention_text=(
            f"Initialize the 8OS kernel (codename ZORTZI, representation v0.2) for "
            f"project {project_name!r} at kernel version {KERNEL_VERSION}, with "
            f"primary scope {user_scope_id!r} and primary operator {operator!r}. "
            f"The kernel and the human are co-equal foundations of this project's "
            f"authority graph."
        ),
        resolution_text=(
            f"Kernel initialized at {ts}. The kernel observed its own start through "
            f"the {KERNEL_SELF_BRIDGE_ID!r} bridge and authored the `_kernel` scope, "
            f"nine vendored projection-definition (I, R)s, three kernel-internal "
            f"resolver (I, R)s, and the {human_bridge_id!r} identity bridge. The "
            f"human authored the {user_scope_id!r} user scope and this bootstrap "
            f"(I, R). Both authority chains terminate at self-grounding existence "
            f"claims. The kernel that describes its own bootstrap is the kernel "
            f"that works."
        ),
    )
    staged.append(StagedFile(ir_collapsed_path(repo, user_scope_id, BOOTSTRAP_SLUG),
                             content_text=serialize(bootstrap_record)))

    # ---- atomic commit -----------------------------------------------------
    commit_staged(staged)
    append_jsonl_line(event_jsonl_path(repo, ts), event)
    write_all(repo)

    return {
        "data": {
            "bootstrap_ir_id": BOOTSTRAP_SLUG,
            "bootstrap_path": bootstrap_relpath,
            "primary_scope_path": str(
                kernel_record_path(repo, "scope", user_scope_id).relative_to(repo).as_posix()
            ),
            "mode": "fresh",
            "previous_version": None,
            "kernel_version": KERNEL_VERSION,
        },
        "event_id": event_id,
        "indexes_updated": _all_index_names(),
    }


# ---- skeleton + vendoring helpers ------------------------------------------


def _ensure_skeleton(repo: Path) -> None:
    """Create every directory the kernel relies on, in canonical v0.2 layout."""
    for d in (
        dot8os(repo),
        projections_dir(repo),
        kernel_projections_dir(repo),
        events_dir(repo),
        events_raw_dir(repo),
        index_dir(repo),
        schemas_dir(repo),
        ir_dir(repo),
        kernel_scope_dir(repo),
    ):
        d.mkdir(parents=True, exist_ok=True)
    for cat in KERNEL_CATEGORIES:
        kernel_category_dir(repo, cat).mkdir(parents=True, exist_ok=True)
    atomic_write_text(dot8os(repo) / "version", KERNEL_VERSION + "\n")


def _vendor_schemas(repo: Path) -> None:
    """Copy every JSON schema shipped in eightos.schemas into .8os/sdk/schemas/."""
    target = schemas_dir(repo)
    for fname in all_schema_filenames():
        op_part, version_part, kind_part, _ = fname.rsplit(".", 3)
        version = int(version_part.removeprefix("v"))
        schema = load_schema(op_part, version, kind_part)
        atomic_write_text(
            target / fname,
            json.dumps(schema, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        )


def _vendor_projection_bodies(repo: Path) -> None:
    """Write the nine vendored projection body schemas to .8os/projections/_kernel/.

    These are the validation source for kernel-shipped projection types
    (resolution to OPEN-Q-014). Sealed at kernel ship; not editable post-clone.
    """
    base = kernel_projections_dir(repo)
    for ptype, decl in _VENDORED_PROJECTIONS.items():
        atomic_write_text(base / f"{ptype}.yml", dump_yaml(decl["vendored_body"]))


def _kernel_self_endpoint() -> dict[str, Any]:
    """Compute the kernel.self bridge endpoint — the binary's own identity."""
    package_marker = (
        f"eightos {KERNEL_VERSION} python {sys.version_info.major}."
        f"{sys.version_info.minor}.{sys.version_info.micro} on "
        f"{platform.system().lower()}"
    )
    checksum = hashlib.sha256(package_marker.encode("utf-8")).hexdigest()
    return {
        "version": KERNEL_VERSION,
        "build": platform.python_implementation().lower(),
        "checksum_sha256": checksum,
    }


def _all_index_names() -> list[str]:
    from .._indexes import INDEX_NAMES

    return list(INDEX_NAMES)


# ---- (I, R) staging helpers ------------------------------------------------


def _base_kernel_frontmatter(
    *,
    record_id: str,
    projection_type: str,
    summary: str,
    authored_by: str,
    authored_on: str,
    authority_level: str,
) -> dict[str, Any]:
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
        "resolved_at": authored_on,
        "valid_through": None,
        "revalidate_trigger": None,
        "status": "resolved",
        "resolver": KERNEL_BINARY_RESOLVER_ID,
        "resolution_event": None,
        "authored_by": authored_by,
        "authored_on": authored_on,
        "authority_level": authority_level,
        "authored_via": KERNEL_SELF_BRIDGE_ID,
        "supersedes": None,
        "superseded_by": None,
        "surrogate_of": None,
    }


def _stage_scope(
    repo: Path,
    *,
    scope_id: str,
    display_name: str,
    parent_scope: str | None,
    authored_by: str,
    authored_on: str,
    authority_level: str,
    body: str,
) -> StagedFile:
    fm = _base_kernel_frontmatter(
        record_id=scope_id,
        projection_type="_kernel.scope",
        summary=f"Scope declaration: {display_name}",
        authored_by=authored_by,
        authored_on=authored_on,
        authority_level=authority_level,
    )
    fm["parent_scope"] = parent_scope
    fm["authority_defaults"] = {"hard": [], "convention": [], "uncalibrated": []}
    fm["visibility_defaults"] = [scope_id]
    fm["display_name"] = display_name
    record = IRRecord(frontmatter=fm, intention_text=body, resolution_text=None)
    return StagedFile(
        kernel_record_path(repo, "scope", scope_id),
        content_text=serialize(record),
    )


def _stage_projection(
    repo: Path,
    *,
    projection_id: str,
    display_name: str,
    authored_by: str,
    authored_on: str,
    authority_level: str,
    body: str,
) -> StagedFile:
    fm = _base_kernel_frontmatter(
        record_id=projection_id,
        projection_type="_kernel.projection",
        summary=f"Projection definition: {display_name}",
        authored_by=authored_by,
        authored_on=authored_on,
        authority_level=authority_level,
    )
    fm["projection_id"] = projection_id
    fm["display_name"] = display_name
    fm["body_schema_ref"] = (
        f".8os/projections/_kernel/{projection_id}.yml"
    )
    record = IRRecord(frontmatter=fm, intention_text=body, resolution_text=None)
    return StagedFile(
        kernel_record_path(repo, "projection", projection_id),
        content_text=serialize(record),
    )


def _stage_resolver(
    repo: Path,
    *,
    resolver_id: str,
    display_name: str,
    bridge: str | None,
    cost: dict[str, Any],
    capability: dict[str, Any],
    model_name: str | None,
    authored_by: str,
    authored_on: str,
    authority_level: str,
    body: str,
) -> StagedFile:
    fm = _base_kernel_frontmatter(
        record_id=resolver_id,
        projection_type="_kernel.resolver",
        summary=f"Resolver: {display_name}",
        authored_by=authored_by,
        authored_on=authored_on,
        authority_level=authority_level,
    )
    fm["resolver_id"] = resolver_id
    fm["display_name"] = display_name
    fm["bridge"] = bridge
    fm["cost"] = cost
    fm["capability"] = capability
    fm["model_name"] = model_name
    record = IRRecord(frontmatter=fm, intention_text=body, resolution_text=None)
    return StagedFile(
        kernel_record_path(repo, "resolver", resolver_id),
        content_text=serialize(record),
    )


def _stage_bridge(
    repo: Path,
    *,
    bridge_id: str,
    display_name: str,
    bridge_type: str,
    endpoint: Any,
    requires_authorization: bool,
    scope_of_authority: str,
    cost_envelope: dict[str, Any],
    authored_by: str,
    authored_on: str,
    authority_level: str,
    body: str,
) -> StagedFile:
    fm = _base_kernel_frontmatter(
        record_id=bridge_id,
        projection_type="_kernel.bridge",
        summary=f"Bridge: {display_name}",
        authored_by=authored_by,
        authored_on=authored_on,
        authority_level=authority_level,
    )
    fm["bridge_id"] = bridge_id
    fm["display_name"] = display_name
    fm["bridge_type"] = bridge_type
    fm["endpoint"] = endpoint
    fm["requires_authorization"] = requires_authorization
    fm["scope_of_authority"] = scope_of_authority
    fm["cost_envelope"] = cost_envelope
    record = IRRecord(frontmatter=fm, intention_text=body, resolution_text=None)
    return StagedFile(
        kernel_record_path(repo, "bridge", bridge_id),
        content_text=serialize(record),
    )


# ---- the nine vendored projection types ------------------------------------


def _required(name: str, ptype: str, desc: str) -> dict[str, Any]:
    return {"name": name, "type": ptype, "description": desc}


_VENDORED_PROJECTIONS: dict[str, dict[str, Any]] = {
    "_kernel.scope": {
        "display_name": "Scope Declaration",
        "vendored_body": {
            "projection_id": "_kernel.scope",
            "filename_suffix": ".md",
            "body_shape": "free",
            "required_frontmatter": [
                _required("parent_scope", "string|null", "parent in the scope hierarchy"),
                _required("authority_defaults", "object", "default authority attribution per level"),
                _required("visibility_defaults", "array", "default visible_to for (I, R)s in this scope"),
            ],
            "optional_frontmatter": [
                _required("display_name", "string", "human-readable name"),
                _required("stakes_defaults", "object", "{false_positive_cost, false_negative_cost, reversibility, consequence_scope} — default stakes for intentions in this scope (v1.0 §2.2)"),
                _required("domain_default", "string", "default domain for (I, R)s in this scope; record-level domain overrides (v1.1 §4.3)"),
                _required("data_classification_default", "string", "default data_classification for (I, R)s in this scope; record-level data_classification overrides (v1.1 §4.2, Block 4.3)"),
            ],
            "spec_reference": "docs/spec/8OS-BLOCK-1-SPEC.md#3-1-_kernel-scope",
        },
        "body": (
            "Declares a scope. Per axiom 3, every (I, R) belongs to exactly one scope; "
            "scopes form a hierarchy with `parent_scope` linking child to parent. "
            "Authority is `hard` only — scope creation is a foundational decision. "
            "See spec §3.1."
        ),
    },
    "_kernel.projection": {
        "display_name": "Projection Definition",
        "vendored_body": {
            "projection_id": "_kernel.projection",
            "filename_suffix": ".md",
            "body_shape": "free",
            "required_frontmatter": [
                _required("projection_id", "string", "must equal the (I, R)'s id"),
                _required("display_name", "string", "human-readable name"),
            ],
            "optional_frontmatter": [
                _required("body_schema_ref", "string", "reference to the body schema YAML"),
            ],
            "spec_reference": "docs/spec/8OS-BLOCK-1-SPEC.md#3-2-_kernel-projection",
        },
        "body": (
            "Declares a projection type. Projection types are opaque labels the kernel "
            "uses to group (I, R)s into queryable categories and to drive frontmatter-"
            "extension validation per §2.1 and filename-suffix application per §2.2. "
            "See spec §3.2."
        ),
    },
    "_kernel.resolver": {
        "display_name": "Resolver Registration",
        "vendored_body": {
            "projection_id": "_kernel.resolver",
            "filename_suffix": ".md",
            "body_shape": "free",
            "required_frontmatter": [
                _required("resolver_id", "string", "must equal the (I, R)'s id"),
                _required("display_name", "string", "human-readable name"),
                _required("bridge", "string|null", "bridge id, or null for inside resolvers"),
                _required("cost", "object", "{clock_ms, coin_usd, carbon_g, currency}"),
                _required("capability", "object", "{<domain>: {sigma, pi, alpha, rho}}"),
            ],
            "optional_frontmatter": [
                _required("model_name", "string|null", "for LLM resolvers, the model id"),
                _required("cost_model", "string", "fixed|linear-in-depth; default fixed when absent (v1.0 §2.1). cost_model: piecewise is reserved but rejected at registration."),
                _required("cost_per_depth_unit", "object", "{clock_ms, coin_usd, carbon_g} — required when cost_model: linear-in-depth, ignored otherwise (v1.0 §2.1)"),
                _required("depth_grid", "object", "{shallow, medium, deep: <integer>} — coarse grid the selector picks from when cost_model: linear-in-depth (v1.0 §5.1)"),
            ],
            "spec_reference": "docs/spec/8OS-BLOCK-1-SPEC.md#3-3-_kernel-resolver",
        },
        "body": (
            "Registers a resolver with declared cost (Clock, Coin, Carbon — axiom 5) "
            "and capability (σ, π, α, ρ — axiom 5) vectors. Kernel-internal resolvers "
            "(`kernel.selector`, `kernel.gatekeeper`, `kernel.calibrator`) are vendored "
            "at init; user resolvers are added post-init via `kernel.ir.new` with "
            "`projection_types: [_kernel.resolver]`. See spec §3.3."
        ),
    },
    "_kernel.bridge": {
        "display_name": "Bridge Declaration",
        "vendored_body": {
            "projection_id": "_kernel.bridge",
            "filename_suffix": ".md",
            "body_shape": "free",
            "required_frontmatter": [
                _required("bridge_id", "string", "must equal the (I, R)'s id"),
                _required("display_name", "string", "human-readable name"),
                _required("bridge_type", "string", "api|human|simulation|script|sensor|other"),
                _required("requires_authorization", "boolean", "whether crossings require authorization"),
                _required("scope_of_authority", "string", "single|session|persistent"),
                _required("cost_envelope", "object", "{clock_ms_max, coin_usd_max, carbon_g_max}"),
            ],
            "optional_frontmatter": [
                _required("endpoint", "any", "URL, identity, or other endpoint payload"),
                _required("bridge_status", "string", "active|quarantined|deprecated|removed; defaults to active when absent. kernel.bridge.cross rejects crossings into bridges with bridge_status: quarantined per BLOCK-2.7-SPEC-CORRECTIONS Patch 4."),
            ],
            "spec_reference": "docs/spec/8OS-BLOCK-1-SPEC.md#3-4-_kernel-bridge",
        },
        "body": (
            "Declares an inside/outside bridge (axiom 0). Two bridges are vendored "
            "at init: `kernel.self` (the kernel's *cogito*) and `human-<operator>` "
            "(the human's sovereignty per #NOKINGS). Both are real bridges with real "
            "provenance — neither is a magic exception. See spec §2.4 and §3.4."
        ),
    },
    "_kernel.surrogate-lineage": {
        "display_name": "Surrogate Lineage",
        "vendored_body": {
            "projection_id": "_kernel.surrogate-lineage",
            "filename_suffix": ".md",
            "body_shape": "free",
            "required_frontmatter": [
                _required("surrogate_id", "string", "must equal the (I, R)'s id"),
                _required("surrogate_of", "string", "resolver this surrogate approximates"),
                _required("training_corpus", "object", "{start, end, event_count}"),
                _required("validation", "object", "{holdout_event_count, accuracy_metric, accuracy_value}"),
                _required("trained_on", "string", "ISO-8601 when training completed"),
                _required("trained_by", "string", "what trained the surrogate"),
            ],
            "optional_frontmatter": [],
            "spec_reference": "docs/spec/8OS-BLOCK-1-SPEC.md#3-5-_kernel-surrogate-lineage",
        },
        "body": (
            "Declares a surrogate resolver's lineage (axiom 7). Surrogates emerge "
            "from operational history — they are not bootstrapped. See spec §3.5."
        ),
    },
    "_kernel.tier3-event": {
        "display_name": "Tier 3 Event Pointer",
        "vendored_body": {
            "projection_id": "_kernel.tier3-event",
            "filename_suffix": ".md",
            "body_shape": "free",
            "required_frontmatter": [],
            "optional_frontmatter": [],
            "spec_reference": "docs/spec/8OS-BLOCK-1-SPEC.md#3-6-1-_kernel-tier3-event",
        },
        "body": (
            "Typed projection over tier 3 events written to .8os/events/. (I, R) "
            "records of this type are pointers to canonical events in JSONL streams. "
            "See spec §3.6.1."
        ),
    },
    "_kernel.authorization": {
        "display_name": "Authorization Record",
        "vendored_body": {
            "projection_id": "_kernel.authorization",
            "filename_suffix": ".md",
            "body_shape": "free",
            "required_frontmatter": [],
            "optional_frontmatter": [
                _required("authorizes", "object", "{bridge, for_ir, scope_of_authority, cost_ceiling} — present for bridge-cross authorizations (v0.2 shape)"),
                _required("authorized_action", "string", "bridge-cross|supersede-calibration-policy; default bridge-cross when absent (v1.0 §3.4 / Block 2.8 amendment)"),
                _required("authorized_subject", "any", "<ir-id> or [<ir-id>, ...] — required when authorized_action: supersede-calibration-policy"),
                _required("conditions", "array", "list of condition predicates the standing authorization checks against incoming proposals; absent for bridge-cross"),
            ],
            "spec_reference": "docs/spec/8OS-BLOCK-1-SPEC-v1.0.md#3-4-standing-authorizations",
        },
        "body": (
            "Records an authorization decision per axiom 6. Two shapes share this "
            "projection in v1.0: (1) bridge-cross authorizations issued by the "
            "gatekeeper when a bridge crossing requires authorization (v0.2 shape — "
            "carries `authorizes`); (2) standing authorizations for calibration-"
            "policy supersession (v1.0 §3.4 — carries `authorized_action`, "
            "`authorized_subject`, `conditions`). The kernel applies "
            "`authorized_action: bridge-cross` as default when absent for v0.2 "
            "backward compatibility. Block 2.8 spec amendment per question batch Q2."
        ),
    },
    "_kernel.resolver-selection": {
        "display_name": "Resolver Selection",
        "vendored_body": {
            "projection_id": "_kernel.resolver-selection",
            "filename_suffix": ".md",
            "body_shape": "free",
            "required_frontmatter": [
                _required("selection", "object", "{for_ir, domain, demands, selected_resolver_id, fitness_scores}"),
            ],
            "optional_frontmatter": [],
            "spec_reference": "docs/spec/8OS-BLOCK-1-SPEC.md#3-6-3-_kernel-resolver-selection",
        },
        "body": (
            "Records a selector decision when `kernel.selector.select` is invoked. "
            "See spec §3.6.3."
        ),
    },
    "_kernel.capability-update": {
        "display_name": "Capability Update",
        "vendored_body": {
            "projection_id": "_kernel.capability-update",
            "filename_suffix": ".md",
            "body_shape": "free",
            "required_frontmatter": [
                _required("capability_update", "object", "{resolver_id, previous, updated, corpus_summary}; v1.0 §3.5: previous and updated may carry cost-vector fields alongside σ/π/α/ρ"),
            ],
            "optional_frontmatter": [],
            "spec_reference": "docs/spec/8OS-BLOCK-1-SPEC.md#3-6-4-_kernel-capability-update",
        },
        "body": (
            "Records a calibration-driven update to a resolver's capability vector, "
            "produced by `kernel.calibrator`. v1.0 §3.5 extends the projection to "
            "also carry cost-vector updates — `previous_capabilities` and "
            "`updated_capabilities` (under the nested `capability_update` block) may "
            "include optional cost-vector fields alongside σ/π/α/ρ. See spec §3.6.4 "
            "and v1.0 §3.5."
        ),
    },
    "_kernel.prediction": {
        "display_name": "Prediction",
        "vendored_body": {
            "projection_id": "_kernel.prediction",
            "filename_suffix": ".prediction.md",
            "target_subdirectory": "_predictions",
            "body_shape": "free",
            "required_frontmatter": [
                _required("subject_intention", "string", "the intention (I, R) being predicted about"),
                _required("predicted_resolution", "any", "the predictor's claim about how the intention resolves"),
                _required("probability", "number|null", "predictor's reported confidence 0–1; null for uncalibrated predictors"),
                _required("predictor", "string", "resolver id of the predictor that produced this prediction"),
            ],
            "optional_frontmatter": [
                _required("predictor_calibration", "string|null", "optional reference to a more-specific _kernel.capability-update overriding the predictor's general calibration"),
            ],
            "spec_reference": "docs/spec/8OS-BLOCK-1-SPEC-v1.0.md#3-1-_kernel-prediction",
        },
        "body": (
            "Records a prediction about an intention's resolution, authored by a "
            "predictor resolver before (and possibly instead of, or alongside) the "
            "candidate ground-truth resolver runs. The prediction's `subject_intention` "
            "names the intention; the predictor's `probability` and `predicted_resolution` "
            "carry the prediction itself; `predictor` references the resolver that "
            "produced it. The prediction does not carry an escalation_cost field — "
            "VOI looks up the candidate ground-truth resolver's current cost at "
            "consultation time. See spec v1.0 §3.1 and §3.7."
        ),
    },
    "_kernel.calibration-policy": {
        "display_name": "Calibration Policy",
        "vendored_body": {
            "projection_id": "_kernel.calibration-policy",
            "filename_suffix": ".policy.md",
            "target_subdirectory": "_calibration-policies",
            "body_shape": "free",
            "required_frontmatter": [
                _required("policy_id", "string", "must equal the (I, R)'s id"),
                _required("applies_to_scope", "string", "scope this policy governs"),
                _required("predictor", "string", "resolver id of the predictor being calibrated"),
                _required("calibration_signal", "string", "ground_truth|proxy"),
                _required("holdout_rate", "number", "0–1 fraction of decisions sampled for calibration evidence"),
                _required("recalibration_trigger", "object", "{kind: count|time|drift-threshold, params: {...}}"),
            ],
            "optional_frontmatter": [
                _required("applies_to_domain", "string|null", "optional domain restriction within the scope"),
                _required("ground_truth_resolver", "string|null", "candidate ground-truth resolver; required when calibration_signal: ground_truth"),
                _required("proxy_specification", "object", "{kind: peer-agreement|supersession-rate|outcome-correlation|holdout-against-ensemble, params}; required when calibration_signal: proxy"),
                _required("ground_truth_timeout", "string|null", "ISO-8601 duration; how long to wait for actuals before falling back to proxy"),
            ],
            "spec_reference": "docs/spec/8OS-BLOCK-1-SPEC-v1.0.md#3-2-_kernel-calibration-policy",
        },
        "body": (
            "Declares, for a scope or domain, how the kernel invests in keeping its "
            "predictors honest. Specifies what predictor is being calibrated against "
            "what ground-truth resolver, when holdouts fire, when recalibration "
            "triggers, and what signal to fall back to when ground-truth is "
            "impractical (the muddy-puddle-or-distant-galaxy case per v1.0 §3.6). "
            "calibration_signal: ground_truth requires non-null ground_truth_resolver; "
            "calibration_signal: proxy requires proxy_specification (cross-field check "
            "applied at ir.new time). Authority: hard. See spec v1.0 §3.2 and §3.6."
        ),
    },
    "_kernel.calibration-policy-proposal": {
        "display_name": "Calibration Policy Proposal",
        "vendored_body": {
            "projection_id": "_kernel.calibration-policy-proposal",
            "filename_suffix": ".proposal.md",
            "target_subdirectory": "_calibration-proposals",
            "body_shape": "free",
            "required_frontmatter": [
                _required("proposal_id", "string", "must equal the (I, R)'s id"),
                _required("target_policy", "string", "calibration-policy id this proposal recommends superseding"),
                _required("proposed_changes", "object", "{<field>: <new-value>, ...}"),
                _required("evidence_summary", "object", "{observation_count, period_start, period_end, observed_calibration_error, ...}"),
                _required("proposed_by", "string", "resolver id of the calibrator that produced the proposal (always kernel.calibrator in v1.0)"),
                _required("proposed_on", "string", "ISO-8601 when the calibrator authored the proposal"),
                _required("proposal_status", "string", "pending|approved|rejected|superseded — namespaced per Block 2.7's discipline (v1.0 spec amendment Q1)"),
            ],
            "optional_frontmatter": [
                _required("effective_supersession", "string|null", "when proposal_status: approved, the (I, R) id of the actual supersession on the target policy"),
            ],
            "spec_reference": "docs/spec/8OS-BLOCK-1-SPEC-v1.0.md#3-3-_kernel-calibration-policy-proposal",
        },
        "body": (
            "Records the calibrator's proposal to update a calibration policy in "
            "response to observed evidence. Proposals are not effective; they queue "
            "as `proposal_status: pending` until standing authorization match (per §3.4) "
            "or runtime countersignature transitions them to `approved`, at which "
            "point the calibrator is dispatched to author the actual supersession on "
            "the target policy. Append-only discipline: status transitions are "
            "recorded by superseding the proposal with a new (I, R) carrying the new "
            "proposal_status; query the latest record in the supersession chain to "
            "get current status. See spec v1.0 §3.3 and §3.4. Block 2.8 spec "
            "amendment Q1: field renamed from `status` to `proposal_status` to avoid "
            "collision with base 8OS frontmatter `status`."
        ),
    },
    # v1.1 §7.2 (Block 4.7): role-based access control. Roles confer
    # permission tags to a list of holders. Referenced by policy conditions
    # (§7.3) and `visible_when` predicate `role:` leaves (§4.4). Hard
    # authority — role definitions bind access control across the project.
    "_kernel.role": {
        "display_name": "Role",
        "vendored_body": {
            "projection_id": "_kernel.role",
            "filename_suffix": ".role.md",
            "target_subdirectory": "_roles",
            "body_shape": "free",
            "required_frontmatter": [
                _required("role_id", "string", "must equal the (I, R)'s id"),
                _required("grants", "array", "non-empty list of permission-tag strings the role confers"),
                _required("holders", "array", "list of author strings holding the role; may be empty (an unfilled role)"),
            ],
            "optional_frontmatter": [],
            "spec_reference": "docs/spec/8OS-BLOCK-1-SPEC-v1_1.md#7-2-_kernel-role",
        },
        "body": (
            "Declares an access-control role. A role grants a list of permission "
            "tags to its holders; permission tags are application-defined opaque "
            "strings (common patterns: `<op-name>:scope=<scope-id>`, "
            "`policy.write:scope=<scope-id>`). Roles are referenced by policies "
            "(§7.3) and by `visible_when` predicates (§4.4). Authority: hard. "
            "See spec v1.1 §7.2 and §8.2."
        ),
    },
    # v1.1 §7.3 (Block 4.7): policy-as-content. Policies declare which ops
    # they gate, under what conditions, and what decision (allow / deny /
    # transform / defer / follow-up) they make. Hard authority — policies
    # bind kernel behavior across operations.
    "_kernel.policy": {
        "display_name": "Policy",
        "vendored_body": {
            "projection_id": "_kernel.policy",
            "filename_suffix": ".policy.md",
            "target_subdirectory": "_policies",
            "body_shape": "free",
            "required_frontmatter": [
                _required("policy_id", "string", "must equal the (I, R)'s id"),
                _required("applies_to_op", "array", "list of kernel operation names this policy gates"),
                _required("condition", "any", "inline predicate object (any/all/not over leaves) OR resolver id string"),
                _required("decision", "string", "allow|deny|transform|defer|follow-up — what the policy enacts when its condition matches"),
            ],
            "optional_frontmatter": [
                _required("applies_to_scope", "string|null", "scope restriction; null means all scopes"),
                _required("applies_to_classification", "string|null", "classification restriction; null means all classifications"),
                _required("transform_action", "any", "modification applied to op input/output when decision: transform"),
                _required("defer_to", "string|null", "role id authorized to override when decision: defer"),
                _required("follow_up_action", "any", "action queued after permitting the op when decision: follow-up"),
            ],
            "spec_reference": "docs/spec/8OS-BLOCK-1-SPEC-v1_1.md#7-3-_kernel-policy",
        },
        "body": (
            "Declares a policy that gates kernel operations. The condition can "
            "be an inline predicate (same language as `visible_when` per §4.4 — "
            "`any`/`all`/`not` over leaves; Block 4.7 implements caller-context-"
            "only semantics per Block 4.7 finding F-PRED) or a resolver "
            "reference (the kernel dispatches the resolver synchronously to "
            "obtain the decision per Block 4.7 Q-RESOLVER). When multiple "
            "policies match an op, the kernel evaluates in author order, "
            "short-circuits on the first deny, accumulates transforms and "
            "follow-ups. Authority: hard. See spec v1.1 §7.3 and §8."
        ),
    },
    # v1.1 §7.4 (Block 4.7): policy-evaluation cache. One record per
    # op-signature hash; cached evaluations are reused when valid_through
    # has not elapsed and all consulted policies are still current.
    # Authority: convention (operation-output records).
    "_kernel.policy-evaluation": {
        "display_name": "Policy Evaluation",
        "vendored_body": {
            "projection_id": "_kernel.policy-evaluation",
            "filename_suffix": ".md",
            "body_shape": "free",
            "required_frontmatter": [
                _required("evaluation_id", "string", "must equal the (I, R)'s id"),
                _required("op_signature", "string", "hash of op_name + canonical op input + canonical caller context (Block 4.7 Q-NEW-4)"),
                _required("policies_consulted", "array", "list of policy ids that were evaluated, in author order"),
                _required("decision", "string", "combined decision: allow|deny|transform|defer|follow-up"),
                _required("evaluated_at", "string", "ISO-8601 when the evaluation occurred"),
            ],
            "optional_frontmatter": [
                _required("transform_actions", "array", "accumulated transform actions"),
                _required("follow_up_actions", "array", "accumulated follow-up actions"),
                _required("defer_to_role", "string|null", "deferred-to role when decision: defer"),
            ],
            "spec_reference": "docs/spec/8OS-BLOCK-1-SPEC-v1_1.md#7-4-_kernel-policy-evaluation",
        },
        "body": (
            "Caches the result of a policy evaluation. Keyed by an "
            "`op_signature` hash incorporating the op name, the canonical "
            "JSON serialization of the op input, and the canonical "
            "serialization of the caller context (caller_id, caller_scope, "
            "caller_roles, caller_authority_level, caller_data_classification_at_most). "
            "Caller context is included in the hash because policy decisions "
            "may reference caller-identity leaves (per Block 4.7 Q-NEW-4). "
            "Cached evaluations are valid iff `valid_through` has not elapsed "
            "AND all `policies_consulted` are still in status open or "
            "resolved (Block 4.7 implements eager invalidation: when a "
            "policy is superseded, evaluations citing it have their "
            "`valid_through` set to expired). Authority: convention. "
            "See spec v1.1 §7.4 and §8.5."
        ),
    },
    # v1.1 §7.1 (Block 4.8): lease coordination primitive. A lease declares
    # that a specific holder (factory id, process id, or author string) has
    # acquired write rights against a specific scope or (I, R) for a bounded
    # time window. Other writers respect the lease via op_pipeline.py's
    # phase-2 lease check. Authority: convention (coordination state, not
    # sovereignty-shaped). Lifecycle: leases expire automatically at
    # `valid_through` (axiom 4); explicit release via supersession is
    # optional. ID-uniqueness invariant prevents two factories from
    # acquiring the same target's lease simultaneously.
    "_kernel.lease": {
        "display_name": "Lease",
        "vendored_body": {
            "projection_id": "_kernel.lease",
            "filename_suffix": ".lease.md",
            "target_subdirectory": "_leases",
            "body_shape": "free",
            "required_frontmatter": [
                _required("lease_id", "string", "must equal the (I, R)'s id"),
                _required("lease_for", "string", "scope-id or (I, R) id the lease covers"),
                _required("held_by", "string", "factory:<factory-id> | process:<process-id> | author:<author-string>"),
                _required("lease_purpose", "string", "write|read|exclusive|shared — kernel enforces write and exclusive; read and shared are coordination metadata"),
                _required("acquired_at", "string", "ISO-8601 when the lease was acquired"),
            ],
            "optional_frontmatter": [],
            "spec_reference": "docs/spec/8OS-BLOCK-1-SPEC-v1_1.md#7-1-_kernel-lease",
        },
        "body": (
            "Declares a multi-writer coordination claim. Acquired by authoring "
            "this projection type via `kernel.ir.new`; checked by every write op "
            "in op_pipeline.py phase 2; rejected with `LEASE_HELD` when an active "
            "lease held by another writer covers the target scope or (I, R). "
            "Expires automatically when `valid_through` (axiom-4 base field) "
            "elapses; explicit release via supersession is optional — kernel "
            "treats expired leases as released. `lease_for` may name a scope "
            "(locks all (I, R)s in it) or a specific (I, R) id (locks one "
            "record); kernel walks parent scopes during conflict detection. "
            "See spec v1.1 §7.1, §13.3-13.5, §8.6 phase 2."
        ),
    },
}


# ---- the three kernel-internal resolvers -----------------------------------


def _vendored_cost(declared_clock: float = 0, declared_coin: float = 0) -> dict[str, Any]:
    return {
        "clock_ms": declared_clock,
        "coin_usd": declared_coin,
        "carbon_g": 0,
        "currency": "USD",
    }


def _vendored_capability(domain: str) -> dict[str, Any]:
    return {
        domain: {
            "sigma": {"declared": 0.9, "measured": None},
            "pi": {"declared": 0.9, "measured": None},
            "alpha": {"declared": 1.0, "measured": None},
            "rho": {"declared": 0.95, "measured": None},
        }
    }


_KERNEL_INTERNAL_RESOLVERS: dict[str, dict[str, Any]] = {
    "kernel.selector": {
        "display_name": "Kernel Selector",
        "cost": _vendored_cost(),
        "capability": _vendored_capability("kernel/selection"),
        "body": (
            "The kernel-internal resolver responsible for selecting other resolvers "
            "to bind to (I, R)s per axiom 5. Vendored at init. The selector itself "
            "is an (I, R) of `_kernel.resolver` projection type."
        ),
    },
    "kernel.gatekeeper": {
        "display_name": "Kernel Gatekeeper",
        "cost": _vendored_cost(),
        "capability": _vendored_capability("kernel/authorization"),
        "body": (
            "The kernel-internal resolver responsible for evaluating bridge crossing "
            "authorizations per axiom 6. Vendored at init."
        ),
    },
    "kernel.calibrator": {
        "display_name": "Kernel Calibrator",
        "cost": _vendored_cost(),
        "capability": _vendored_capability("kernel/calibration"),
        "body": (
            "The kernel-internal resolver responsible for updating other resolvers' "
            "measured capability and cost vectors based on tier 3 event aggregation "
            "per axiom 5. v1.0 §3.5 extends the calibrator to also author "
            "_kernel.calibration-policy-proposal records when accumulated evidence "
            "suggests a policy change is warranted, and to author the actual "
            "supersession on a policy after the proposal attains approved status "
            "(via standing authorization match or runtime countersignature). "
            "Capability- and cost-vector updates remain calibrator-authority alone; "
            "policy supersessions require sovereign approval. Vendored at init."
        ),
    },
    "kernel.voi": {
        "display_name": "Kernel Value-of-Information",
        "cost": {
            "clock_ms": 1,
            "coin_usd": 0,
            "carbon_g": 0,
            "currency": "USD",
        },
        "capability": {
            "kernel/voi": {
                "sigma": {"declared": 1.0, "measured": None},
                "pi": {"declared": 1.0, "measured": None},
                "alpha": {"declared": 1.0, "measured": None},
                "rho": {"declared": 1.0, "measured": None},
            },
        },
        "body": (
            "The kernel-internal resolver that computes the expected value of "
            "escalation given a prediction, a candidate ground-truth resolver, "
            "and stakes (v1.0 §4). Pure inside resolver, near-zero cost, "
            "deterministic given inputs. Stakes-unknown defaults to "
            "`escalate-directly` per §3.7 — the kernel's expression of epistemic "
            "humility: in the absence of information that would justify "
            "economizing on authority, defer to the more authoritative source. "
            "VOI's recommendations may later be refined by the calibrator if "
            "they are observed to diverge from sovereign judgment. Reference math "
            "documented in `eightos.voi`'s module docstring."
        ),
    },
}


# ---- v1.0 §7.2 upgrade-mode ------------------------------------------------


def _run_upgrade(repo: Path, *, existing_version: str) -> dict[str, Any]:
    """Bring an initialized repo's state up to the binary's current declarations.

    Three sub-cases (all routed through this same function):

    - Version mismatch (binary > existing): add net-new vendored content,
      refresh changed bodies, emit upgrade event, bump `.8os/version`. Mode
      `upgrade`.
    - Version match, deltas detected: only refresh changed bodies (binary
      owns vendored bodies across versions, so they may need to update for
      same-version additive amendments). Emit a refresh event. Mode
      `refresh`. No version bump (already current).
    - Version match, no deltas: pure noop. No event, no work, no writes.
      Mode `noop`.

    Discipline:
    - User-scope content untouched. The bootstrap (I, R), human bridges,
      and any user (I, R)s are never written by this function.
    - Vendored projection-definition (I, R)s and kernel-internal resolver
      (I, R)s are skip-if-exists (never overwritten).
    - Vendored projection bodies (.8os/projections/_kernel/*.yml) are
      always rewritten when their content differs from the binary's
      current declarations — the seal is against user edits, not binary
      upgrades.
    - At most one tier 3 event per call, in `_ops`, authored through
      `kernel.self`. Last write is `.8os/version` when the version
      changes (idempotency anchor).
    """
    ts = now_iso()
    user_scope = _existing_user_scope(repo)
    version_changes = existing_version != KERNEL_VERSION

    # 1. Vendored projection bodies. Sealed against user edits; the binary
    #    owns them across versions. Write missing → "added". Existing-but-
    #    differing → "refreshed" (covers additive field amendments like
    #    Block 2.8's _kernel.authorization extension and v1.0 optional
    #    fields on _kernel.resolver / _kernel.scope). Existing-and-same →
    #    no write.
    bodies_added: list[str] = []
    bodies_refreshed: list[str] = []
    body_dir = kernel_projections_dir(repo)
    body_dir.mkdir(parents=True, exist_ok=True)
    for ptype, decl in _VENDORED_PROJECTIONS.items():
        target = body_dir / f"{ptype}.yml"
        new_text = dump_yaml(decl["vendored_body"])
        if target.exists():
            if target.read_text(encoding="utf-8") == new_text:
                continue
            atomic_write_text(target, new_text)
            bodies_refreshed.append(ptype)
        else:
            atomic_write_text(target, new_text)
            bodies_added.append(ptype)

    # 2. Projection-definition (I, R)s — stage missing only.
    staged: list[StagedFile] = []
    projections_added: list[str] = []
    for ptype, decl in _VENDORED_PROJECTIONS.items():
        target = kernel_record_path(repo, "projection", ptype)
        if target.exists():
            continue
        staged.append(
            _stage_projection(
                repo,
                projection_id=ptype,
                display_name=decl["display_name"],
                authored_by=KERNEL_SELF_BRIDGE_ID,
                authored_on=ts,
                authority_level="hard",
                body=decl["body"],
            )
        )
        projections_added.append(ptype)

    # 3. Kernel-internal resolver (I, R)s — stage missing only.
    resolvers_added: list[str] = []
    for rid, decl in _KERNEL_INTERNAL_RESOLVERS.items():
        target = kernel_record_path(repo, "resolver", rid)
        if target.exists():
            continue
        staged.append(
            _stage_resolver(
                repo,
                resolver_id=rid,
                display_name=decl["display_name"],
                bridge=None,
                cost=decl["cost"],
                capability=decl["capability"],
                model_name=None,
                authored_by=KERNEL_SELF_BRIDGE_ID,
                authored_on=ts,
                authority_level="hard",
                body=decl["body"],
            )
        )
        resolvers_added.append(rid)

    has_deltas = bool(
        bodies_added or bodies_refreshed or projections_added or resolvers_added
    )
    bootstrap_relpath = str(
        ir_collapsed_path(repo, user_scope, BOOTSTRAP_SLUG).relative_to(repo).as_posix()
    )

    # Pure noop: version already matches, nothing to write.
    if not version_changes and not has_deltas:
        return {
            "data": {
                "bootstrap_ir_id": BOOTSTRAP_SLUG,
                "bootstrap_path": bootstrap_relpath,
                "primary_scope_path": str(
                    kernel_record_path(repo, "scope", user_scope).relative_to(repo).as_posix()
                ),
                "mode": "noop",
                "previous_version": existing_version,
                "kernel_version": KERNEL_VERSION,
                "added": {
                    "vendored_projection_bodies": [],
                    "projection_definitions": [],
                    "kernel_internal_resolvers": [],
                },
                "refreshed": {
                    "vendored_projection_bodies": [],
                },
            },
            "event_id": None,
            "indexes_updated": [],
        }

    mode = "upgrade" if version_changes else "refresh"

    # 4. Tier 3 event — one per init call that did work, in _ops, authored
    #    through kernel.self.
    event_intention_text = (
        f"Upgrade 8OS kernel state from v{existing_version} to "
        f"v{KERNEL_VERSION} per v1.0 §7.2. Fold in net-new vendored "
        "content and refresh changed bodies; preserve all existing "
        "(I, R)s, bridges, and user content."
        if version_changes
        else (
            f"Refresh vendored projection bodies at v{KERNEL_VERSION} to "
            "match current binary declarations. No version change; bodies "
            "are sealed against user edits but binary owns them."
        )
    )
    event_resolution_text = (
        f"Added {len(bodies_added)} projection bodies "
        f"(refreshed {len(bodies_refreshed)}), "
        f"{len(projections_added)} projection-definition (I, R)s, "
        f"{len(resolvers_added)} kernel-internal resolver (I, R)s."
        + (f" Updated .8os/version to {KERNEL_VERSION}." if version_changes else "")
    )
    event = make_event(
        event_type="operation",
        ir_node_id=f"{mode}-{_compact_ts(ts)}",
        ir_node_path_at_event="",  # no (I, R) pointer for these events
        resolver_id=KERNEL_BINARY_RESOLVER_ID,
        bridge_id=KERNEL_SELF_BRIDGE_ID,
        intention={
            "text": event_intention_text,
            "context_refs": [],
            "scope": OPS_SCOPE,
            "depth": 0,
        },
        resolution={
            "text": event_resolution_text,
            "structured": {
                "previous_version": existing_version,
                "new_version": KERNEL_VERSION,
                "mode": mode,
                "vendored_projection_bodies_added": bodies_added,
                "vendored_projection_bodies_refreshed": bodies_refreshed,
                "projection_definitions_added": projections_added,
                "kernel_internal_resolvers_added": resolvers_added,
            },
            "authority_level": "hard",
        },
        outcome="accepted",
        ts=ts,
    )

    # 5. Commit, append, reindex; bump version only on actual upgrade.
    if staged:
        commit_staged(staged)
    append_jsonl_line(event_jsonl_path(repo, ts), event)
    write_all(repo)
    if version_changes:
        atomic_write_text(dot8os(repo) / "version", KERNEL_VERSION + "\n")

    return {
        "data": {
            "bootstrap_ir_id": BOOTSTRAP_SLUG,
            "bootstrap_path": bootstrap_relpath,
            "primary_scope_path": str(
                kernel_record_path(repo, "scope", user_scope).relative_to(repo).as_posix()
            ),
            "mode": mode,
            "previous_version": existing_version,
            "kernel_version": KERNEL_VERSION,
            "added": {
                "vendored_projection_bodies": bodies_added,
                "projection_definitions": projections_added,
                "kernel_internal_resolvers": resolvers_added,
            },
            "refreshed": {
                "vendored_projection_bodies": bodies_refreshed,
            },
        },
        "event_id": event["event_id"],
        "indexes_updated": _all_index_names(),
    }


def _existing_user_scope(repo: Path) -> str:
    """Identify the user scope of an initialized repo by reading
    `ir/_kernel/scope/<id>.md` records and returning the one that isn't
    `_kernel` itself."""
    scope_dir = kernel_category_dir(repo, "scope")
    if not scope_dir.exists():
        raise KernelError(
            ALREADY_EXISTS,
            f"initialized repo at {repo} has no ir/_kernel/scope/ directory",
            offending_value=str(scope_dir),
        )
    for md in sorted(scope_dir.glob("*.md")):
        scope_id = md.stem
        if scope_id != KERNEL_SCOPE_ID:
            return scope_id
    raise KernelError(
        ALREADY_EXISTS,
        f"initialized repo at {repo} has no user scope under ir/_kernel/scope/",
        offending_value=str(scope_dir),
    )


def _version_tuple(version: str) -> tuple[int, ...]:
    """Parse `MAJOR.MINOR.PATCH[-pre]` into a comparable tuple.

    Pre-release tags (e.g., `1.0.1-partial`, `1.0.2-dev.1`) compare equal at
    the numeric component for upgrade-mode purposes; the per-version-identity
    invariant from v1.0.1-partial Amendment 3 is enforced by string equality
    elsewhere. Pre-release suffixes lower-bound the numeric tuple so the
    `existing > KERNEL_VERSION` downgrade check remains conservative.
    """
    base = version.split("-", 1)[0]
    return tuple(int(p) for p in base.split("."))


def _compact_ts(ts: str) -> str:
    """ISO timestamp → slug-safe compact form (mirrors selector_op._compact_ts)."""
    return ts.replace(":", "").replace("-", "").replace(".", "").rstrip("Z").lower()


OPS_SCOPE = "_ops"
