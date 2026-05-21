"""Projection registry and validation (v0.2 §2.1, §2.2, §3).

Two sources of truth at runtime:

- Vendored body schemas at `.8os/projections/_kernel/<type>.yml` — sealed at
  kernel ship; read directly during bootstrap before the projection-to-ids
  index exists. These are the canonical validation source for kernel-shipped
  projection types per the resolution to OPEN-Q-014.

- Projection-definition (I, R)s at `ir/_kernel/projection/<type>.md` — the
  queryable record of the projection's existence, with frontmatter carrying
  provenance / authority and a body that mirrors (or extends, for user-declared
  projections) the vendored body shape.

For user-declared projections (e.g., prism-ir), the body of the (I, R) IS
the body schema; there is no separate vendored YAML. For kernel-shipped
projections (`_kernel.*`), the (I, R) body is descriptive and the vendored
YAML is authoritative.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._frontmatter import parse_file
from ._paths import kernel_category_dir, kernel_projections_dir
from ._yaml import load_yaml, load_yaml_file
from .errors import (
    CONFLICTING_PROJECTION_TARGETS,
    KernelError,
    NOT_FOUND,
    SCHEMA_INVALID,
)

# Base 8OS frontmatter field names (v0.1 §2, extended in v1.0 §2.3).
# Projection extensions may not collide with these.
BASE_FRONTMATTER_FIELDS: frozenset[str] = frozenset({
    "id",
    "kind",
    "tier",
    "projection_types",
    "collapsed_summary",
    "expanded_into",
    "parent",
    "scope",
    "depends_on",
    "visible_to",
    "resolved_at",
    "valid_through",
    "revalidate_trigger",
    "status",
    "resolver",
    "resolution_event",
    "authored_by",
    "authored_on",
    "authority_level",
    "authored_via",
    "supersedes",
    "superseded_by",
    "surrogate_of",
    # v1.0 §2.3: stakes is an optional base field. Absent or null means
    # "stakes unknown for this intention"; VOI's response under stakes-unknown
    # is escalate-directly (v1.0 §3.7).
    "stakes",
    # v1.1 §4.3: domain is an optional base field, lifted from extension-only
    # in Block 4.1 (closes OPEN-Q-019). Absent on a record falls back to the
    # scope's domain_default; null at both levels means "no domain" and
    # domain-scoped policies do not match.
    "domain",
    # v1.1 §4.2: data_classification is an optional base field added in
    # Block 4.3. Application-declared opaque string; the kernel does not
    # interpret the value. Absent or null falls back to the scope's
    # data_classification_default; classification-based policy gating (v1.1
    # §8) plugs in at kernel.ir.new and kernel.ir.resolve when the policy
    # machinery lands.
    "data_classification",
    # v1.1 §4.4 (Block 4.4): visible_when is an optional base field carrying
    # a structured predicate (object|null) the kernel evaluates at every
    # read op (get/list/deps). Hard-authored records only — convention- or
    # uncalibrated-authored records carrying the field reject as
    # VISIBILITY_PREDICATE_NOT_PERMITTED. See `src/eightos/predicates.py`
    # for the predicate AST and evaluator.
    "visible_when",
})


def load_projection_body(repo: Path, projection_type: str) -> dict[str, Any]:
    """Return the body content (schema declarations) for a projection type.

    Resolution order:
    1. Vendored body at `.8os/projections/_kernel/<type>.yml` (kernel-shipped).
    2. Body of the projection-definition (I, R) at `ir/_kernel/projection/<type>.md`
       (user-declared).

    Raises NOT_FOUND if neither source exists.
    """
    vendored = kernel_projections_dir(repo) / f"{projection_type}.yml"
    if vendored.exists():
        doc = load_yaml_file(vendored) or {}
        return doc

    record_path = kernel_category_dir(repo, "projection") / f"{projection_type}.md"
    if record_path.exists():
        rec = parse_file(record_path)
        body = _extract_yaml_body(rec.intention_text + ("\n" + (rec.resolution_text or "")))
        if body is None:
            return {}
        return body

    raise KernelError(
        NOT_FOUND,
        f"projection type {projection_type!r} not found "
        f"(checked {vendored.relative_to(repo)} and {record_path.relative_to(repo)})",
        input_field="projection_types",
        offending_value=projection_type,
    )


def _extract_yaml_body(text: str) -> dict[str, Any] | None:
    """Extract the first ```yaml fenced block from a markdown body; return parsed dict or None."""
    lines = text.splitlines()
    in_fence = False
    fence_lines: list[str] = []
    for ln in lines:
        stripped = ln.strip()
        if not in_fence and stripped in ("```yaml", "```yml"):
            in_fence = True
            continue
        if in_fence and stripped == "```":
            break
        if in_fence:
            fence_lines.append(ln)
    if not fence_lines:
        return None
    parsed = load_yaml("\n".join(fence_lines))
    return parsed if isinstance(parsed, dict) else None


def required_frontmatter_for(repo: Path, projection_types: list[str]) -> dict[str, dict[str, Any]]:
    """Union of required frontmatter declarations across the listed projections.

    Returns {field_name: {type, description, source_projection}}. Detects
    cross-projection collisions and raises SCHEMA_INVALID. Detects collisions
    with base 8OS frontmatter field names and raises SCHEMA_INVALID.
    """
    out: dict[str, dict[str, Any]] = {}
    for ptype in projection_types:
        body = load_projection_body(repo, ptype)
        for field in (body.get("required_frontmatter") or []):
            if not isinstance(field, dict):
                continue
            name = field.get("name")
            if not name:
                continue
            if name in BASE_FRONTMATTER_FIELDS:
                raise KernelError(
                    SCHEMA_INVALID,
                    f"projection {ptype!r} declares required field {name!r} which "
                    "collides with a base 8OS frontmatter field",
                    input_field="projection_types",
                    offending_value=ptype,
                )
            if name in out and out[name]["source_projection"] != ptype:
                raise KernelError(
                    SCHEMA_INVALID,
                    f"projections {out[name]['source_projection']!r} and {ptype!r} "
                    f"both declare required field {name!r}",
                    input_field="projection_types",
                )
            out[name] = {
                "type": field.get("type", "any"),
                "description": field.get("description", ""),
                "source_projection": ptype,
            }
    return out


def filename_suffix_for(repo: Path, projection_types: list[str]) -> str:
    """Resolve the on-disk filename suffix for an (I, R) of these projection types.

    Default `.md`. If multiple projections declare conflicting non-default
    suffixes, raises SCHEMA_INVALID. If exactly one non-default suffix is
    declared, returns it.
    """
    suffix: str | None = None
    source: str | None = None
    for ptype in projection_types:
        body = load_projection_body(repo, ptype)
        declared = body.get("filename_suffix")
        if not declared or declared == ".md":
            continue
        if suffix is None:
            suffix = declared
            source = ptype
        elif suffix != declared:
            raise KernelError(
                SCHEMA_INVALID,
                f"projections {source!r} (suffix {suffix!r}) and {ptype!r} "
                f"(suffix {declared!r}) declare conflicting filename suffixes",
                input_field="projection_types",
            )
    return suffix or ".md"


def target_subdirectory_for(repo: Path, projection_types: list[str]) -> str | None:
    """v1.0.1-partial Amendment 1: resolve the projection-declared subdirectory
    under ir/<scope>/ where (I, R)s of these projection_types live.

    Returns None when no projection declares a `target_subdirectory:` field
    (records go flat under `ir/<scope>/`). Returns the declared name when
    exactly one projection declares it. Raises CONFLICTING_PROJECTION_TARGETS
    when multiple projection_types declare conflicting non-empty values.
    """
    chosen: str | None = None
    source: str | None = None
    for ptype in projection_types:
        body = load_projection_body(repo, ptype)
        declared = body.get("target_subdirectory")
        if not declared:
            continue
        if not isinstance(declared, str):
            raise KernelError(
                SCHEMA_INVALID,
                f"projection {ptype!r} declares non-string target_subdirectory: "
                f"{declared!r}",
                input_field="projection_types",
                offending_value=ptype,
            )
        if chosen is None:
            chosen = declared
            source = ptype
        elif chosen != declared:
            raise KernelError(
                CONFLICTING_PROJECTION_TARGETS,
                f"projections {source!r} (target_subdirectory {chosen!r}) and "
                f"{ptype!r} (target_subdirectory {declared!r}) declare "
                f"conflicting target_subdirectory values",
                input_field="projection_types",
            )
    return chosen


def validate_extensions(
    repo: Path, projection_types: list[str], extensions: dict[str, Any]
) -> dict[str, Any]:
    """Validate the supplied frontmatter_extensions against projection-declared requirements.

    Returns the validated extensions dict (possibly augmented or normalized).
    Raises SCHEMA_INVALID on missing-required, unknown-field, or type-mismatch.
    """
    required = required_frontmatter_for(repo, projection_types)
    optional: dict[str, dict[str, Any]] = {}
    for ptype in projection_types:
        body = load_projection_body(repo, ptype)
        for field in (body.get("optional_frontmatter") or []):
            if not isinstance(field, dict):
                continue
            name = field.get("name")
            if not name or name in required or name in BASE_FRONTMATTER_FIELDS:
                continue
            optional[name] = {
                "type": field.get("type", "any"),
                "description": field.get("description", ""),
                "source_projection": ptype,
            }

    missing = [name for name in required if name not in extensions]
    if missing:
        raise KernelError(
            SCHEMA_INVALID,
            f"frontmatter_extensions missing required fields: {missing!r}",
            input_field="frontmatter_extensions",
            suggested_action=f"supply values for {missing!r} per projection requirements",
        )

    allowed = set(required) | set(optional)
    unknown = [k for k in extensions if k not in allowed]
    if unknown:
        raise KernelError(
            SCHEMA_INVALID,
            f"frontmatter_extensions includes fields not declared by any "
            f"projection in {projection_types!r}: {unknown!r}",
            input_field="frontmatter_extensions",
            offending_value=unknown,
        )

    return dict(extensions)
