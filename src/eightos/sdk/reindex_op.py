"""kernel.reindex — recompute or verify the kernel index set (Block 1 §7.6.2).

`mode: "rebuild"` writes every index; `mode: "check"` recomputes and compares.
On drift, raise INDEX_DRIFT with a structured `drift_diff` in context.

v1.2 (Block 5.0): mode value renamed `"full"` → `"rebuild"` per Block-1
§3.17 mode-name reconciliation (no deprecation alias; `mode: "full"` is
SCHEMA_INVALID against v1.2+ binaries). `mode: "rebuild"` now mandates a
tier-3 event recording the regeneration per axiom 8 (Reflexivity, kernel
spec v0.2). The recursion concern that previously kept rebuild silent is
resolved via a two-phase commit:

  phase 1 — call write_all to regenerate every index from records on disk.
            input_set_hash at this point excludes the rebuild event.
  phase 2 — emit the tier-3 rebuild event (event_type: "operation",
            resolver_id: "kernel", authored_via: kernel.self,
            authority_level: hard) recording the rebuild's outcome.
  phase 2b — call write_all a second time so the events-related indexes
             (resolver-to-events, _checksum) reflect the new event. The
             post-rebuild input_set_hash now includes the rebuild event.

A subsequent `mode: "check"` finds the indexes consistent because the
second write_all reflected the appended event. The rebuild claim is
itself an (I, R)-formed tier-3 event on the graph, satisfying axiom 8.
The cost of the two-phase pattern is O(2N) index writes per rebuild;
acceptable given rebuild is a maintenance op, not a hot path.

v1.0.1-partial Amendment 2: `mode: "check"` additionally validates that
every (I, R) record on disk carries a non-empty `authored_via` field.
Records lacking it are reported as schema violations.

v1.1 §4.3 (Block 4.1): `mode: "check"` additionally validates that any
record carrying a `domain` field has it set to a non-empty string. Records
lacking the field are accepted (domain is optional); records with empty
or non-string `domain` values are rejected as schema violations.

v1.1 §3.8 / §5.1 (Block 4.2): `mode: "check"` additionally validates
cancelled-state shape. A record with `status: cancelled` MUST carry
non-empty `cancelled_at` and `cancelled_by`. No record may have
`superseded_by: <cancelled-id>` — a cancelled record cannot be the
forward target of another record's supersession chain (the
`kernel.ir.new`-with-`supersedes:<cancelled-id>` path puts `supersedes`
on the new record, not `superseded_by` on the cancelled one).

v1.1 §4.2 (Block 4.3): `mode: "check"` additionally validates that any
record carrying a `data_classification` field has it set to a non-empty
string. Records lacking the field are accepted (data_classification is
optional); records with empty or non-string `data_classification` values
are rejected as schema violations. Same shape as the v1.1 §4.3 `domain`
validation introduced in Block 4.1.

v1.1 §4.4 (Block 4.4): `mode: "check"` additionally validates that any
record carrying a `visible_when` field has it shaped as a valid predicate
(per `eightos.predicates.validate_predicate`) and that the record's
authority_level is `hard` (defense-in-depth — the kernel.ir.new write
path enforces the same invariant, but a direct-edit drift would
otherwise let a non-hard record carry a predicate).
"""

from __future__ import annotations

from typing import Any

from .. import predicates
from .._atomic import append_jsonl_line
from .._events import make_event
from .._frontmatter import parse_file
from .._indexes import INDEX_NAMES, check_drift, input_set_hash, write_all
from .._paths import event_jsonl_path, ir_dir
from .._time import now_iso
from ..errors import INDEX_DRIFT, SCHEMA_INVALID, KernelError
from ._common import repo_root_or_raise


def run(payload: dict[str, Any]) -> dict[str, Any]:
    repo = repo_root_or_raise()
    mode = payload["mode"]

    if mode == "rebuild":
        # Phase 1: regenerate every index from records on disk.
        write_all(repo)
        pre_event_input_hash = input_set_hash(repo)

        # Phase 2: emit the tier-3 rebuild event (axiom 8 / kernel spec
        # v0.2). The event records the rebuild's outcome with the
        # input_set_hash computed before the event itself was appended,
        # which is the input set the indexes were actually rebuilt over.
        ts = now_iso()
        event = make_event(
            event_type="operation",
            ir_node_id="kernel.reindex",
            ir_node_path_at_event="<kernel-internal>",
            resolver_id="kernel",
            bridge_id="kernel.self",
            intention={
                "text": (
                    "kernel.reindex rebuild — assert indexes consistent "
                    "with records on disk"
                ),
                "context_refs": [],
                "scope": "_kernel",
                "depth": 0,
            },
            resolution={
                "text": f"All indexes regenerated at {ts}.",
                "structured": {
                    "mode": "rebuild",
                    "input_set_hash": pre_event_input_hash,
                    "indexes_written": len(INDEX_NAMES) + 1,
                },
                "authority_level": "hard",
            },
            outcome="accepted",
            ts=ts,
        )
        append_jsonl_line(event_jsonl_path(repo, ts), event)

        # Phase 2b: re-run write_all so the events-related indexes
        # (resolver-to-events, _checksum) and the on-disk input_set_hash
        # reflect the freshly appended event. After this call, a
        # subsequent mode:"check" finds the indexes consistent with the
        # records-plus-events-on-disk. Costs one additional write_all
        # pass; acceptable for a maintenance op.
        write_all(repo)

        return {
            "data": {
                "mode": "rebuild",
                "input_set_hash": input_set_hash(repo),
                "indexes_written": len(INDEX_NAMES) + 1,  # named indexes + _checksum
            },
            "event_id": event["event_id"],
            "indexes_updated": list(INDEX_NAMES),
        }

    # check mode
    missing = _records_missing_authored_via(repo)
    if missing:
        raise KernelError(
            SCHEMA_INVALID,
            f"{len(missing)} (I, R) record(s) lack `authored_via` "
            "(v1.0.1-partial Amendment 2 — mandatory base frontmatter)",
            input_field="authored_via",
            extra_context={"records_missing_authored_via": missing},
            suggested_action=(
                "run `python scripts/migrate-v1.0-to-v1.0.1-partial.py` "
                "to backfill, or supply authored_via on subsequent ir.new calls"
            ),
        )
    invalid_domain = _records_with_invalid_domain(repo)
    if invalid_domain:
        raise KernelError(
            SCHEMA_INVALID,
            f"{len(invalid_domain)} (I, R) record(s) carry a `domain` field "
            "with an invalid value (v1.1 §4.3 — when present, domain must be "
            "a non-empty string; use null or omit to indicate no domain)",
            input_field="domain",
            extra_context={"records_with_invalid_domain": invalid_domain},
            suggested_action=(
                "remove the `domain` field, set it to null, or supply a "
                "non-empty string"
            ),
        )
    invalid_classification = _records_with_invalid_data_classification(repo)
    if invalid_classification:
        raise KernelError(
            SCHEMA_INVALID,
            f"{len(invalid_classification)} (I, R) record(s) carry a "
            "`data_classification` field with an invalid value (v1.1 §4.2 — "
            "when present, data_classification must be a non-empty string; "
            "use null or omit to indicate no classification)",
            input_field="data_classification",
            extra_context={"records_with_invalid_data_classification": invalid_classification},
            suggested_action=(
                "remove the `data_classification` field, set it to null, or "
                "supply a non-empty string"
            ),
        )
    invalid_visible_when = _records_with_invalid_visible_when(repo)
    if invalid_visible_when:
        raise KernelError(
            SCHEMA_INVALID,
            f"{len(invalid_visible_when)} (I, R) record(s) have invalid "
            "visible_when state (v1.1 §4.4 — predicates must be well-formed "
            "per eightos.predicates.validate_predicate, and only hard-"
            "authority records may carry the field)",
            input_field="visible_when",
            extra_context={"records_with_invalid_visible_when": invalid_visible_when},
            suggested_action=(
                "fix the predicate shape or remove visible_when from non-"
                "hard records; re-author at hard authority if a visibility "
                "predicate is needed"
            ),
        )
    invalid_cancelled = _records_with_invalid_cancelled_state(repo)
    if invalid_cancelled:
        raise KernelError(
            SCHEMA_INVALID,
            f"{len(invalid_cancelled)} (I, R) record(s) have invalid "
            "cancelled-state shape (v1.1 §3.8 / §5.1 — cancelled records "
            "must carry non-empty cancelled_at and cancelled_by, and no "
            "record may have superseded_by pointing to a cancelled record)",
            input_field="status",
            extra_context={"records_with_invalid_cancelled_state": invalid_cancelled},
            suggested_action=(
                "for cancelled records lacking cancelled_at/cancelled_by, "
                "re-cancel through kernel.ir.cancel; for records pointing at "
                "a cancelled record via superseded_by, re-author with "
                "supersedes pointing the other way"
            ),
        )
    drift = check_drift(repo)
    if drift is not None:
        raise KernelError(
            INDEX_DRIFT,
            "committed indexes do not match a fresh recompute",
            axiom_violated=3,
            extra_context={"drift_diff": drift},
            suggested_action="run `8os reindex` with mode=rebuild and commit the result",
        )
    return {
        "data": {
            "mode": "check",
            "input_set_hash": input_set_hash(repo),
            "drift_detected": False,
        },
        "event_id": None,
        "indexes_updated": [],
    }


def _records_missing_authored_via(repo) -> list[str]:
    """Return relative paths of (I, R) records whose authored_via is missing/empty."""
    base = ir_dir(repo)
    out: list[str] = []
    if not base.exists():
        return out
    for md in sorted(base.rglob("*.md")):
        try:
            rec = parse_file(md)
        except Exception:
            continue
        value = rec.frontmatter.get("authored_via")
        if not isinstance(value, str) or not value.strip():
            out.append(str(md.relative_to(repo).as_posix()))
    return out


def _records_with_invalid_cancelled_state(repo) -> list[dict[str, str]]:
    """Validate cancelled-state invariants per v1.1 §3.8 / §5.1.

    Two conditions surface a record:

    1. `status: cancelled` records that lack a non-empty `cancelled_at` or
       `cancelled_by` field. These are malformed cancellations — the cancel
       op writes both, so a missing pair indicates direct-edit drift.

    2. Records whose `superseded_by` points at a cancelled record. v1.1
       §5.3's supersede-with-replacement path puts `supersedes` on the new
       record (the new pointing back at the cancelled one); putting
       `superseded_by` on or pointing-at a cancelled record is a structural
       violation — it would imply the cancelled record was inserted into a
       supersession chain on the receiving end, which §5.2 forbids.

    Returns a list of `{path, problem}` dicts so the caller can surface
    each violation precisely.
    """
    base = ir_dir(repo)
    out: list[dict[str, str]] = []
    if not base.exists():
        return out
    # First pass: collect cancelled record ids so we can flag dangling
    # superseded_by references in pass two.
    cancelled_ids: set[str] = set()
    records: list[tuple[str, dict]] = []
    for md in sorted(base.rglob("*.md")):
        try:
            rec = parse_file(md)
        except Exception:
            continue
        rel = str(md.relative_to(repo).as_posix())
        records.append((rel, rec.frontmatter))
        if rec.frontmatter.get("status") == "cancelled":
            rid = rec.frontmatter.get("id")
            if isinstance(rid, str):
                cancelled_ids.add(rid)

    for rel, fm in records:
        if fm.get("status") == "cancelled":
            cat = fm.get("cancelled_at")
            cby = fm.get("cancelled_by")
            missing: list[str] = []
            if not isinstance(cat, str) or not cat.strip():
                missing.append("cancelled_at")
            if not isinstance(cby, str) or not cby.strip():
                missing.append("cancelled_by")
            if missing:
                out.append({
                    "path": rel,
                    "problem": (
                        f"status: cancelled but missing/empty "
                        f"{', '.join(missing)}"
                    ),
                })
        sup_by = fm.get("superseded_by")
        if isinstance(sup_by, str) and sup_by in cancelled_ids:
            out.append({
                "path": rel,
                "problem": (
                    f"superseded_by points at cancelled record {sup_by!r} "
                    "(v1.1 §5.3 forbids cancelled records as the receiving "
                    "end of a supersession chain)"
                ),
            })
    return out


def _records_with_invalid_domain(repo) -> list[str]:
    """Return relative paths of (I, R) records whose `domain` field is present but invalid.

    v1.1 §4.3: `domain` is optional. Records lacking the field are valid.
    Records with the field absent-via-null are valid (null is the explicit
    "no domain" signal). Records with `domain: ""` or non-string types are
    rejected.
    """
    base = ir_dir(repo)
    out: list[str] = []
    if not base.exists():
        return out
    for md in sorted(base.rglob("*.md")):
        try:
            rec = parse_file(md)
        except Exception:
            continue
        if "domain" not in rec.frontmatter:
            continue
        value = rec.frontmatter["domain"]
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            out.append(str(md.relative_to(repo).as_posix()))
    return out


def _records_with_invalid_visible_when(repo) -> list[dict[str, str]]:
    """Validate visible_when shape and authority invariant per v1.1 §4.4.

    Surfaces a record when:

    1. The `visible_when` field is present (and not null) but malformed —
       fails `eightos.predicates.validate_predicate`. Returns the
       structured error message in `problem`.

    2. The `visible_when` field is present (and not null) AND the record's
       `authority_level` is not `hard`. Defense-in-depth: the
       `kernel.ir.new` write path rejects this with
       VISIBILITY_PREDICATE_NOT_PERMITTED, but a direct-edit drift would
       otherwise allow a non-hard record on disk.
    """
    base = ir_dir(repo)
    out: list[dict[str, str]] = []
    if not base.exists():
        return out
    for md in sorted(base.rglob("*.md")):
        try:
            rec = parse_file(md)
        except Exception:
            continue
        if "visible_when" not in rec.frontmatter:
            continue
        value = rec.frontmatter["visible_when"]
        if value is None:
            continue
        rel = str(md.relative_to(repo).as_posix())
        try:
            predicates.validate_predicate(value)
        except KernelError as exc:
            out.append({
                "path": rel,
                "problem": f"malformed visible_when predicate: {exc.message}",
            })
            continue
        authority = rec.frontmatter.get("authority_level")
        if authority != "hard":
            out.append({
                "path": rel,
                "problem": (
                    f"visible_when present on non-hard record "
                    f"(authority_level={authority!r}); v1.1 §4.4 permits the "
                    "field only on hard-authority records"
                ),
            })
    return out


def _records_with_invalid_data_classification(repo) -> list[str]:
    """Return relative paths of (I, R) records whose `data_classification` is present but invalid.

    v1.1 §4.2 (Block 4.3): `data_classification` is optional. Records lacking
    the field are valid. Records with the field absent-via-null are valid
    (null is the explicit "no classification" signal). Records with
    `data_classification: ""` or non-string types are rejected. Mirror of
    `_records_with_invalid_domain`.
    """
    base = ir_dir(repo)
    out: list[str] = []
    if not base.exists():
        return out
    for md in sorted(base.rglob("*.md")):
        try:
            rec = parse_file(md)
        except Exception:
            continue
        if "data_classification" not in rec.frontmatter:
            continue
        value = rec.frontmatter["data_classification"]
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            out.append(str(md.relative_to(repo).as_posix()))
    return out
