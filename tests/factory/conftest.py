"""Factory-test fixtures.

Builds on the shared `tests/conftest.py` fixtures (`repo`, `run_op`,
`initialized`). Adds helpers for authoring synthetic resolvers, bridges,
and intentions directly to disk — bypassing `kernel.ir.new` because the
factory's `implementation:` field is not declared in the vendored
`_kernel.resolver` body (per OPEN-Q-026), so `validate_extensions`
would reject SDK-authored resolver records carrying it.

DIRECT-TO-DISK + REINDEX RULE (surfaced Block 3 Piece 1, codified
Piece 2): any code path that writes (I, R) records directly to
disk — bypassing `kernel.ir.new` — must follow with
`kernel.reindex --mode full` so the kernel's `id-to-path` index
sees the new records. Without it, downstream ops (`kernel.ir.resolve`,
`kernel.selector.select`, etc.) raise `NOT_FOUND` because they look
up records via the index, not the filesystem. The `_reindex`
helper below applies after every authoring fixture call. The same
rule applies to migration scripts and any other non-SDK authoring
path.

Per Block 3 Piece 2 walker fix: synthetic intentions do NOT carry
a `resolver_id` frontmatter field. The Piece 1 fixture wrote that
field as a "factory hint" — that was a fixture-masked bug because
the walker also checked the same wrong field. Intentions never
carry a pre-resolution resolver pointer under v1.0; the selector
picks dynamically. See OPEN-Q-027 for the disambiguation note.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from eightos._frontmatter import IRRecord, serialize


def _resolver_record(
    resolver_id: str,
    *,
    bridge: str | None = None,
    implementation: str | None = None,
    standing_authorization: str | None = None,
) -> IRRecord:
    fm = {
        "id": resolver_id,
        "kind": "ir-node",
        "scope": "_kernel",
        "tier": 1,
        "status": "open",
        "authority_level": "hard",
        "authored_by": "kernel.self",
        "authored_on": "2026-04-27T00:00:00.000Z",
        "authored_via": "kernel.self",
        "projection_types": ["_kernel.resolver"],
        "depends_on": [],
        "visible_to": ["_kernel"],
        "resolver_id": resolver_id,
        "display_name": resolver_id,
        "bridge": bridge,
        "cost": {"clock_ms": 1, "coin_usd": 0, "carbon_g": 0, "currency": "USD"},
        "capability": {"test/domain": {
            "sigma": {"declared": 0.5, "measured": None},
            "pi": {"declared": 0.5, "measured": None},
            "alpha": {"declared": 0.5, "measured": None},
            "rho": {"declared": 0.5, "measured": None},
        }},
        "cost_model": "fixed",
        "model_name": None,
        "parent": None,
        "expanded_into": None,
        "resolution_event": None,
        "resolved_at": None,
        "resolver": None,
        "revalidate_trigger": None,
        "superseded_by": None,
        "supersedes": None,
        "surrogate_of": None,
        "valid_through": None,
        "collapsed_summary": resolver_id,
    }
    if implementation is not None:
        fm["implementation"] = implementation
    if standing_authorization is not None:
        fm["standing_authorization"] = standing_authorization
    return IRRecord(
        frontmatter=fm,
        intention_text=f"Synthetic resolver {resolver_id}.",
        resolution_text=None,
    )


def _intention_record(
    intention_id: str,
    *,
    scope: str,
    depends_on: list[str] | None = None,
    status: str = "open",
    projection_types: list[str] | None = None,
    domain: str | None = None,
) -> IRRecord:
    """Build a synthetic intention (I, R) record.

    Per Block 3 Piece 2 walker fix: intentions do NOT carry a
    `resolver_id` frontmatter field. The canonical pre-resolution
    pointer for "which resolver should run" is decided by the
    selector at dispatch time; intentions only carry `resolver`
    (set at resolution time by `kernel.ir.resolve`). Tests that
    want to influence selector choice should set up the resolver
    pool's capability vectors and call tick with the matching
    `domain` parameter, not pre-stamp a resolver on the intention.

    `domain` (optional) lands in frontmatter as a non-canonical
    extension — the factory's `tick` reads it as a fallback when
    no explicit `domain` is passed in. This anticipates OPEN-Q-019's
    eventual lift of `domain` to base frontmatter.
    """
    fm = {
        "id": intention_id,
        "kind": "ir-node",
        "scope": scope,
        "tier": 1,
        "status": status,
        "authority_level": "convention",
        "authored_by": "test",
        "authored_on": "2026-04-27T00:00:00.000Z",
        "authored_via": "outside",
        "projection_types": projection_types or [],
        "depends_on": depends_on or [],
        "visible_to": [scope],
        "display_name": intention_id,
        "parent": None,
        "expanded_into": None,
        "resolution_event": None,
        "resolved_at": None,
        "resolver": None,
        "revalidate_trigger": None,
        "superseded_by": None,
        "supersedes": None,
        "surrogate_of": None,
        "valid_through": None,
    }
    if domain is not None:
        fm["domain"] = domain
    return IRRecord(
        frontmatter=fm,
        intention_text=f"Synthetic intention {intention_id}.",
        resolution_text=None,
    )


def _reindex(repo: Path) -> None:
    """Regenerate indexes after direct-to-disk record authoring.

    Records written via the helpers below bypass `kernel.ir.new`
    (because the factory's `implementation:` field is not declared in
    the vendored `_kernel.resolver` body — see OPEN-Q-026), so the
    kernel's id-to-path index does not see them until reindex runs.
    Without this, `kernel.ir.resolve` raises NOT_FOUND for the
    directly-authored intention.
    """
    from eightos.sdk._runner import run as run_op

    run_op("kernel.reindex", {"mode": "rebuild"})


@pytest.fixture
def author_resolver(initialized: Path):
    """Write a synthetic `_kernel.resolver` (I, R) directly to disk."""

    def _author(resolver_id: str, **kwargs: Any) -> Path:
        rec = _resolver_record(resolver_id, **kwargs)
        path = initialized / "ir" / "_kernel" / "resolver" / f"{resolver_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialize(rec))
        _reindex(initialized)
        return path

    return _author


@pytest.fixture
def author_intention(initialized: Path):
    """Write a synthetic intention (I, R) directly to disk under ir/<scope>/."""

    def _author(intention_id: str, *, scope: str = "test-scope", **kwargs: Any) -> Path:
        rec = _intention_record(intention_id, scope=scope, **kwargs)
        path = initialized / "ir" / scope / f"{intention_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialize(rec))
        _reindex(initialized)
        return path

    return _author


def _calibration_policy_record(
    policy_id: str,
    *,
    applies_to_scope: str,
    predictor: str,
    ground_truth_resolver: str,
    applies_to_domain: str | None = None,
    holdout_rate: float = 0.0,
) -> IRRecord:
    """Build a `_kernel.calibration-policy` (I, R) record for tests."""
    fm = {
        "id": policy_id,
        "kind": "ir-node",
        "scope": applies_to_scope,
        "tier": 1,
        "status": "open",
        "authority_level": "hard",
        "authored_by": "test",
        "authored_on": "2026-04-27T00:00:00.000Z",
        "authored_via": "outside",
        "projection_types": ["_kernel.calibration-policy"],
        "depends_on": [],
        "visible_to": [applies_to_scope],
        "policy_id": policy_id,
        "applies_to_scope": applies_to_scope,
        "applies_to_domain": applies_to_domain,
        "predictor": predictor,
        "ground_truth_resolver": ground_truth_resolver,
        "holdout_rate": holdout_rate,
        "ground_truth_timeout": "PT5M",
        "calibration_signal": "ground_truth",
        "recalibration_trigger": {"kind": "count", "params": {"n": 10}},
        "parent": None,
        "expanded_into": None,
        "resolution_event": None,
        "resolved_at": None,
        "resolver": None,
        "revalidate_trigger": None,
        "superseded_by": None,
        "supersedes": None,
        "surrogate_of": None,
        "valid_through": None,
        "collapsed_summary": f"Test calibration policy {policy_id}.",
    }
    return IRRecord(
        frontmatter=fm,
        intention_text=f"Test calibration policy {policy_id}.",
        resolution_text=None,
    )


@pytest.fixture
def author_calibration_policy(initialized: Path):
    """Write a `_kernel.calibration-policy` (I, R) directly to disk.

    Subdirectory placement matches v1.0.1-partial Amendment 1
    (target_subdirectory: _calibration-policies on the projection).
    """

    def _author(policy_id: str, **kwargs: Any) -> Path:
        rec = _calibration_policy_record(policy_id, **kwargs)
        applies_to_scope = kwargs["applies_to_scope"]
        path = (
            initialized
            / "ir"
            / applies_to_scope
            / "_calibration-policies"
            / f"{policy_id}.policy.md"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialize(rec))
        _reindex(initialized)
        return path

    return _author
