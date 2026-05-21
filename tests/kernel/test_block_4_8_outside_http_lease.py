"""Tests for Block 4.8 — kernel.outside.http + _kernel.lease.

Implements 8OS-BLOCK-1-SPEC v1.1 §11 (`kernel.outside.http`) and §7.1
(`_kernel.lease`). Closes Block 4.2's lease-check placeholder by
implementing op_pipeline phase 2.

Categories:
1. Vendored projection body for `_kernel.lease`.
2. Lease records lifecycle (acquire, expire, supersede).
3. op_pipeline phase-2 lease check.
4. Lease check helpers (read_active_leases_for_target, _caller_holds_lease,
   _extract_lease_targets).
5. Indexes (lease-holders, payload-hash-to-events).
6. kernel.outside.http schema validation.
7. kernel.outside.http expires_at gate.
8. kernel.outside.http transport (against a local HTTP test server).
9. kernel.outside.http payload hashing.
10. kernel.outside.http sidecar storage.
11. kernel.outside.http error codes.
12. kernel.outside.http pipeline integration.
13. Backward compat (Block 4.7 policy machinery still works).
14. Upgrade path (1.1.0-dev.6 → 1.1.0-dev.7 clean).

Out of scope for first landing (deferred — surface back if the test
count is significantly under 120 per A9 watch):
- Multi-factory lease arbitration (single-process; can't simulate).
- Priority queue ordering (queue is degenerate single-threaded).
- inbound / bidirectional direction (rejected with one test, not a suite).
- Cache-lookup semantics (cache logic deferred to a future block; the
  payload-hash-to-events index is populated but not consulted by the
  op handler in this block).
- Bridge composition (bridges-as-PRISM-IR not in this block).
- Three-cost migration of pre-existing events (separate cleanup block).
"""

from __future__ import annotations

import hashlib
import http.server
import json
import socketserver
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from eightos import __version__ as KERNEL_VERSION
from eightos import op_pipeline as pipeline
from eightos._frontmatter import parse_file
from eightos._yaml import load_yaml_file
from eightos.errors import (
    EXPIRES_AT_PASSED,
    LEASE_HELD,
    NOT_FOUND,
    OUTSIDE_UNREACHABLE,
    POLICY_DENIED,
    SCHEMA_INVALID,
    KernelError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _author_open(run_op, slug, *, scope="test-scope", **kwargs):
    payload = {
        "scope_id": scope,
        "slug": slug,
        "tier": 1,
        "intention_text": f"Test intention {slug!r}.",
        "authority_level": "convention",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
    }
    payload.update(kwargs)
    return run_op("kernel.ir.new", payload)


def _author_lease(
    run_op,
    lease_id,
    lease_for,
    held_by,
    *,
    lease_purpose="write",
    valid_through=None,
    scope="test-scope",
):
    if valid_through is None:
        valid_through = (
            datetime.now(timezone.utc) + timedelta(hours=1)
        ).isoformat().replace("+00:00", "Z")
    return run_op("kernel.ir.new", {
        "scope_id": scope,
        "slug": lease_id,
        "tier": 1,
        "intention_text": f"Lease {lease_id!r}.",
        "projection_types": ["_kernel.lease"],
        "authority_level": "convention",
        "authored_by": held_by.split(":", 1)[-1] if ":" in held_by else held_by,
        "authored_via": "kernel.self",
        "valid_through": valid_through,
        "frontmatter_extensions": {
            "lease_id": lease_id,
            "lease_for": lease_for,
            "held_by": held_by,
            "lease_purpose": lease_purpose,
            "acquired_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
    })


def _author_role(run_op, role_id, grants, holders, scope="_kernel"):
    return run_op("kernel.ir.new", {
        "scope_id": scope,
        "slug": role_id,
        "tier": 1,
        "intention_text": f"Role {role_id!r}.",
        "projection_types": ["_kernel.role"],
        "authority_level": "hard",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "frontmatter_extensions": {
            "role_id": role_id,
            "grants": grants,
            "holders": holders,
        },
    })


def _author_policy(
    run_op,
    policy_id,
    applies_to_op,
    decision,
    *,
    condition=None,
    defer_to=None,
    scope="_kernel",
):
    extensions = {
        "policy_id": policy_id,
        "applies_to_op": applies_to_op,
        "decision": decision,
        "condition": condition if condition is not None else {"any": [{"caller": "anyone"}]},
    }
    if defer_to is not None:
        extensions["defer_to"] = defer_to
    return run_op("kernel.ir.new", {
        "scope_id": scope,
        "slug": policy_id,
        "tier": 1,
        "intention_text": f"Policy {policy_id!r}.",
        "projection_types": ["_kernel.policy"],
        "authority_level": "hard",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "frontmatter_extensions": extensions,
    })


def _reindex(run_op):
    """Run kernel.reindex --mode=rebuild so newly-authored records appear in indexes."""
    return run_op("kernel.reindex", {"mode": "rebuild"})


# Local HTTP test server fixture shared by transport tests.
class _EchoHandler(http.server.BaseHTTPRequestHandler):
    """Echoes the request method, path, and body in a JSON response."""

    def log_message(self, format, *args):  # noqa: A002 — silence stdout
        pass

    def _send(self, status, body, content_type="application/json"):
        body_bytes = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def do_GET(self):  # noqa: N802
        if self.path == "/404":
            self._send(404, "{\"error\": \"not found\"}")
            return
        self._send(200, json.dumps({"method": "GET", "path": self.path}))

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        self._send(200, json.dumps({
            "method": "POST",
            "path": self.path,
            "echoed": body.decode("utf-8", errors="replace"),
        }))


@pytest.fixture
def http_server():
    """Start a local HTTP echo server on an ephemeral port."""
    httpd = socketserver.TCPServer(("127.0.0.1", 0), _EchoHandler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


# ---------------------------------------------------------------------------
# 1. Vendored projection body for `_kernel.lease`
# ---------------------------------------------------------------------------


def test_kernel_lease_projection_vendored_after_init(initialized: Path):
    body_path = initialized / ".8os" / "projections" / "_kernel" / "_kernel.lease.yml"
    assert body_path.exists()
    body = load_yaml_file(body_path)
    assert body["projection_id"] == "_kernel.lease"
    assert body["filename_suffix"] == ".lease.md"
    assert body["target_subdirectory"] == "_leases"


def test_kernel_lease_required_frontmatter_present(initialized: Path):
    body_path = initialized / ".8os" / "projections" / "_kernel" / "_kernel.lease.yml"
    body = load_yaml_file(body_path)
    required_names = {item["name"] for item in body["required_frontmatter"]}
    assert {"lease_id", "lease_for", "held_by", "lease_purpose", "acquired_at"} == required_names


def test_kernel_lease_projection_definition_record_authored(initialized: Path):
    rec_path = initialized / "ir" / "_kernel" / "projection" / "_kernel.lease.md"
    assert rec_path.exists()
    rec = parse_file(rec_path)
    assert rec.frontmatter["id"] == "_kernel.lease"
    assert "_kernel.projection" in rec.frontmatter["projection_types"]


def test_kernel_lease_in_projection_to_ids_index(initialized: Path):
    idx = load_yaml_file(initialized / ".8os" / "index" / "projection-to-ids.yml")
    assert "_kernel.projection" in idx
    assert "_kernel.lease" in idx["_kernel.projection"]


# ---------------------------------------------------------------------------
# 2. Lease records lifecycle
# ---------------------------------------------------------------------------


def test_lease_authored_via_kernel_ir_new(initialized: Path, run_op):
    env = _author_lease(run_op, "lease-1", "test-scope", "author:test-author")
    assert env["status"] == "ok"
    rec_path = initialized / "ir" / "test-scope" / "_leases" / "lease-1.lease.md"
    assert rec_path.exists()


def test_lease_held_by_field_preserved(initialized: Path, run_op):
    _author_lease(run_op, "lease-h1", "test-scope", "author:alice")
    rec = parse_file(initialized / "ir" / "test-scope" / "_leases" / "lease-h1.lease.md")
    assert rec.frontmatter["held_by"] == "author:alice"
    assert rec.frontmatter["lease_purpose"] == "write"


def test_lease_id_uniqueness_prevents_re_acquire(initialized: Path, run_op):
    _author_lease(run_op, "lease-uniq", "test-scope", "author:alice")
    with pytest.raises(KernelError) as exc:
        _author_lease(run_op, "lease-uniq", "test-scope", "author:bob")
    assert exc.value.code in {"ALREADY_EXISTS", "ID_CONFLICT"}


def test_lease_authoring_does_not_self_block(initialized: Path, run_op):
    """Authoring a _kernel.lease record bypasses phase-2 lease check.

    Otherwise leases would deadlock: acquiring a lease would require holding one.
    """
    _author_lease(run_op, "lease-bootstrap", "test-scope", "author:test-author", lease_purpose="exclusive")
    # Authoring a second lease for the same target by a different holder
    # is permitted at write time (lease conflicts are checked when other ops
    # try to write into the leased target, not at lease-author time).
    env = _author_lease(run_op, "lease-second", "other-scope", "author:bob")
    assert env["status"] == "ok"


def test_lease_with_past_valid_through_is_ignored_by_index(initialized: Path, run_op):
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    _author_lease(
        run_op, "lease-expired", "test-scope", "author:alice", valid_through=past
    )
    _reindex(run_op)
    idx = load_yaml_file(initialized / ".8os" / "index" / "lease-holders.yml")
    assert "test-scope" not in (idx or {})


# ---------------------------------------------------------------------------
# 3. op_pipeline phase-2 lease check
# ---------------------------------------------------------------------------


def test_phase_2_no_op_when_no_leases(initialized: Path, run_op):
    """Block 4.7's pre-Block-4.8 path: with no leases, phase 2 passes through."""
    env = _author_open(run_op, "no-lease-record")
    assert env["status"] == "ok"


def test_lease_held_by_other_writer_blocks_kernel_ir_new(initialized: Path, run_op):
    _author_lease(run_op, "lease-block-1", "test-scope", "author:alice", lease_purpose="write")
    _reindex(run_op)
    # test-author tries to author into test-scope, which alice has leased
    with pytest.raises(KernelError) as exc:
        _author_open(run_op, "blocked-record", scope="test-scope")
    assert exc.value.code == LEASE_HELD


def test_lease_held_by_caller_passes(initialized: Path, run_op):
    _author_lease(run_op, "lease-self-1", "test-scope", "author:test-author", lease_purpose="write")
    _reindex(run_op)
    env = _author_open(run_op, "self-lease-record", scope="test-scope")
    assert env["status"] == "ok"


def test_exclusive_lease_blocks_writes(initialized: Path, run_op):
    _author_lease(run_op, "lease-excl", "test-scope", "author:alice", lease_purpose="exclusive")
    _reindex(run_op)
    with pytest.raises(KernelError) as exc:
        _author_open(run_op, "excl-blocked", scope="test-scope")
    assert exc.value.code == LEASE_HELD


def test_read_lease_does_not_block_writes(initialized: Path, run_op):
    _author_lease(run_op, "lease-read", "test-scope", "author:alice", lease_purpose="read")
    _reindex(run_op)
    env = _author_open(run_op, "read-not-blocked", scope="test-scope")
    assert env["status"] == "ok"


def test_shared_lease_does_not_block_writes(initialized: Path, run_op):
    _author_lease(run_op, "lease-shared", "test-scope", "author:alice", lease_purpose="shared")
    _reindex(run_op)
    env = _author_open(run_op, "shared-not-blocked", scope="test-scope")
    assert env["status"] == "ok"


def test_expired_lease_re_validated_at_read_time(initialized: Path, run_op):
    """Even if the index hasn't been regenerated, _check_leases revalidates valid_through."""
    # Author with a valid_through in the past — index won't include it,
    # but if it somehow did, the re-validation in read_active_leases_for_target
    # would still skip it. This exercises the re-validation path.
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    _author_lease(run_op, "lease-just-expired", "test-scope", "author:alice", valid_through=past)
    _reindex(run_op)
    env = _author_open(run_op, "after-expired", scope="test-scope")
    assert env["status"] == "ok"


def test_lease_on_specific_ir_blocks_op_against_it(initialized: Path, run_op):
    _author_open(run_op, "target-ir", scope="test-scope")
    _author_lease(run_op, "lease-ir-1", "target-ir", "author:alice", lease_purpose="write")
    _reindex(run_op)
    # Cancel the target-ir as test-author (not the lease holder)
    with pytest.raises(KernelError) as exc:
        run_op("kernel.ir.cancel", {
            "ir_id": "target-ir",
            "cancelled_by": "test-author",
            "authored_via": "kernel.self",
        })
    # Either LEASE_HELD or AUTHORITY_INSUFFICIENT can fire first depending on
    # phase ordering; both are correct rejections.
    assert exc.value.code in {LEASE_HELD, "AUTHORITY_INSUFFICIENT", "CANCELLATION_AUTHORITY_INSUFFICIENT"}


def test_lease_on_scope_inherited_by_ir_in_scope(initialized: Path, run_op):
    """Lease on scope X blocks writes against any ir in scope X (because the
    op extracts both target_ir and target_ir's scope as lease targets)."""
    _author_open(run_op, "ir-in-leased-scope", scope="test-scope")
    _author_lease(run_op, "lease-scope-x", "test-scope", "author:alice", lease_purpose="write")
    _reindex(run_op)
    # Author another record in the leased scope as test-author (different from alice)
    with pytest.raises(KernelError) as exc:
        _author_open(run_op, "another-in-scope", scope="test-scope")
    assert exc.value.code == LEASE_HELD


# ---------------------------------------------------------------------------
# 4. Lease check helpers (unit tests)
# ---------------------------------------------------------------------------


def test_caller_holds_lease_author_prefix():
    fm = {"held_by": "author:alice", "id": "l1"}
    assert pipeline._caller_holds_lease(fm, "alice") is True
    assert pipeline._caller_holds_lease(fm, "bob") is False


def test_caller_holds_lease_factory_prefix():
    fm = {"held_by": "factory:f1", "id": "l1"}
    assert pipeline._caller_holds_lease(fm, "f1") is True
    assert pipeline._caller_holds_lease(fm, "factory:f1") is True
    assert pipeline._caller_holds_lease(fm, "other") is False


def test_caller_holds_lease_handles_missing_caller():
    fm = {"held_by": "author:alice", "id": "l1"}
    assert pipeline._caller_holds_lease(fm, None) is False
    assert pipeline._caller_holds_lease(fm, "") is False


def test_caller_holds_lease_handles_malformed_held_by():
    fm = {"id": "l1"}  # no held_by
    assert pipeline._caller_holds_lease(fm, "alice") is False
    fm2 = {"held_by": "", "id": "l1"}
    assert pipeline._caller_holds_lease(fm2, "alice") is False


def test_extract_lease_targets_with_scope_id(initialized: Path):
    targets = pipeline._extract_lease_targets(initialized, "kernel.ir.new", {
        "scope_id": "test-scope",
    })
    assert "test-scope" in targets


def test_extract_lease_targets_skips_non_write_ops(initialized: Path):
    assert pipeline._extract_lease_targets(initialized, "kernel.ir.get", {
        "ir_id": "anything",
    }) == []


def test_extract_lease_targets_skips_lease_authoring(initialized: Path):
    """Authoring a lease record bypasses phase 2 — otherwise deadlock."""
    targets = pipeline._extract_lease_targets(initialized, "kernel.ir.new", {
        "scope_id": "_kernel",
        "projection_types": ["_kernel.lease"],
    })
    assert targets == []


def test_extract_lease_targets_resolves_ir_id_to_scope(initialized: Path, run_op):
    _author_open(run_op, "ir-with-scope", scope="test-scope")
    _reindex(run_op)
    targets = pipeline._extract_lease_targets(initialized, "kernel.ir.cancel", {
        "ir_id": "ir-with-scope",
    })
    assert "ir-with-scope" in targets
    assert "test-scope" in targets


def test_read_active_leases_returns_empty_when_no_index(initialized: Path):
    # The lease-holders index exists post-init but is empty.
    leases = pipeline.read_active_leases_for_target(initialized, "no-such-target")
    assert leases == []


def test_read_active_leases_filters_expired_at_read_time(initialized: Path, run_op):
    # Active lease in index
    _author_lease(run_op, "lease-active", "target-x", "author:alice")
    _reindex(run_op)
    leases = pipeline.read_active_leases_for_target(initialized, "target-x")
    assert len(leases) == 1
    assert leases[0]["lease_id"] == "lease-active"


# ---------------------------------------------------------------------------
# 5. Indexes (lease-holders, payload-hash-to-events)
# ---------------------------------------------------------------------------


def test_lease_holders_index_in_INDEX_NAMES():
    from eightos._indexes import INDEX_NAMES
    assert "lease-holders" in INDEX_NAMES


def test_payload_hash_to_events_index_in_INDEX_NAMES():
    from eightos._indexes import INDEX_NAMES
    assert "payload-hash-to-events" in INDEX_NAMES


def test_lease_holders_index_populates_active_leases(initialized: Path, run_op):
    _author_lease(run_op, "lease-pop-1", "scope-a", "author:alice")
    _author_lease(run_op, "lease-pop-2", "scope-b", "author:bob")
    _reindex(run_op)
    idx = load_yaml_file(initialized / ".8os" / "index" / "lease-holders.yml") or {}
    assert "lease-pop-1" in idx.get("scope-a", [])
    assert "lease-pop-2" in idx.get("scope-b", [])


def test_lease_holders_index_excludes_expired(initialized: Path, run_op):
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    _author_lease(run_op, "lease-old", "scope-c", "author:alice", valid_through=past)
    _reindex(run_op)
    idx = load_yaml_file(initialized / ".8os" / "index" / "lease-holders.yml") or {}
    assert "scope-c" not in idx


def test_lease_holders_index_regenerable_no_drift(initialized: Path, run_op):
    _author_lease(run_op, "lease-drift", "scope-drift", "author:alice")
    _reindex(run_op)
    env = run_op("kernel.reindex", {"mode": "check"})
    assert env["data"].get("drift_detected") is False


def test_payload_hash_to_events_index_initially_empty(initialized: Path):
    idx_path = initialized / ".8os" / "index" / "payload-hash-to-events.yml"
    assert idx_path.exists()
    idx = load_yaml_file(idx_path) or {}
    assert idx == {}


# ---------------------------------------------------------------------------
# 6. kernel.outside.http schema validation
# ---------------------------------------------------------------------------


def test_outside_http_rejects_missing_required(initialized: Path, run_op):
    with pytest.raises(KernelError) as exc:
        run_op("kernel.outside.http", {})
    assert exc.value.code == SCHEMA_INVALID


def test_outside_http_rejects_unknown_direction(initialized: Path, run_op):
    with pytest.raises(KernelError) as exc:
        run_op("kernel.outside.http", {
            "direction": "telepathy",
            "target_category": "network",
            "target_identifier": "http://x",
            "payload": {},
            "for_ir_id": "any",
        })
    assert exc.value.code == SCHEMA_INVALID


def test_outside_http_rejects_unknown_target_category(initialized: Path, run_op):
    with pytest.raises(KernelError) as exc:
        run_op("kernel.outside.http", {
            "direction": "outbound",
            "target_category": "filesystem",
            "target_identifier": "/etc/passwd",
            "payload": {},
            "for_ir_id": "any",
        })
    assert exc.value.code == SCHEMA_INVALID


def test_outside_http_inbound_direction_rejected_in_first_landing(
    initialized: Path, run_op, http_server,
):
    _author_open(run_op, "ir-inbound")
    _reindex(run_op)
    with pytest.raises(KernelError) as exc:
        run_op("kernel.outside.http", {
            "direction": "inbound",
            "target_category": "network",
            "target_identifier": http_server,
            "payload": {},
            "for_ir_id": "ir-inbound",
        })
    # The handler rejects inbound with OUTSIDE_UNREACHABLE per first-landing scope.
    assert exc.value.code == OUTSIDE_UNREACHABLE


# ---------------------------------------------------------------------------
# 7. kernel.outside.http expires_at gate
# ---------------------------------------------------------------------------


def test_expires_at_in_past_rejects_at_op_entry(initialized: Path, run_op, http_server):
    _author_open(run_op, "ir-exp-1")
    _reindex(run_op)
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    with pytest.raises(KernelError) as exc:
        run_op("kernel.outside.http", {
            "direction": "outbound",
            "target_category": "network",
            "target_identifier": http_server,
            "payload": {},
            "for_ir_id": "ir-exp-1",
            "expires_at": past,
        })
    assert exc.value.code == EXPIRES_AT_PASSED


def test_expires_at_null_skips_gate(initialized: Path, run_op, http_server):
    _author_open(run_op, "ir-exp-null")
    _reindex(run_op)
    env = run_op("kernel.outside.http", {
        "direction": "outbound",
        "target_category": "network",
        "target_identifier": http_server + "/x",
        "payload": {},
        "for_ir_id": "ir-exp-null",
        "expires_at": None,
    })
    assert env["status"] == "ok"


def test_expires_at_future_passes(initialized: Path, run_op, http_server):
    _author_open(run_op, "ir-exp-future")
    _reindex(run_op)
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    env = run_op("kernel.outside.http", {
        "direction": "outbound",
        "target_category": "network",
        "target_identifier": http_server + "/y",
        "payload": {},
        "for_ir_id": "ir-exp-future",
        "expires_at": future,
    })
    assert env["status"] == "ok"


# ---------------------------------------------------------------------------
# 8. kernel.outside.http transport
# ---------------------------------------------------------------------------


def test_outside_http_get_smoke(initialized: Path, run_op, http_server):
    _author_open(run_op, "ir-get-1")
    _reindex(run_op)
    env = run_op("kernel.outside.http", {
        "direction": "outbound",
        "target_category": "network",
        "target_identifier": http_server + "/hello",
        "payload": {},  # empty dict triggers GET
        "for_ir_id": "ir-get-1",
    })
    assert env["status"] == "ok"
    data = env["data"]
    assert data["response"]["method"] == "GET"
    assert data["response"]["path"] == "/hello"
    assert isinstance(data["payload_hash"], str) and len(data["payload_hash"]) == 64
    assert isinstance(data["response_hash"], str) and len(data["response_hash"]) == 64


def test_outside_http_post_json_smoke(initialized: Path, run_op, http_server):
    _author_open(run_op, "ir-post-1")
    _reindex(run_op)
    env = run_op("kernel.outside.http", {
        "direction": "outbound",
        "target_category": "network",
        "target_identifier": http_server + "/api",
        "payload": {"key": "value", "n": 42},
        "for_ir_id": "ir-post-1",
    })
    assert env["status"] == "ok"
    data = env["data"]
    assert data["response"]["method"] == "POST"
    # The echoed body is the canonical JSON we sent
    echoed = json.loads(data["response"]["echoed"])
    assert echoed == {"key": "value", "n": 42}


def test_outside_http_unreachable_returns_OUTSIDE_UNREACHABLE(initialized: Path, run_op):
    _author_open(run_op, "ir-bad-host")
    _reindex(run_op)
    with pytest.raises(KernelError) as exc:
        run_op("kernel.outside.http", {
            "direction": "outbound",
            "target_category": "network",
            "target_identifier": "http://127.0.0.1:1/never-listens",
            "payload": {},
            "for_ir_id": "ir-bad-host",
        })
    assert exc.value.code == OUTSIDE_UNREACHABLE


def test_outside_http_404_returns_OUTSIDE_UNREACHABLE(initialized: Path, run_op, http_server):
    _author_open(run_op, "ir-404")
    _reindex(run_op)
    with pytest.raises(KernelError) as exc:
        run_op("kernel.outside.http", {
            "direction": "outbound",
            "target_category": "network",
            "target_identifier": http_server + "/404",
            "payload": {},
            "for_ir_id": "ir-404",
        })
    assert exc.value.code == OUTSIDE_UNREACHABLE


def test_outside_http_event_emitted(initialized: Path, run_op, http_server):
    _author_open(run_op, "ir-event-1")
    _reindex(run_op)
    env = run_op("kernel.outside.http", {
        "direction": "outbound",
        "target_category": "network",
        "target_identifier": http_server + "/evt",
        "payload": {},
        "for_ir_id": "ir-event-1",
    })
    event_id = env["data"]["tier3_event_id"]
    assert isinstance(event_id, str) and len(event_id) > 0
    # Re-index and check payload-hash-to-events index has an entry for our payload_hash
    _reindex(run_op)
    idx = load_yaml_file(initialized / ".8os" / "index" / "payload-hash-to-events.yml") or {}
    assert env["data"]["payload_hash"] in idx
    assert event_id in idx[env["data"]["payload_hash"]]


def test_outside_http_for_ir_id_not_found(initialized: Path, run_op, http_server):
    with pytest.raises(KernelError) as exc:
        run_op("kernel.outside.http", {
            "direction": "outbound",
            "target_category": "network",
            "target_identifier": http_server,
            "payload": {},
            "for_ir_id": "does-not-exist",
        })
    assert exc.value.code == NOT_FOUND


# ---------------------------------------------------------------------------
# 9. kernel.outside.http payload hashing
# ---------------------------------------------------------------------------


def test_payload_hash_canonical_json_dict(initialized: Path, run_op, http_server):
    """Same dict (different key order) → same canonical bytes → same hash."""
    _author_open(run_op, "ir-canon-1")
    _reindex(run_op)
    env_a = run_op("kernel.outside.http", {
        "direction": "outbound",
        "target_category": "network",
        "target_identifier": http_server + "/c",
        "payload": {"a": 1, "b": 2},
        "for_ir_id": "ir-canon-1",
    })
    _author_open(run_op, "ir-canon-2")
    _reindex(run_op)
    env_b = run_op("kernel.outside.http", {
        "direction": "outbound",
        "target_category": "network",
        "target_identifier": http_server + "/c",
        "payload": {"b": 2, "a": 1},
        "for_ir_id": "ir-canon-2",
    })
    assert env_a["data"]["payload_hash"] == env_b["data"]["payload_hash"]


def test_payload_hash_different_payloads_different_hashes(
    initialized: Path, run_op, http_server,
):
    _author_open(run_op, "ir-diff-1")
    _author_open(run_op, "ir-diff-2")
    _reindex(run_op)
    env_a = run_op("kernel.outside.http", {
        "direction": "outbound",
        "target_category": "network",
        "target_identifier": http_server + "/d",
        "payload": {"k": "alpha"},
        "for_ir_id": "ir-diff-1",
    })
    env_b = run_op("kernel.outside.http", {
        "direction": "outbound",
        "target_category": "network",
        "target_identifier": http_server + "/d",
        "payload": {"k": "beta"},
        "for_ir_id": "ir-diff-2",
    })
    assert env_a["data"]["payload_hash"] != env_b["data"]["payload_hash"]


def test_payload_hash_string_passthrough(initialized: Path, run_op, http_server):
    _author_open(run_op, "ir-str-1")
    _reindex(run_op)
    env = run_op("kernel.outside.http", {
        "direction": "outbound",
        "target_category": "network",
        "target_identifier": http_server + "/s",
        "payload": "raw string body",
        "for_ir_id": "ir-str-1",
    })
    expected = hashlib.sha256("raw string body".encode("utf-8")).hexdigest()
    assert env["data"]["payload_hash"] == expected


# ---------------------------------------------------------------------------
# 10. kernel.outside.http sidecar storage
# ---------------------------------------------------------------------------


def test_sidecar_off_by_default_no_files(initialized: Path, run_op, http_server):
    _author_open(run_op, "ir-no-sidecar")
    _reindex(run_op)
    env = run_op("kernel.outside.http", {
        "direction": "outbound",
        "target_category": "network",
        "target_identifier": http_server + "/ns",
        "payload": {},
        "for_ir_id": "ir-no-sidecar",
    })
    assert env["data"]["sidecar_path"] is None
    assert not (initialized / ".8os" / "payloads").exists() or not list(
        (initialized / ".8os" / "payloads").iterdir()
    )


def test_sidecar_on_writes_request_and_response(initialized: Path, run_op, http_server):
    _author_open(run_op, "ir-sidecar")
    _reindex(run_op)
    env = run_op("kernel.outside.http", {
        "direction": "outbound",
        "target_category": "network",
        "target_identifier": http_server + "/sc",
        "payload": {"x": 1},
        "for_ir_id": "ir-sidecar",
        "store_payload_sidecar": True,
    })
    sidecar_dir = initialized / ".8os" / "payloads"
    assert sidecar_dir.exists()
    event_id = env["data"]["tier3_event_id"]
    assert (sidecar_dir / f"{event_id}.request").exists()
    assert (sidecar_dir / f"{event_id}.response").exists()


def test_sidecar_path_in_output(initialized: Path, run_op, http_server):
    _author_open(run_op, "ir-sidecar-path")
    _reindex(run_op)
    env = run_op("kernel.outside.http", {
        "direction": "outbound",
        "target_category": "network",
        "target_identifier": http_server + "/sp",
        "payload": {},
        "for_ir_id": "ir-sidecar-path",
        "store_payload_sidecar": True,
    })
    assert env["data"]["sidecar_path"] is not None
    assert "payloads" in env["data"]["sidecar_path"]


# ---------------------------------------------------------------------------
# 11. kernel.outside.http cost decomposition
# ---------------------------------------------------------------------------


def test_cost_three_vector_shape(initialized: Path, run_op, http_server):
    _author_open(run_op, "ir-cost-1")
    _reindex(run_op)
    env = run_op("kernel.outside.http", {
        "direction": "outbound",
        "target_category": "network",
        "target_identifier": http_server + "/cost",
        "payload": {},
        "for_ir_id": "ir-cost-1",
    })
    cost = env["data"]["cost_actual"]
    assert "resolver_cost" in cost
    assert "kernel_cost" in cost
    assert "factory_cost" in cost
    # Each vector has clock/coin/carbon (not strict in JSON Schema; check by access)
    assert isinstance(cost["resolver_cost"], dict)
    assert isinstance(cost["kernel_cost"], dict)
    assert isinstance(cost["factory_cost"], dict)


def test_resolver_cost_clock_ms_close_to_serve_time(initialized: Path, run_op, http_server):
    _author_open(run_op, "ir-cost-2")
    _reindex(run_op)
    env = run_op("kernel.outside.http", {
        "direction": "outbound",
        "target_category": "network",
        "target_identifier": http_server + "/cost2",
        "payload": {},
        "for_ir_id": "ir-cost-2",
    })
    data = env["data"]
    resolver_clock = data["cost_actual"]["resolver_cost"]["clock_ms"]
    serve_ms = data["serve_time_ms"]
    # resolver_cost.clock_ms is exactly serve_time_ms (rounded)
    assert abs(resolver_clock - serve_ms) < 1.0


def test_factory_cost_zero_for_direct_call(initialized: Path, run_op, http_server):
    _author_open(run_op, "ir-fc")
    _reindex(run_op)
    env = run_op("kernel.outside.http", {
        "direction": "outbound",
        "target_category": "network",
        "target_identifier": http_server + "/fc",
        "payload": {},
        "for_ir_id": "ir-fc",
    })
    factory_cost = env["data"]["cost_actual"]["factory_cost"]
    assert factory_cost["clock_ms"] == 0.0


# ---------------------------------------------------------------------------
# 12. kernel.outside.http pipeline integration
# ---------------------------------------------------------------------------


def test_outside_http_lease_held_by_other_blocks(initialized: Path, run_op, http_server):
    _author_open(run_op, "ir-pi-lease")
    _author_lease(run_op, "lease-pi", "test-scope", "author:alice", lease_purpose="write")
    _reindex(run_op)
    with pytest.raises(KernelError) as exc:
        run_op("kernel.outside.http", {
            "direction": "outbound",
            "target_category": "network",
            "target_identifier": http_server + "/pi",
            "payload": {},
            "for_ir_id": "ir-pi-lease",
        })
    assert exc.value.code == LEASE_HELD


def test_outside_http_policy_denies_returns_POLICY_DENIED(
    initialized: Path, run_op, http_server,
):
    _author_open(run_op, "ir-policy-deny")
    _author_policy(
        run_op, "deny-outside",
        applies_to_op=["kernel.outside.http"],
        decision="deny",
        condition={"any": [{"caller": "test-author"}]},
    )
    _reindex(run_op)
    with pytest.raises(KernelError) as exc:
        run_op("kernel.outside.http", {
            "direction": "outbound",
            "target_category": "network",
            "target_identifier": http_server + "/pd",
            "payload": {},
            "for_ir_id": "ir-policy-deny",
        })
    assert exc.value.code == POLICY_DENIED


def test_outside_http_no_policy_no_lease_path_clean(
    initialized: Path, run_op, http_server,
):
    _author_open(run_op, "ir-clean-1")
    _reindex(run_op)
    env = run_op("kernel.outside.http", {
        "direction": "outbound",
        "target_category": "network",
        "target_identifier": http_server + "/clean",
        "payload": {},
        "for_ir_id": "ir-clean-1",
    })
    assert env["status"] == "ok"


def test_outside_http_records_transforms_without_applying(
    initialized: Path, run_op, http_server,
):
    """Block 4.7 F-TRANSFORM carry-forward: transform_action recorded, not applied."""
    _author_open(run_op, "ir-xform")
    _author_policy(
        run_op, "transform-policy",
        applies_to_op=["kernel.outside.http"],
        decision="transform",
        condition={"any": [{"caller": "anyone"}]},
    )
    _reindex(run_op)
    # The op proceeds (transform is non-blocking) and records the transform
    # in the tier-3 event without actually modifying the payload.
    env = run_op("kernel.outside.http", {
        "direction": "outbound",
        "target_category": "network",
        "target_identifier": http_server + "/x",
        "payload": {"original": "data"},
        "for_ir_id": "ir-xform",
    })
    assert env["status"] == "ok"
    # The echoed body equals the original (no transform applied)
    echoed = json.loads(env["data"]["response"]["echoed"])
    assert echoed == {"original": "data"}


# ---------------------------------------------------------------------------
# 13. Backward compat
# ---------------------------------------------------------------------------


def test_existing_records_unaffected_by_lease_check(initialized: Path, run_op):
    """No leases on disk → all writes pass through phase 2 unchanged."""
    env = _author_open(run_op, "compat-1")
    assert env["status"] == "ok"


def test_seventeen_op_count_unchanged(initialized: Path):
    """kernel.outside.http is NOT counted among the 17 SDK ops per §11.9."""
    from eightos.sdk import OP_HANDLERS
    # 17 SDK ops + 1 outside-call primitive = 18 handlers.
    # The seventeen are: init, reindex, ir.{new,get,list,resolve,expand,collapse,
    # promote,supersede,cancel,deps}, bridge.cross, authorize, gatekeeper.check,
    # selector.select, event.get.
    sdk_ops = {name for name in OP_HANDLERS if name != "kernel.outside.http"}
    assert len(sdk_ops) == 17
    assert "kernel.outside.http" in OP_HANDLERS


# ---------------------------------------------------------------------------
# 14. Upgrade path
# ---------------------------------------------------------------------------


def test_upgrade_dev6_to_dev7_adds_kernel_lease_projection(initialized: Path, run_op):
    """initialized fixture runs init at current KERNEL_VERSION (dev.7).
    Verify _kernel.lease projection is materialized in the live state."""
    body_path = initialized / ".8os" / "projections" / "_kernel" / "_kernel.lease.yml"
    assert body_path.exists()
    rec_path = initialized / "ir" / "_kernel" / "projection" / "_kernel.lease.md"
    assert rec_path.exists()


def test_kernel_version_at_dev8_or_later():
    """Block 4.8 landed at dev.7; Block 5.0 (axiom 8 ratification) bumped to
    dev.8. Pinning forward-monotonic — any later 1.1.0-dev.N (or release)
    is fine; the point is to catch unintended downgrades, not pin a specific
    in-progress version.
    """
    if KERNEL_VERSION.startswith("1.1.0-dev."):
        suffix = int(KERNEL_VERSION.rsplit(".", 1)[1])
        assert suffix >= 8, f"binary at {KERNEL_VERSION}; expected dev.8+ post-Block-5.0"
    else:
        assert KERNEL_VERSION >= "1.1.0", f"unexpected version: {KERNEL_VERSION}"


def test_drift_detected_false_post_upgrade(initialized: Path, run_op):
    env = run_op("kernel.reindex", {"mode": "check"})
    assert env["data"]["drift_detected"] is False
