"""Tests for kernel.init — the self-describing bootstrap."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eightos import KERNEL_BINARY_RESOLVER_ID, __version__ as KERNEL_VERSION
from eightos.errors import KERNEL_VERSION_MISMATCH, KernelError
from eightos._frontmatter import parse_file


VALID_INIT = {
    "project_name": "test-project",
    "primary_scope_id": "test-scope",
    "primary_operator_id": "test-author",
    "kernel_version": KERNEL_VERSION,
}


def test_init_creates_skeleton(repo: Path, run_op):
    envelope = run_op("kernel.init", VALID_INIT)
    assert envelope["status"] == "ok"
    assert envelope["op"] == "kernel.init"
    assert envelope["data"]["bootstrap_ir_id"] == "000-bootstrap"
    assert envelope["data"]["mode"] == "fresh"
    assert (repo / ".8os" / "version").read_text().strip() == KERNEL_VERSION
    # v0.2 / Patch 1: scope declarations are (I, R)s under ir/_kernel/scope/,
    # not _scope.yml files alongside the scope's tier 1 content.
    assert (repo / "ir" / "_kernel" / "scope" / "test-scope.md").exists()
    assert (repo / "ir" / "test-scope" / "000-bootstrap.md").exists()
    # Every kernel index present (the named indexes plus _checksum).
    # v1.0 §6.1 adds calibration-corpus.
    # v1.1 §3.17 (Block 4.7) adds policy-evaluations.
    # v1.1 §3.17 (Block 4.8) adds lease-holders and payload-hash-to-events.
    idx = repo / ".8os" / "index"
    expected = {
        "id-to-path", "path-to-id", "scope-to-ids", "tier-to-ids",
        "projection-to-ids", "resolver-to-events", "bridge-to-resolvers",
        "deps-forward", "deps-reverse", "temporal", "surrogate-lineage",
        "calibration-corpus",
        "policy-evaluations",
        "lease-holders",
        "payload-hash-to-events",
        "_checksum",
    }
    actual = {p.stem for p in idx.glob("*.yml")}
    assert actual == expected
    # Schemas vendored.
    schemas = repo / ".8os" / "sdk" / "schemas"
    assert (schemas / "kernel.init.v1.input.json").exists()


def test_init_bootstrap_records_its_own_event(repo: Path, run_op):
    """The bootstrap (I, R) must reference the tier 3 event of its own creation."""
    envelope = run_op("kernel.init", VALID_INIT)
    event_id = envelope["event_id"]

    rec = parse_file(repo / "ir" / "test-scope" / "000-bootstrap.md")
    assert rec.frontmatter["resolution_event"] == event_id
    assert rec.frontmatter["status"] == "resolved"
    # OPEN-Q-008-RESOLVED: the resolver id for kernel-self-observed records is
    # the version-suffixed kernel binary id (`kernel.binary@<version>`), not
    # the bare "kernel" v0.1 used. The bridge through which the observation
    # was authored remains kernel.self (recorded in `authored_via`). See
    # BLOCK-2.7-SPEC-CORRECTIONS Question 1 + the cogito mechanics in §2.4.
    assert rec.frontmatter["resolver"] == KERNEL_BINARY_RESOLVER_ID
    assert rec.frontmatter["authored_via"] == "kernel.self"
    assert rec.frontmatter["authority_level"] == "hard"

    # And the event line exists in the JSONL.
    jsonl = next((repo / ".8os" / "events").rglob("*.jsonl"))
    lines = jsonl.read_text().strip().splitlines()
    events = [json.loads(ln) for ln in lines]
    assert any(ev["event_id"] == event_id for ev in events)


def test_init_is_idempotent_at_matching_version(repo: Path, run_op):
    """v1.0 §7.2: re-running init against an initialized repo whose state
    version matches the kernel binary is a noop — not an error. The old
    behavior (raise ALREADY_EXISTS) contradicted the spec's idempotency
    promise; v0.2 → v1.0 upgrade-mode wiring removes the contradiction.
    """
    first = run_op("kernel.init", VALID_INIT)
    assert first["data"]["mode"] == "fresh"
    second = run_op("kernel.init", VALID_INIT)
    assert second["data"]["mode"] == "noop"
    assert second["event_id"] is None
    assert second["data"]["bootstrap_ir_id"] == first["data"]["bootstrap_ir_id"]
    # Bootstrap (I, R) untouched by the noop.
    assert (repo / first["data"]["bootstrap_path"]).read_text() == (
        repo / first["data"]["bootstrap_path"]
    ).read_text()


def test_init_rejects_kernel_version_mismatch(repo: Path, run_op):
    payload = dict(VALID_INIT, kernel_version="0.99.0")
    with pytest.raises(KernelError) as excinfo:
        run_op("kernel.init", payload)
    assert excinfo.value.code == KERNEL_VERSION_MISMATCH


def test_init_validates_input_schema(repo: Path, run_op):
    """Missing required field surfaces SCHEMA_INVALID with field locator."""
    bad = dict(VALID_INIT)
    del bad["primary_operator_id"]
    with pytest.raises(KernelError) as excinfo:
        run_op("kernel.init", bad)
    assert excinfo.value.code == "SCHEMA_INVALID"


# ---- v1.0 §7.2 upgrade-mode -----------------------------------------------


def _strip_v1_content_to_simulate_v02(repo: Path, run_op) -> None:
    """Reverse-engineer a v0.2-state repo from a fresh v1.0 init.

    Removes the three v1.0 projection bodies, three v1.0 projection-definition
    (I, R)s, kernel.voi resolver (I, R), then writes 0.2.0 to .8os/version
    and re-runs reindex --mode full so the indexes match the stripped state.
    Mirrors what an actual v0.2 repo would look like: vendored content lacking
    the v1.0 additions, version file at 0.2.0.
    """
    body_dir = repo / ".8os" / "projections" / "_kernel"
    proj_dir = repo / "ir" / "_kernel" / "projection"
    res_dir = repo / "ir" / "_kernel" / "resolver"
    for ptype in (
        "_kernel.prediction",
        "_kernel.calibration-policy",
        "_kernel.calibration-policy-proposal",
    ):
        (body_dir / f"{ptype}.yml").unlink()
        (proj_dir / f"{ptype}.md").unlink()
    (res_dir / "kernel.voi.md").unlink()
    (repo / ".8os" / "version").write_text("0.2.0\n")
    run_op("kernel.reindex", {"mode": "rebuild"})


def test_init_upgrades_v02_repo_to_v1_idempotently(repo: Path, run_op):
    """v1.0 §7.2: init against a v0.2-state repo with v1.0 binary folds in
    new vendored content (three projection bodies, three projection-definition
    (I, R)s, kernel.voi resolver). Second run is a noop. Existing user-scope
    content untouched.
    """
    run_op("kernel.init", VALID_INIT)
    bootstrap_text_before = (repo / "ir" / "test-scope" / "000-bootstrap.md").read_text()
    _strip_v1_content_to_simulate_v02(repo, run_op)

    env = run_op("kernel.init", VALID_INIT)
    assert env["data"]["mode"] == "upgrade"
    assert env["data"]["previous_version"] == "0.2.0"
    assert env["data"]["kernel_version"] == KERNEL_VERSION
    added = env["data"]["added"]
    assert set(added["vendored_projection_bodies"]) == {
        "_kernel.prediction",
        "_kernel.calibration-policy",
        "_kernel.calibration-policy-proposal",
    }
    assert set(added["projection_definitions"]) == {
        "_kernel.prediction",
        "_kernel.calibration-policy",
        "_kernel.calibration-policy-proposal",
    }
    assert added["kernel_internal_resolvers"] == ["kernel.voi"]

    # Vendored content present.
    assert (repo / ".8os" / "projections" / "_kernel" / "_kernel.prediction.yml").exists()
    assert (repo / "ir" / "_kernel" / "resolver" / "kernel.voi.md").exists()
    # Version file last write — repo is now at the kernel binary's version.
    assert (repo / ".8os" / "version").read_text().strip() == KERNEL_VERSION
    # Bootstrap (I, R) untouched.
    assert (repo / "ir" / "test-scope" / "000-bootstrap.md").read_text() == bootstrap_text_before
    # Reindex --check is deterministic post-upgrade.
    check = run_op("kernel.reindex", {"mode": "check"})
    assert check["data"]["drift_detected"] is False

    # Second run is a noop — idempotency guarantee.
    second = run_op("kernel.init", VALID_INIT)
    assert second["data"]["mode"] == "noop"
    assert second["event_id"] is None
    assert second["data"]["added"]["vendored_projection_bodies"] == []


def test_init_upgrade_emits_one_tier3_event_in_ops(repo: Path, run_op):
    """v1.0 §7.2 + Block 2.9 Task 0a spec: upgrade-mode emits exactly one
    tier 3 event recording the upgrade. The event is authored through
    kernel.self (cogito), payload lists every vendored file added.
    """
    run_op("kernel.init", VALID_INIT)
    _strip_v1_content_to_simulate_v02(repo, run_op)
    env = run_op("kernel.init", VALID_INIT)
    upgrade_event_id = env["event_id"]
    assert upgrade_event_id is not None

    jsonl = next((repo / ".8os" / "events").rglob("*.jsonl"))
    events = [json.loads(ln) for ln in jsonl.read_text().strip().splitlines() if ln]
    matched = [e for e in events if e.get("event_id") == upgrade_event_id]
    assert len(matched) == 1
    upgrade = matched[0]
    # Provenance: authored through kernel.self (cogito).
    assert upgrade["bridge_id"] == "kernel.self"
    assert upgrade["resolver_id"] == KERNEL_BINARY_RESOLVER_ID
    # In _ops scope.
    assert upgrade["intention"]["scope"] == "_ops"
    # Payload lists every vendored file added.
    structured = upgrade["resolution"]["structured"]
    assert structured["previous_version"] == "0.2.0"
    assert structured["new_version"] == KERNEL_VERSION
    assert "_kernel.prediction" in structured["projection_definitions_added"]
    assert "kernel.voi" in structured["kernel_internal_resolvers_added"]


def test_init_rejects_repo_newer_than_binary(repo: Path, run_op):
    """v1.0 §7.2: refuse when the repo's representation version is newer
    than the binary's — that would be a downgrade in place, which the
    upgrade-mode mechanism does not handle."""
    run_op("kernel.init", VALID_INIT)
    (repo / ".8os" / "version").write_text("9.9.9\n")
    with pytest.raises(KernelError) as excinfo:
        run_op("kernel.init", VALID_INIT)
    assert excinfo.value.code == KERNEL_VERSION_MISMATCH


def test_init_upgrade_refreshes_changed_vendored_bodies(repo: Path, run_op):
    """Vendored projection bodies are sealed against user edits but the
    binary owns them across versions. Upgrade-mode rewrites bodies whose
    content differs from the binary's current declarations (e.g., Block
    2.8's additive amendments to `_kernel.authorization`, `_kernel.resolver`,
    `_kernel.scope`). Bodies whose content is unchanged are left alone.
    """
    run_op("kernel.init", VALID_INIT)
    body_path = repo / ".8os" / "projections" / "_kernel" / "_kernel.resolver.yml"
    # Replace the v1.0 vendored body with a stripped-down v0.2 shape (no
    # cost_model/cost_per_depth_unit/depth_grid optional fields).
    body_path.write_text(
        "body_shape: free\n"
        "filename_suffix: .md\n"
        "optional_frontmatter:\n"
        "- description: for LLM resolvers, the model id\n"
        "  name: model_name\n"
        "  type: string|null\n"
        "projection_id: _kernel.resolver\n"
        "required_frontmatter:\n"
        "- description: must equal the (I, R)'s id\n"
        "  name: resolver_id\n"
        "  type: string\n"
        "- description: human-readable name\n"
        "  name: display_name\n"
        "  type: string\n"
        "- description: bridge id, or null for inside resolvers\n"
        "  name: bridge\n"
        "  type: string|null\n"
        "- description: '{clock_ms, coin_usd, carbon_g, currency}'\n"
        "  name: cost\n"
        "  type: object\n"
        "- description: '{<domain>: {sigma, pi, alpha, rho}}'\n"
        "  name: capability\n"
        "  type: object\n"
        "spec_reference: docs/spec/8OS-BLOCK-1-SPEC.md#3-3-_kernel-resolver\n"
    )
    (repo / ".8os" / "version").write_text("0.2.0\n")
    run_op("kernel.reindex", {"mode": "rebuild"})

    env = run_op("kernel.init", VALID_INIT)
    assert env["data"]["mode"] == "upgrade"
    refreshed = env["data"]["refreshed"]["vendored_projection_bodies"]
    assert "_kernel.resolver" in refreshed
    # The refreshed body now contains the v1.0 optional fields.
    refreshed_body = body_path.read_text()
    assert "cost_model" in refreshed_body
    assert "depth_grid" in refreshed_body
