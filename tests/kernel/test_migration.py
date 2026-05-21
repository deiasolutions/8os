"""Tests for the v0.1.0 → v0.2 migration script.

Synthesizes a minimal v0.1 repo state in tmp_path, runs the migration,
asserts post-state shape, then runs the migration again and asserts
bit-for-bit no-op (idempotency anchor — Phase 4.3's version bump is what
guarantees this).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from eightos import KERNEL_BINARY_RESOLVER_ID
from eightos._frontmatter import parse_file
from eightos._yaml import dump_yaml


# Load the migration script as a module despite its non-identifier filename.
_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "migrate-v0.1-to-v0.2.py"
_spec = importlib.util.spec_from_file_location("migration_script", _SCRIPT)
assert _spec and _spec.loader
migration_script = importlib.util.module_from_spec(_spec)
sys.modules["migration_script"] = migration_script
_spec.loader.exec_module(migration_script)
migrate = migration_script.migrate


# ---------------------------------------------------------------------------
# Synthetic v0.1 fixture builders
# ---------------------------------------------------------------------------


def _v01_skeleton(repo: Path) -> None:
    (repo / ".8os").mkdir()
    (repo / ".8os" / "version").write_text("0.1.0\n")
    (repo / ".8os" / "events" / "2026" / "04" / "26").mkdir(parents=True)
    (repo / ".8os" / "events" / "2026" / "04" / "26" / "events.jsonl").write_text("")
    (repo / ".8os" / "index").mkdir()
    (repo / ".8os" / "projections" / "_kernel").mkdir(parents=True)


def _v01_user_scope(repo: Path, scope_id: str = "test-scope", operator_id: str = "test-op") -> None:
    sd = repo / "ir" / scope_id
    sd.mkdir(parents=True)
    (sd / "_scope.yml").write_text(
        dump_yaml({"id": scope_id, "kind": "scope", "display_name": f"Scope {scope_id}"})
    )
    bootstrap = """---
id: 000-bootstrap
kind: ir-node
tier: 1
projection_types: []
collapsed_summary: 'Bootstrap'
expanded_into: null
parent: null
scope: """ + scope_id + """
depends_on: []
visible_to: ['""" + scope_id + """']
resolved_at: '2026-04-26T00:00:00Z'
valid_through: null
revalidate_trigger: null
status: resolved
resolver: kernel
resolution_event: 01XXXBOOTSTRAP00000000000000
authored_by: """ + operator_id + """
authored_on: '2026-04-26T00:00:00Z'
authority_level: hard
bridge_type: kernel.self
supersedes: null
superseded_by: null
surrogate_of: null
---
# Bootstrap

The kernel started here.
"""
    (sd / "000-bootstrap.md").write_text(bootstrap)


def _v01_resolver(repo: Path, rid: str = "claude-sonnet", bridge: str = "anthropic-api") -> None:
    rd = repo / ".8os" / "resolvers"
    rd.mkdir(exist_ok=True)
    (rd / f"{rid}.yml").write_text(dump_yaml({
        "id": rid,
        "kind": "resolver",
        "display_name": "Claude Sonnet",
        "bridge": bridge,
        "cost": {
            "clock": {"unit": "ms", "declared": 800, "measured_p50": None, "measured_p95": None},
            "coin": {"unit": "usd", "declared": 0.003, "measured_p50": None},
            "carbon": {"unit": "g-co2e", "declared": 0.5, "measured_p50": None},
        },
        "capability": [
            {
                "domain": "code-gen",
                "sigma": {"declared": 0.85, "measured": None, "sample_n": 0},
                "pi": {"declared": 0.7, "measured": None},
                "alpha": {"declared": 0.9, "measured": None},
                "rho": {"declared": 0.95, "measured": None},
            }
        ],
        "authored_by": "test-op",
        "authority_default": "convention",
    }))


def _v01_bridge(repo: Path, bid: str = "anthropic-api", with_default_cost: bool = True) -> None:
    bd = repo / ".8os" / "bridges"
    bd.mkdir(exist_ok=True)
    doc: dict[str, Any] = {
        "id": bid,
        "kind": "bridge",
        "display_name": "Anthropic API",
        "outside_type": "llm-api",
        "outside_label": "Anthropic Sonnet via HTTPS",
        "endpoint": {"protocol": "https", "address": "https://api.anthropic.com"},
        "synchronous": True,
        "batchable": False,
        "rate_limit": {"unit": "requests-per-minute", "value": 60},
        "requires_authorization": True,
        "authorization_authority": "convention",
        "authored_by": "test-op",
        "authored_on": "2026-04-26T00:00:00Z",
        "status": "active",
    }
    if with_default_cost:
        doc["default_cost"] = {"clock_ms_p50": 800, "coin_usd_p50": 0.003, "carbon_g_p50": 0.5}
    (bd / f"{bid}.yml").write_text(dump_yaml(doc))


def _v01_project_projection(repo: Path, *, suffix_field: str = "file_extension") -> None:
    """A Block 2.5-era projection yaml. The actual Block 2.5 wrote
    `file_extension`; v0.2 §3.2 standardized on `filename_suffix`. Migration
    translates; the test surface matches what Block 2.5 actually produced."""
    pd = repo / ".8os" / "projections"
    pd.mkdir(exist_ok=True)
    (pd / "prism-ir.yml").write_text(dump_yaml({
        "applies_to_tier": 1,
        suffix_field: ".prism.md",
        "body_shape": "yaml-fenced",
        "required_body_top_level_keys": ["v", "id", "name", "intention", "nodes", "edges"],
        "spec_reference": "docs/spec/PRISM-IR-SPEC-v1.1.md",
    }))


def _v01_prism_record(repo: Path, scope_id: str = "test-scope") -> None:
    """A v0.1 PRISM-IR (I, R) with the .prism slug suffix (Block 2.5 OPEN-Q-012)."""
    sd = repo / "ir" / scope_id
    sd.mkdir(parents=True, exist_ok=True)
    body = """---
id: expense-approval.prism
kind: ir-node
tier: 1
projection_types: ['prism-ir']
collapsed_summary: 'Expense approval flow'
expanded_into: null
parent: null
scope: """ + scope_id + """
depends_on: []
visible_to: ['""" + scope_id + """']
resolved_at: null
valid_through: null
revalidate_trigger: null
status: open
resolver: null
resolution_event: null
authored_by: test-op
authored_on: '2026-04-26T00:00:00Z'
authority_level: convention
bridge_type: null
supersedes: null
superseded_by: null
surrogate_of: null
---
```yaml
v: 1.1.0
id: expense-approval.prism
name: Expense Approval
intention: classify and route an expense
nodes:
  - {id: classify, kind: step}
edges: []
```
"""
    (sd / "expense-approval.prism.md").write_text(body)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_migration_idempotent(tmp_path: Path):
    """First run migrates; second run is a no-op."""
    _v01_skeleton(tmp_path)
    _v01_user_scope(tmp_path)
    _v01_resolver(tmp_path)
    _v01_bridge(tmp_path)

    result1 = migrate(tmp_path, operator_id="test-op")
    assert result1["already_migrated"] is False
    assert (tmp_path / ".8os" / "version").read_text().strip() == "0.2.0"

    # Snapshot file tree + content hashes after first run.
    snapshot = _snapshot_tree(tmp_path)

    result2 = migrate(tmp_path, operator_id="test-op")
    assert result2["already_migrated"] is True

    snapshot2 = _snapshot_tree(tmp_path)
    assert snapshot == snapshot2, "second migration run was not a no-op"


def test_migration_preserves_record_bodies(tmp_path: Path):
    """Existing v0.1 (I, R) bodies are byte-equal post-migration."""
    _v01_skeleton(tmp_path)
    _v01_user_scope(tmp_path)
    _v01_resolver(tmp_path)
    _v01_bridge(tmp_path)
    pre_body = parse_file(tmp_path / "ir" / "test-scope" / "000-bootstrap.md").intention_text
    pre_resolution = parse_file(tmp_path / "ir" / "test-scope" / "000-bootstrap.md").resolution_text

    migrate(tmp_path, operator_id="test-op")

    post = parse_file(tmp_path / "ir" / "test-scope" / "000-bootstrap.md")
    assert post.intention_text == pre_body
    assert post.resolution_text == pre_resolution


def test_migration_prism_id_clean(tmp_path: Path):
    """expense-approval.prism → expense-approval; filename retains .prism.md."""
    _v01_skeleton(tmp_path)
    _v01_user_scope(tmp_path)
    _v01_project_projection(tmp_path)
    _v01_prism_record(tmp_path)

    migrate(tmp_path, operator_id="test-op")

    # Filename preserved (the projection's filename_suffix declaration).
    f = tmp_path / "ir" / "test-scope" / "expense-approval.prism.md"
    assert f.exists()
    fm = parse_file(f).frontmatter
    # Id is now clean — no .prism suffix.
    assert fm["id"] == "expense-approval"


def test_migration_resolver_rewrite_only_when_cogito(tmp_path: Path):
    """A v0.1 record with resolver=kernel + bridge_type=kernel.self gets the
    version-suffixed kernel.binary id. Records with bridge_type pointing
    elsewhere are left alone (refinement: only when authored_via==kernel.self
    after the Patch 5 rename)."""
    _v01_skeleton(tmp_path)
    _v01_user_scope(tmp_path)  # bootstrap (I, R) has bridge_type: kernel.self
    # And a non-cogito v0.1 record with resolver=kernel:
    sd = tmp_path / "ir" / "test-scope"
    (sd / "non-cogito.md").write_text("""---
id: non-cogito
kind: ir-node
tier: 1
projection_types: []
collapsed_summary: 'unrelated'
expanded_into: null
parent: null
scope: test-scope
depends_on: []
visible_to: ['test-scope']
resolved_at: null
valid_through: null
revalidate_trigger: null
status: open
resolver: kernel
resolution_event: null
authored_by: test-op
authored_on: '2026-04-26T00:00:00Z'
authority_level: convention
bridge_type: anthropic-api
supersedes: null
superseded_by: null
surrogate_of: null
---
# Non-cogito record
""")

    migrate(tmp_path, operator_id="test-op")

    cogito_fm = parse_file(sd / "000-bootstrap.md").frontmatter
    non_cogito_fm = parse_file(sd / "non-cogito.md").frontmatter

    # Cogito record: resolver rewritten.
    assert cogito_fm["resolver"] == KERNEL_BINARY_RESOLVER_ID
    assert cogito_fm["authored_via"] == "kernel.self"
    # Non-cogito record: resolver untouched, bridge_type renamed but value preserved.
    assert non_cogito_fm["resolver"] == "kernel"
    assert non_cogito_fm["authored_via"] == "anthropic-api"


def test_migration_event_emitted(tmp_path: Path):
    """Exactly one tier 3 migration event with the documented schema."""
    _v01_skeleton(tmp_path)
    _v01_user_scope(tmp_path)
    _v01_bridge(tmp_path)

    result = migrate(tmp_path, operator_id="test-op")

    # Find the event in JSONL.
    jsonls = list((tmp_path / ".8os" / "events").rglob("*.jsonl"))
    events = []
    for j in jsonls:
        for ln in j.read_text().splitlines():
            if ln.strip():
                events.append(json.loads(ln))
    migration_events = [e for e in events if e["event_id"] == result["event_id"]]
    assert len(migration_events) == 1
    me = migration_events[0]
    structured = me["resolution"]["structured"]
    assert structured["schema"] == "8os.migration.v1"
    assert structured["from_version"] == "0.1.0"
    assert structured["to_version"] == "0.2.0"
    assert isinstance(structured["records_created"], list)
    assert isinstance(structured["records_removed"], list)
    assert isinstance(structured["records_rewritten"], list)
    assert isinstance(structured["warnings"], list)
    # The bridge migration writes a default scope_of_authority warning.
    warning_types = {w["type"] for w in structured["warnings"]}
    assert "default-scope-of-authority" in warning_types


def test_migration_translates_file_extension_to_filename_suffix(tmp_path: Path):
    """Block 2.5 ad hoc projection yamls used `file_extension`; v0.2 §3.2
    standardized on `filename_suffix`. Migration translates the field name."""
    _v01_skeleton(tmp_path)
    _v01_user_scope(tmp_path)
    _v01_project_projection(tmp_path)  # uses file_extension
    _v01_prism_record(tmp_path)

    migrate(tmp_path, operator_id="test-op")

    proj_md = tmp_path / "ir" / "_kernel" / "projection" / "prism-ir.md"
    body = proj_md.read_text()
    assert "filename_suffix: .prism.md" in body
    assert "file_extension:" not in body
    # And the suffix-stripped id transition succeeds because the renamed field
    # is now what phase 3.5 reads.
    fm = parse_file(tmp_path / "ir" / "test-scope" / "expense-approval.prism.md").frontmatter
    assert fm["id"] == "expense-approval"


def test_migration_no_false_collision_warnings(tmp_path: Path):
    """Vendored _kernel.bridge records (kernel.self, human-<op>) carry both
    bridge_type (projection extension, category enum) and authored_via (base
    provenance) by design. Phase 3.2's rename must skip them."""
    _v01_skeleton(tmp_path)
    _v01_user_scope(tmp_path)
    result = migrate(tmp_path, operator_id="test-op")
    collisions = [w for w in result["warnings"] if w["type"] == "frontmatter-collision"]
    assert collisions == [], f"unexpected frontmatter-collision warnings: {collisions!r}"


def test_migration_bridge_default_cost_envelope_uncalibrated(tmp_path: Path):
    """Bridges migrated without v0.1 default_cost get authority_level: uncalibrated."""
    _v01_skeleton(tmp_path)
    _v01_user_scope(tmp_path)
    _v01_bridge(tmp_path, bid="no-defaults", with_default_cost=False)

    migrate(tmp_path, operator_id="test-op")

    fm = parse_file(tmp_path / "ir" / "_kernel" / "bridge" / "no-defaults.md").frontmatter
    assert fm["authority_level"] == "uncalibrated"
    assert fm["cost_envelope"] == {"clock_ms_max": None, "coin_usd_max": None, "carbon_g_max": None}


def test_migration_refreshes_schemas(tmp_path: Path):
    """v0.1 init wrote schemas for removed ops (kernel.bridge.add, .resolver.add).
    Migration must clear .8os/sdk/schemas/ and re-vendor from the current package
    so the on-disk schema set matches the running v0.2 kernel."""
    _v01_skeleton(tmp_path)
    _v01_user_scope(tmp_path)
    # Plant fake v0.1-only schema files like Block 2.5's init produced.
    schemas = tmp_path / ".8os" / "sdk" / "schemas"
    schemas.mkdir(parents=True)
    (schemas / "kernel.bridge.add.v1.input.json").write_text("{}")
    (schemas / "kernel.resolver.add.v1.input.json").write_text("{}")

    migrate(tmp_path, operator_id="test-op")

    # Stale schemas removed; current schemas vendored.
    assert not (schemas / "kernel.bridge.add.v1.input.json").exists()
    assert not (schemas / "kernel.resolver.add.v1.input.json").exists()
    assert (schemas / "kernel.ir.new.v1.input.json").exists()
    assert (schemas / "kernel.bridge.cross.v1.input.json").exists()


def test_migration_already_v02_is_noop(tmp_path: Path):
    """Running on a repo already at 0.2.0 is a clean no-op."""
    (tmp_path / ".8os").mkdir()
    (tmp_path / ".8os" / "version").write_text("0.2.0\n")
    result = migrate(tmp_path)
    assert result["already_migrated"] is True


def _snapshot_tree(root: Path) -> dict[str, str]:
    """Map of relative-path → content-hash for every file in the tree."""
    import hashlib

    out: dict[str, str] = {}
    for f in sorted(root.rglob("*")):
        if f.is_file():
            rel = str(f.relative_to(root))
            out[rel] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out
