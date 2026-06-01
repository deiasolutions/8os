"""Index regeneration (Block 1 §6).

The kernel index set is computed deterministically from the repo's
on-disk state. v1.1 added `policy-evaluations` (Block 4.7),
`lease-holders` and `payload-hash-to-events` (Block 4.8). The function
`compute_all` returns a name -> data mapping; `write_all` persists them
as canonical YAML; `check_all` compares the written state against a
fresh recompute and returns a structured drift report.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable

from ._frontmatter import parse_file
from ._paths import (
    events_dir,
    index_dir,
    ir_dir,
    kernel_category_dir,
)
from ._yaml import dump_yaml, load_yaml_file

INDEX_NAMES: tuple[str, ...] = (
    "id-to-path",
    "path-to-id",
    "scope-to-ids",
    "tier-to-ids",
    "projection-to-ids",
    "resolver-to-events",
    "bridge-to-resolvers",
    "deps-forward",
    "deps-reverse",
    "temporal",
    "surrogate-lineage",
    # v1.0 §6.1: calibration-corpus index — maps (predictor_id, scope, domain)
    # triples to ordered (predicted, actual) tuples. Regenerable from
    # prediction (I, R)s and their corresponding ground-truth resolution (I, R)s.
    "calibration-corpus",
    # v1.1 §3.17 (Block 4.7): policy-evaluations cache index — maps
    # op_signature hashes to evaluation_id. Enables the policy-evaluation
    # phase (§8.6) to skip re-evaluation when a cached record is still
    # current. Regenerable from `_kernel.policy-evaluation` records.
    "policy-evaluations",
    # v1.1 §3.17 (Block 4.8): lease-holders index — maps lease target
    # (scope-id or (I, R) id) to the list of active lease record ids
    # currently covering it. Consulted by op_pipeline.py phase-2 lease
    # check on every write op. Regenerable from `_kernel.lease` records
    # (filtered to those whose `valid_through` has not elapsed).
    "lease-holders",
    # v1.1 §3.17 (Block 4.8): payload-hash-to-events index — maps the
    # SHA-256 hex of an outside-call request payload to the tier-3 event
    # id(s) that recorded crossings carrying that payload. Enables
    # deduplication queries ("have we sent this payload before?") and
    # cache-as-resolver patterns. Regenerable from tier-3 events whose
    # `payload_hash` field is non-null (kernel.outside.http events).
    "payload-hash-to-events",
)


def compute_all(repo_root: Path) -> dict[str, Any]:
    """Compute every index by scanning the repo. Returns name -> data."""
    ir_records = _collect_ir_records(repo_root)
    # v0.2: resolvers and bridges live as (I, R)s under ir/_kernel/<category>/.
    resolver_records = _kernel_records(repo_root, "resolver")
    bridge_records = _kernel_records(repo_root, "bridge")

    id_to_path: dict[str, str] = {}
    path_to_id: dict[str, str] = {}
    scope_to_ids: dict[str, list[str]] = {}
    tier_to_ids: dict[str, list[str]] = {"1": [], "2": [], "3": []}
    projection_to_ids: dict[str, list[str]] = {}
    deps_forward: dict[str, list[str]] = {}
    deps_reverse: dict[str, list[str]] = {}
    temporal_valid_through: list[list[str]] = []
    temporal_revalidate: list[list[str]] = []
    # v1.1 §3.17 (Block 4.7): policy-evaluations index — op_signature → evaluation_id.
    # Built from `_kernel.policy-evaluation` records' op_signature frontmatter field.
    # Last-writer-wins for repeat signatures (the cache reader filters by validity).
    policy_evaluations: dict[str, str] = {}
    # v1.1 §3.17 (Block 4.8): lease-holders index — lease target → list of active lease ids.
    # Built from `_kernel.lease` records whose `valid_through` has not elapsed at compute time.
    # Phase-2 lease check consults this for fast active-lease lookup per target.
    lease_holders: dict[str, list[str]] = {}

    for relpath, fm in ir_records:
        ir_id = fm["id"]
        id_to_path[ir_id] = relpath
        path_to_id[relpath] = ir_id
        scope = fm.get("scope")
        if scope:
            scope_to_ids.setdefault(scope, []).append(ir_id)
        tier = str(fm.get("tier", ""))
        if tier in tier_to_ids:
            tier_to_ids[tier].append(ir_id)
        ptypes = fm.get("projection_types") or []
        for ptype in ptypes:
            projection_to_ids.setdefault(ptype, []).append(ir_id)
        if "_kernel.policy-evaluation" in ptypes:
            sig = fm.get("op_signature")
            if isinstance(sig, str) and sig:
                policy_evaluations[sig] = ir_id
        if "_kernel.lease" in ptypes:
            # Filter to active leases at compute time. Expired leases stay on
            # disk for audit (lifecycle: expire-by-valid-through per §7.1)
            # but don't appear in the active-lease index. Cancelled or
            # superseded leases also excluded.
            valid_through = fm.get("valid_through")
            status = fm.get("status")
            if (
                status not in {"superseded", "cancelled"}
                and isinstance(valid_through, str)
                and _iso_in_future(valid_through)
            ):
                target = fm.get("lease_for")
                if isinstance(target, str) and target:
                    lease_holders.setdefault(target, []).append(ir_id)
        deps = list(fm.get("depends_on") or [])
        if deps:
            deps_forward[ir_id] = sorted(deps)
            for d in deps:
                deps_reverse.setdefault(d, []).append(ir_id)
        if fm.get("valid_through"):
            temporal_valid_through.append([fm["valid_through"], ir_id])
        if fm.get("revalidate_trigger"):
            temporal_revalidate.append([fm["revalidate_trigger"], ir_id])

    # Tier 3 events: each event is also an (I, R) projection per spec; we
    # represent them as JSONL refs in tier-to-ids and id-to-path.
    resolver_to_events: dict[str, list[dict[str, str]]] = {}
    tier3_count = 0
    # v1.1 §3.17 (Block 4.8): payload-hash → tier-3 event id(s). Built from
    # event records carrying `payload_hash` in their resolution.structured
    # block (kernel.outside.http emits this field).
    payload_hash_to_events: dict[str, list[str]] = {}
    for jsonl_path, lineno, ev in _iter_events(repo_root):
        tier3_count += 1
        ev_id = ev.get("event_id")
        if not ev_id:
            continue
        rel = str(jsonl_path.relative_to(repo_root).as_posix())
        # id-to-path entry uses a JSONL line locator: "<path>#L<line>"
        id_to_path[ev_id] = f"{rel}#L{lineno}"
        path_to_id[f"{rel}#L{lineno}"] = ev_id
        rid = ev.get("resolver_id")
        if rid:
            resolver_to_events.setdefault(rid, []).append(
                {"event_id": ev_id, "path": rel, "line": lineno}
            )
        # Payload-hash extraction: the kernel.outside.http event carries
        # payload_hash in resolution.structured.payload_hash. resolution may
        # be a dict OR a plain string in legacy events; structured may also
        # be a plain string (e.g., summary text). Handle defensively.
        resolution = ev.get("resolution")
        if isinstance(resolution, dict):
            structured = resolution.get("structured")
            if isinstance(structured, dict):
                payload_hash = structured.get("payload_hash")
                if isinstance(payload_hash, str) and payload_hash:
                    payload_hash_to_events.setdefault(payload_hash, []).append(ev_id)

    bridge_to_resolvers: dict[str, list[str]] = {}
    for fm in resolver_records:
        rid = fm.get("id")
        if not rid:
            continue
        bridge = fm.get("bridge")
        if bridge:
            bridge_to_resolvers.setdefault(bridge, []).append(rid)
        # ensure resolver-to-events has a key even with no events yet
        resolver_to_events.setdefault(rid, [])
    for fm in bridge_records:
        bid = fm.get("id")
        if bid:
            bridge_to_resolvers.setdefault(bid, [])

    surrogate_lineage = _compute_surrogate_lineage(repo_root)
    calibration_corpus = _compute_calibration_corpus(repo_root, ir_records)

    # tier-to-ids stores tier 3 as both a count and the JSONL ref list (from
    # resolver_to_events we already have per-line locators); the spec calls
    # for "count + JSONL refs" but doesn't dictate exact shape, so we expose
    # both fields for tier 3.
    tier_to_ids_doc: dict[str, Any] = {
        "1": sorted(tier_to_ids["1"]),
        "2": sorted(tier_to_ids["2"]),
        "3": {
            "count": tier3_count,
            "refs": sorted(
                f"{ev['path']}#L{ev['line']}#{ev['event_id']}"
                for evs in resolver_to_events.values()
                for ev in evs
            ),
        },
    }

    # Sort everything deterministically.
    for d in (scope_to_ids, projection_to_ids, deps_forward, deps_reverse, lease_holders, payload_hash_to_events):
        for k in d:
            d[k] = sorted(d[k])
    for k in resolver_to_events:
        resolver_to_events[k] = sorted(
            resolver_to_events[k], key=lambda x: (x["path"], x["line"])
        )
    for k in bridge_to_resolvers:
        bridge_to_resolvers[k] = sorted(set(bridge_to_resolvers[k]))

    temporal_valid_through.sort(key=lambda pair: (pair[0], pair[1]))
    temporal_revalidate.sort(key=lambda pair: (pair[0], pair[1]))

    return {
        "id-to-path": dict(sorted(id_to_path.items())),
        "path-to-id": dict(sorted(path_to_id.items())),
        "scope-to-ids": dict(sorted(scope_to_ids.items())),
        "tier-to-ids": tier_to_ids_doc,
        "projection-to-ids": dict(sorted(projection_to_ids.items())),
        "resolver-to-events": dict(sorted(resolver_to_events.items())),
        "bridge-to-resolvers": dict(sorted(bridge_to_resolvers.items())),
        "deps-forward": dict(sorted(deps_forward.items())),
        "deps-reverse": dict(sorted(deps_reverse.items())),
        "temporal": {
            "valid_through": temporal_valid_through,
            "revalidate_trigger": temporal_revalidate,
        },
        "surrogate-lineage": surrogate_lineage,
        "calibration-corpus": calibration_corpus,
        "policy-evaluations": dict(sorted(policy_evaluations.items())),
        "lease-holders": dict(sorted(lease_holders.items())),
        "payload-hash-to-events": dict(sorted(payload_hash_to_events.items())),
    }


def _iso_in_future(iso_ts: str) -> bool:
    """Return True if the ISO-8601 timestamp is strictly after now (UTC).

    Tolerant: malformed timestamps return False (treated as expired).
    Used by lease-holders index to filter to currently-active leases.
    """
    from datetime import datetime, timezone

    try:
        # Accept trailing Z (zulu) and offset forms.
        if iso_ts.endswith("Z"):
            iso_ts = iso_ts[:-1] + "+00:00"
        ts = datetime.fromisoformat(iso_ts)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts > datetime.now(timezone.utc)
    except (ValueError, TypeError):
        return False


def input_set_hash(repo_root: Path) -> str:
    """SHA-256 over the sorted list of contributing record IDs.

    Block 1 §6.2: the input-set hash is "sorted IDs of all contributing
    records". A change to any record's ID set invalidates the cheap check
    and triggers a full recompute.
    """
    ids: list[str] = []
    for _relpath, fm in _collect_ir_records(repo_root):
        rid = fm.get("id")
        if rid:
            ids.append(f"ir:{rid}")
    for _jsonl, _lineno, ev in _iter_events(repo_root):
        ev_id = ev.get("event_id")
        if ev_id:
            ids.append(f"event:{ev_id}")
    ids.sort()
    h = hashlib.sha256()
    for i in ids:
        h.update(i.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def render_index(name: str, data: Any) -> str:
    """Canonical YAML for one index. Used both to write and to checksum."""
    return dump_yaml(data)


def render_checksum(indexes: dict[str, Any], input_hash: str) -> str:
    """Build the _checksum.yml document.

    Records the input-set hash and a SHA-256 of each index's canonical YAML.
    """
    per_index_sha: dict[str, str] = {}
    for name in INDEX_NAMES:
        text = render_index(name, indexes[name])
        per_index_sha[name] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    doc = {
        "input_set_hash": input_hash,
        "indexes": dict(sorted(per_index_sha.items())),
    }
    return dump_yaml(doc)


def write_all(repo_root: Path, indexes: dict[str, Any] | None = None) -> dict[str, Any]:
    """Recompute and write every kernel index. Returns the computed docs."""
    from ._atomic import atomic_write_text

    if indexes is None:
        indexes = compute_all(repo_root)
    out_dir = index_dir(repo_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in INDEX_NAMES:
        atomic_write_text(out_dir / f"{name}.yml", render_index(name, indexes[name]))
    atomic_write_text(
        out_dir / "_checksum.yml",
        render_checksum(indexes, input_set_hash(repo_root)),
    )
    return indexes


def check_drift(repo_root: Path) -> dict[str, Any] | None:
    """Compare on-disk indexes against a fresh recompute.

    Returns None when fully consistent; otherwise a drift diff describing
    which index files differ.
    """
    on_disk_dir = index_dir(repo_root)
    if not on_disk_dir.exists():
        return {"missing_index_dir": True}

    fresh = compute_all(repo_root)
    fresh_input_hash = input_set_hash(repo_root)

    drift: dict[str, Any] = {}

    # Cheap check: if input_set_hash matches and every index file matches
    # the recomputed canonical YAML, we're consistent.
    checksum_path = on_disk_dir / "_checksum.yml"
    if checksum_path.exists():
        on_disk_checksum = load_yaml_file(checksum_path) or {}
        if on_disk_checksum.get("input_set_hash") != fresh_input_hash:
            drift["input_set_hash"] = {
                "on_disk": on_disk_checksum.get("input_set_hash"),
                "fresh": fresh_input_hash,
            }
    else:
        drift["missing_checksum"] = True

    diffs: dict[str, str] = {}
    for name in INDEX_NAMES:
        path = on_disk_dir / f"{name}.yml"
        fresh_text = render_index(name, fresh[name])
        if not path.exists():
            diffs[name] = "missing"
            continue
        on_disk_text = path.read_text(encoding="utf-8")
        if on_disk_text != fresh_text:
            diffs[name] = "mismatch"
    if diffs:
        drift["indexes"] = diffs

    return drift or None


# ---- internals -------------------------------------------------------------


def _collect_ir_records(repo_root: Path) -> list[tuple[str, dict[str, Any]]]:
    """Walk ir/ and return (relative_path, frontmatter_dict) pairs sorted by path."""
    base = ir_dir(repo_root)
    out: list[tuple[str, dict[str, Any]]] = []
    if not base.exists():
        return out
    for md in sorted(base.rglob("*.md")):
        rel = str(md.relative_to(repo_root).as_posix())
        try:
            rec = parse_file(md)
        except Exception:
            # Malformed records are not silently swallowed; raise so the indexer
            # surfaces the problem instead of producing wrong indexes.
            raise
        out.append((rel, rec.frontmatter))
    return out


def _kernel_records(repo_root: Path, category: str) -> list[dict[str, Any]]:
    """Return frontmatter dicts for every (I, R) under ir/_kernel/<category>/."""
    base = kernel_category_dir(repo_root, category)
    if not base.exists():
        return []
    out: list[dict[str, Any]] = []
    for md in sorted(base.glob("*.md")):
        if md.name.startswith("_"):
            continue  # category-root _node.md files, optional per spec §1.1
        try:
            rec = parse_file(md)
        except Exception:
            raise
        out.append(rec.frontmatter)
    return out


def _iter_events(repo_root: Path) -> Iterable[tuple[Path, int, dict[str, Any]]]:
    """Local copy of _events.iter_events to avoid a circular import path."""
    import json

    base = events_dir(repo_root)
    if not base.exists():
        return
    for year in sorted(p for p in base.iterdir() if p.is_dir() and p.name.isdigit()):
        for month in sorted(p for p in year.iterdir() if p.is_dir()):
            for day in sorted(p for p in month.iterdir() if p.is_dir()):
                for jsonl in sorted(day.glob("*.jsonl")):
                    with open(jsonl, encoding="utf-8") as f:
                        for i, line in enumerate(f, start=1):
                            line = line.strip()
                            if not line:
                                continue
                            yield jsonl, i, json.loads(line)


def _compute_surrogate_lineage(repo_root: Path) -> dict[str, Any]:
    """Aggregate v0.2 surrogate-lineage (I, R)s under ir/_kernel/surrogate-lineage/."""
    out: dict[str, Any] = {}
    for fm in _kernel_records(repo_root, "surrogate-lineage"):
        sid = fm.get("id") or fm.get("surrogate_id")
        if not sid:
            continue
        out[sid] = {
            "surrogate_of": fm.get("surrogate_of"),
            "trained_on": fm.get("trained_on"),
            "trained_by": fm.get("trained_by"),
            "training_corpus": fm.get("training_corpus"),
            "validation": fm.get("validation"),
        }
    return dict(sorted(out.items()))


def _compute_calibration_corpus(
    repo_root: Path,
    ir_records: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    """v1.0 §6.1: maps (predictor_id, scope, domain) → ordered (predicted, actual) tuples.

    Reconstructs the calibration corpus by query — predictions are not
    mutated when actuals arrive; the relationship is rebuilt from the
    on-disk (I, R) graph each reindex.

    Algorithm:
      1. Index intentions by id (every (I, R) is a potential prediction subject).
      2. Index calibration policies by (scope, domain) — pick latest non-superseded.
      3. Iterate prediction (I, R)s. For each:
         - Look up subject intention by id; get its scope.
         - Find the active policy for (scope, intention_domain | None).
         - If policy has a ground_truth_resolver and the subject is resolved
           by that resolver, populate actual_value (subject.resolution_text)
           and actual_at (subject.resolved_at). Otherwise null.
      4. Group tuples by (predictor_id, scope, domain) triple key.
    """
    intentions_by_id: dict[str, dict[str, Any]] = {}
    predictions: list[dict[str, Any]] = []
    policies: list[dict[str, Any]] = []

    for _relpath, fm in ir_records:
        rid = fm.get("id")
        if not rid:
            continue
        intentions_by_id[rid] = fm
        ptypes = fm.get("projection_types") or []
        if "_kernel.prediction" in ptypes:
            predictions.append(fm)
        if "_kernel.calibration-policy" in ptypes:
            if fm.get("status") != "superseded":
                policies.append(fm)

    # Latest policy wins per (scope, domain) — sort by authored_on descending.
    policies.sort(key=lambda p: (p.get("authored_on") or "", p.get("id") or ""), reverse=True)

    def find_policy(scope: str | None, domain: str | None) -> dict[str, Any] | None:
        for p in policies:
            if p.get("applies_to_scope") != scope:
                continue
            p_domain = p.get("applies_to_domain")
            if p_domain is not None and p_domain != domain:
                continue
            return p
        return None

    corpus: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for pred_fm in predictions:
        predictor_id = pred_fm.get("predictor")
        subject_id = pred_fm.get("subject_intention")
        if not predictor_id or not subject_id:
            continue
        subject_fm = intentions_by_id.get(subject_id)
        if subject_fm is None:
            # Subject not on disk (e.g., tier 3 only) — skip for v1.0.
            continue
        scope = subject_fm.get("scope") or ""
        domain = subject_fm.get("domain")  # subjects rarely declare domain; usually None
        policy = find_policy(scope, domain)
        actual_value: Any = None
        actual_at: Any = None
        if policy is not None:
            gt_resolver = policy.get("ground_truth_resolver")
            if (
                gt_resolver
                and subject_fm.get("status") == "resolved"
                and subject_fm.get("resolver") == gt_resolver
            ):
                actual_at = subject_fm.get("resolved_at")
                # Read the resolution text from the file body — frontmatter
                # only carries the resolution_event id, not the text.
                actual_value = _read_resolution_text(repo_root, subject_id)
        tuple_entry = {
            "prediction_id": pred_fm.get("id"),
            "ground_truth_resolution_id": (
                subject_fm.get("resolution_event") if actual_at else None
            ),
            "predicted_value": pred_fm.get("predicted_resolution"),
            "actual_value": actual_value,
            "predicted_at": pred_fm.get("authored_on"),
            "actual_at": actual_at,
        }
        key = (predictor_id, scope, domain or "")
        corpus.setdefault(key, []).append(tuple_entry)

    # Sort each list by predicted_at, then prediction_id, for determinism.
    for key, entries in corpus.items():
        entries.sort(key=lambda e: (e.get("predicted_at") or "", e.get("prediction_id") or ""))

    # Render as a sorted dict with composite string keys "<predictor>|<scope>|<domain>".
    rendered: dict[str, list[dict[str, Any]]] = {}
    for (predictor_id, scope, domain), entries in corpus.items():
        composite = f"{predictor_id}|{scope}|{domain}"
        rendered[composite] = entries
    return dict(sorted(rendered.items()))


def _read_resolution_text(repo_root: Path, ir_id: str) -> str | None:
    """Read the resolution_text from the (I, R) markdown file body.

    Returns None on any read error. Used by calibration-corpus rebuild to
    populate `actual_value` from a resolved subject intention.
    """
    try:
        idx_path = index_dir(repo_root) / "id-to-path.yml"
        if not idx_path.exists():
            return None
        idx = load_yaml_file(idx_path) or {}
        rel = idx.get(ir_id)
        if not rel or "#L" in rel:
            return None
        rec = parse_file(repo_root / rel)
        return rec.resolution_text
    except Exception:
        return None
