"""kernel.outside.http — outside-call primitive (Block 4.8, v1.1 §11).

The canonical outside-call primitive replacing kernel.bridge.cross for new
outside-call work. Per v1.1 §0.2 (axiom 0 inside/outside split) and §11.9,
this op lives in the outside-call category and is NOT counted among the
SDK operations; the runner dispatches it for uniformity.

Pre-commit pipeline (per v1.1 §8.6):
  1. Authority — implicit in the for_ir_id record load (NOT_FOUND if absent).
  2. Lease check — op_pipeline phase 2 (Block 4.8).
  3. Policy evaluation — op_pipeline phase 3 (Block 4.7).
  4. Classification check — folded into phase 3 via classification-aware
     policies per §11.7.

Then payload hashing (post-classification-transform when applied), the
actual HTTP request via urllib.request, response hashing, optional sidecar
storage, and tier-3 event emission. The `payload-hash-to-events` index is
populated by the standard reindex sweep over event ledgers.

A6 invariant (preserved per V0 prompt): when a classification transform
applies, the payload_hash MUST be computed AFTER transformation. Cache
reuse (when a future block adds cache-lookup logic) thus requires the
same transform on lookup. Block 4.8's first landing records transform
actions in the tier-3 event but does NOT apply them — carry-forward of
Block 4.7 finding F-TRANSFORM until a transform language ships. The
invariant is preserved in the code structure for the future block; see
the marker comment near `_canonical_bytes` below.

Queue (per A1): in-memory per-process. Today the kernel binary is single-
threaded synchronous, so the "queue" is degenerate (one call at a time);
queue_time_ms records pipeline + hash time. expires_at is checked at op
entry and again at serve start; calls dropped with EXPIRES_AT_PASSED.
Real concurrency lands when DuckDB storage and multi-factory machinery
do.

Cost decomposition (per v1.1 §6.6, three-vector):
  resolver_cost — outside service cost (serve_time_ms; coin and carbon
                  zero in this binary because the kernel doesn't observe
                  per-API pricing for arbitrary URLs).
  kernel_cost   — queue + event-emission overhead (op_total - serve_time).
  factory_cost  — zero for direct outside.http calls; non-zero only when
                  a factory wraps the call with retry/adapter logic.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .._atomic import append_jsonl_line, atomic_write_text
from .._events import make_event
from .._frontmatter import parse_file
from .._paths import dot8os, event_jsonl_path
from .._time import now_iso
from .._ulid import new_ulid
from .._yaml import load_yaml_file
from ..errors import (
    EVENT_WRITE_FAILED_AFTER_CROSSING,
    EXPIRES_AT_PASSED,
    NOT_FOUND,
    OUTSIDE_UNREACHABLE,
    PAYLOAD_TOO_LARGE,
    KernelError,
)
from ..op_pipeline import build_caller_context, evaluate_op_pre_commit
from ._common import repo_root_or_raise

# Maximum request payload size in bytes. First-landing hard ceiling;
# future block adds per-policy override.
_PAYLOAD_MAX_BYTES = 10 * 1024 * 1024

# HTTP request timeout in seconds. Conservative default; future block
# adds per-call configurability via input or policy.
_HTTP_TIMEOUT_SECONDS = 30


def run(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute one outside-call. Returns success-envelope `data`.

    Raises `KernelError` for any pre-commit rejection (LEASE_HELD,
    POLICY_DENIED, POLICY_REQUIRES_AUTHORIZATION, EXPIRES_AT_PASSED,
    PAYLOAD_TOO_LARGE, NOT_FOUND, AUTHORIZATION_REQUIRED) or for outside-
    contact failures (OUTSIDE_UNREACHABLE, EVENT_WRITE_FAILED_AFTER_CROSSING).
    """
    op_start = time.monotonic()
    direction = payload["direction"]
    target_category = payload["target_category"]
    target_identifier = payload["target_identifier"]
    payload_body = payload["payload"]
    for_ir_id = payload["for_ir_id"]
    authorization_id = payload.get("authorization_id")
    priority = payload.get("priority")
    expires_at = payload.get("expires_at")
    store_sidecar = bool(payload.get("store_payload_sidecar"))

    repo = repo_root_or_raise()

    # Pre-flight: expires_at gate at op entry.
    if expires_at is not None and not _iso_in_future(expires_at):
        raise KernelError(
            EXPIRES_AT_PASSED,
            f"expires_at {expires_at!r} elapsed before op service",
            input_field="expires_at",
            offending_value=expires_at,
            extra_context={"checked_at": now_iso(), "stage": "op_entry"},
        )

    # Resolve the for_ir_id record. Authority is implicit: if the target
    # doesn't exist, NOT_FOUND. The target's scope, classification, and
    # authoring identity feed the pre-commit pipeline.
    target_record = _load_target_record(repo, for_ir_id)
    target_scope = target_record.frontmatter.get("scope") or ""

    # Build caller context. The caller for an outside.http op is the bridge
    # that authored the requesting (I, R); we read that off the record.
    op_input_for_pipeline: dict[str, Any] = {
        "for_ir_id": for_ir_id,
        "scope_id": target_scope,
        "target_identifier": target_identifier,
        "direction": direction,
        "authored_by": target_record.frontmatter.get("authored_by") or "outside",
        "authored_via": target_record.frontmatter.get("authored_via") or "outside",
        "data_classification": target_record.frontmatter.get("data_classification"),
        "domain": target_record.frontmatter.get("domain"),
    }
    caller_context = build_caller_context(
        repo,
        op_input_for_pipeline["authored_via"],
        op_input_for_pipeline,
    )

    # Pipeline phases 2 (lease) and 3 (policy + classification).
    decision = evaluate_op_pre_commit(
        repo,
        op_name="kernel.outside.http",
        op_input=op_input_for_pipeline,
        caller_context=caller_context,
        authorization_id=authorization_id,
    )
    transforms_recorded = list(decision.get("transform_actions") or [])

    # ---- A6 invariant marker -------------------------------------------------
    # If classification transforms were APPLIED here (future block: transform
    # language), payload_for_send would be the transformed payload, and the
    # canonical bytes / payload_hash below would correspond to that transformed
    # form. Cache lookups (future block) would key on the same hash and only
    # hit when the same transform applies — which is correct behavior.
    # Block 4.8 first landing records transforms in the event but does NOT
    # apply them (Block 4.7 F-TRANSFORM carry-forward). When a transform
    # language ships, the application step inserts here and the invariant
    # holds without code reordering.
    payload_for_send = payload_body
    payload_canonical_bytes = _canonical_bytes(payload_for_send)
    if len(payload_canonical_bytes) > _PAYLOAD_MAX_BYTES:
        raise KernelError(
            PAYLOAD_TOO_LARGE,
            f"payload size {len(payload_canonical_bytes)} bytes exceeds max {_PAYLOAD_MAX_BYTES}",
            input_field="payload",
            extra_context={
                "size_bytes": len(payload_canonical_bytes),
                "max_bytes": _PAYLOAD_MAX_BYTES,
            },
        )
    payload_hash = hashlib.sha256(payload_canonical_bytes).hexdigest()
    # --------------------------------------------------------------------------

    queue_start = time.monotonic()
    queue_time_ms = (queue_start - op_start) * 1000.0

    # Pre-serve expires_at gate (re-check; long pipelines can elapse the cutoff).
    if expires_at is not None and not _iso_in_future(expires_at):
        raise KernelError(
            EXPIRES_AT_PASSED,
            f"expires_at {expires_at!r} elapsed during pre-commit pipeline",
            input_field="expires_at",
            offending_value=expires_at,
            extra_context={
                "checked_at": now_iso(),
                "stage": "pre_serve",
                "queue_time_ms": queue_time_ms,
            },
        )

    # ---- Outside contact -----------------------------------------------------
    serve_start = time.monotonic()
    response_body, response_hash = _do_http_call(
        target_identifier=target_identifier,
        payload=payload_for_send,
        canonical_bytes=payload_canonical_bytes,
        direction=direction,
    )
    serve_time_ms = (time.monotonic() - serve_start) * 1000.0

    # Sidecar (optional, opt-in via input flag; first-landing skips policy
    # gating on sidecar enablement — future block adds policy hook).
    event_id = new_ulid()
    sidecar_path: str | None = None
    if store_sidecar:
        sidecar_path = _write_sidecars(
            repo, event_id, payload_canonical_bytes, response_body
        )

    op_total_ms = (time.monotonic() - op_start) * 1000.0
    cost_actual = {
        "resolver_cost": {
            "clock_ms": round(serve_time_ms, 3),
            "coin_usd": 0.0,
            "carbon_g": 0.0,
        },
        "kernel_cost": {
            "clock_ms": round(max(0.0, op_total_ms - serve_time_ms), 3),
            "coin_usd": 0.0,
            "carbon_g": 0.0,
        },
        "factory_cost": {
            "clock_ms": 0.0,
            "coin_usd": 0.0,
            "carbon_g": 0.0,
        },
    }

    # Tier-3 event. payload_hash is in resolution.structured for the
    # `payload-hash-to-events` index sweep to find on reindex.
    ts = now_iso()
    intention = {
        "text": f"Outside HTTP call to {target_identifier!r} for (I, R) {for_ir_id!r}.",
        "scope": target_scope,
        "depth": 0,
        "direction": direction,
        "target_category": target_category,
        "target_identifier": target_identifier,
        "priority": priority,
        "expires_at": expires_at,
        "transforms_recorded": transforms_recorded,
        "transforms_applied": [],
    }
    resolution = {
        "text": f"Outside call completed in {serve_time_ms:.1f} ms.",
        "structured": {
            "payload_hash": payload_hash,
            "response_hash": response_hash,
            "queue_time_ms": queue_time_ms,
            "serve_time_ms": serve_time_ms,
            "sidecar_path": sidecar_path,
            "cost_decomposition": cost_actual,
        },
        "authority_level": "convention",
    }
    target_path = _resolve_target_path(repo, for_ir_id)
    event = make_event(
        event_id=event_id,
        event_type="outside-call",
        ir_node_id=for_ir_id,
        ir_node_path_at_event=target_path,
        resolver_id="kernel.outside.http",
        bridge_id=None,
        intention=intention,
        resolution=resolution,
        cost_actual={
            # Flat shape for backward-compat consumers. Three-vector
            # decomposition lives in resolution.structured.cost_decomposition.
            "clock_ms": round(op_total_ms, 3),
            "coin_usd": 0.0,
            "carbon_g": 0.0,
            "model_name": None,
            "tokens_in": None,
            "tokens_out": None,
        },
        outcome="accepted",
        ts=ts,
    )

    try:
        append_jsonl_line(event_jsonl_path(repo, ts), event)
    except Exception as e:
        raise KernelError(
            EVENT_WRITE_FAILED_AFTER_CROSSING,
            (
                f"outside call to {target_identifier!r} succeeded but event "
                f"write failed: {type(e).__name__}: {e}"
            ),
            extra_context={
                "payload_hash": payload_hash,
                "response_hash": response_hash,
                "response": response_body,
            },
        ) from e

    return {
        "data": {
            "response": response_body,
            "payload_hash": payload_hash,
            "response_hash": response_hash,
            "cost_actual": cost_actual,
            "queue_time_ms": round(queue_time_ms, 3),
            "serve_time_ms": round(serve_time_ms, 3),
            "sidecar_path": sidecar_path,
            "tier3_event_id": event_id,
        },
        "event_id": event_id,
        "indexes_updated": [
            "resolver-to-events",
            "payload-hash-to-events",
        ],
    }


# ---- Helpers ----------------------------------------------------------------


def _load_target_record(repo: Path, for_ir_id: str):
    """Load the (I, R) record this call is performed for. Raises NOT_FOUND."""
    idx = load_yaml_file(repo / ".8os" / "index" / "id-to-path.yml") or {}
    rel = idx.get(for_ir_id)
    if not rel or "#L" in rel:
        raise KernelError(
            NOT_FOUND,
            f"for_ir_id {for_ir_id!r} not found in id-to-path index",
            input_field="for_ir_id",
            offending_value=for_ir_id,
        )
    try:
        return parse_file(repo / rel)
    except Exception as e:
        raise KernelError(
            NOT_FOUND,
            f"for_ir_id {for_ir_id!r} record at {rel!r} unreadable: {type(e).__name__}: {e}",
            input_field="for_ir_id",
            offending_value=for_ir_id,
        ) from e


def _resolve_target_path(repo: Path, for_ir_id: str) -> str:
    """Best-effort relative path for the target (I, R); empty string on miss."""
    idx = load_yaml_file(repo / ".8os" / "index" / "id-to-path.yml") or {}
    rel = idx.get(for_ir_id) or ""
    return rel if isinstance(rel, str) else ""


def _canonical_bytes(payload: Any) -> bytes:
    """Canonical serialization of payload for hashing.

    bytes / bytearray pass through. str encoded UTF-8. Other types serialized
    as canonical JSON (sorted keys, no extraneous whitespace).
    """
    if isinstance(payload, (bytes, bytearray)):
        return bytes(payload)
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def _do_http_call(
    *,
    target_identifier: str,
    payload: Any,
    canonical_bytes: bytes,
    direction: str,
) -> tuple[Any, str]:
    """Make the HTTP request. Returns (decoded_response, response_hash).

    First-landing scope: outbound only. POST when payload is non-empty;
    GET when payload is empty/null. Headers: User-Agent always; Content-
    Type: application/json when JSON-serialized.

    Raises OUTSIDE_UNREACHABLE on transport failure or non-2xx status.
    """
    if direction != "outbound":
        raise KernelError(
            OUTSIDE_UNREACHABLE,
            (
                f"direction {direction!r} not supported in this binary; "
                f"outbound only. Inbound and bidirectional are reserved for "
                f"future blocks."
            ),
            input_field="direction",
            offending_value=direction,
        )

    headers: dict[str, str] = {"User-Agent": "8OS-kernel.outside.http/1.1"}
    body_bytes: bytes | None = None
    method = "GET"
    if payload is not None and not (isinstance(payload, dict) and not payload):
        method = "POST"
        body_bytes = canonical_bytes
        if not isinstance(payload, (bytes, bytearray, str)):
            headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        target_identifier, data=body_bytes, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_SECONDS) as resp:
            response_bytes = resp.read()
            response_headers = dict(resp.headers)
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = ""
        raise KernelError(
            OUTSIDE_UNREACHABLE,
            f"outside service returned {e.code}: {e.reason}",
            extra_context={
                "status": e.code,
                "url": target_identifier,
                "method": method,
                "body_excerpt": err_body[:1000],
            },
        ) from e
    except urllib.error.URLError as e:
        raise KernelError(
            OUTSIDE_UNREACHABLE,
            f"outside service unreachable: {e.reason!s}",
            extra_context={
                "url": target_identifier,
                "method": method,
                "reason": str(e.reason),
            },
        ) from e
    except Exception as e:  # noqa: BLE001 — opaque transport failure
        raise KernelError(
            OUTSIDE_UNREACHABLE,
            f"outside service contact failed: {type(e).__name__}: {e}",
            extra_context={"url": target_identifier, "method": method},
        ) from e

    response_hash = hashlib.sha256(response_bytes).hexdigest()
    response_body = _decode_response(response_bytes, response_headers)
    return response_body, response_hash


def _decode_response(
    response_bytes: bytes, headers: dict[str, str]
) -> Any:
    """Decode response bytes per Content-Type. JSON / text / base64 fallback."""
    content_type = (headers.get("Content-Type") or "").lower()
    if "application/json" in content_type:
        try:
            return json.loads(response_bytes)
        except json.JSONDecodeError:
            return response_bytes.decode("utf-8", errors="replace")
    if content_type.startswith("text/") or not content_type:
        return response_bytes.decode("utf-8", errors="replace")
    return {"_b64": base64.b64encode(response_bytes).decode("ascii")}


def _write_sidecars(
    repo: Path,
    event_id: str,
    payload_bytes: bytes,
    response_body: Any,
) -> str:
    """Write request and response sidecar files; return their parent dir.

    Files: `<event_id>.request` and `<event_id>.response` under
    `.8os/payloads/`. Directory created on demand. No automatic cleanup
    in this block (see Block 4.8 [WIP] commit message for A5).
    """
    sidecar_dir = dot8os(repo) / "payloads"
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    request_path = sidecar_dir / f"{event_id}.request"
    response_path = sidecar_dir / f"{event_id}.response"
    atomic_write_text(
        request_path, payload_bytes.decode("utf-8", errors="replace")
    )
    if isinstance(response_body, str):
        atomic_write_text(response_path, response_body)
    else:
        atomic_write_text(
            response_path,
            json.dumps(response_body, ensure_ascii=False, indent=2),
        )
    return str(sidecar_dir)


def _iso_in_future(iso_ts: Any) -> bool:
    """Mirror of op_pipeline._iso_in_future for self-contained module."""
    if not isinstance(iso_ts, str) or not iso_ts:
        return False
    try:
        if iso_ts.endswith("Z"):
            iso_ts = iso_ts[:-1] + "+00:00"
        ts = datetime.fromisoformat(iso_ts)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts > datetime.now(timezone.utc)
    except (ValueError, TypeError):
        return False


__all__ = ["run"]
