"""Block 2.9 dogfood regression — verify the prediction-economics artifacts persist.

Block 2.9 authored a calibration policy, a heuristic predictor (code +
vendored (I, R)), and a pytest ground-truth runner (code + vendored
(I, R)) on the live repo. This test verifies those artifacts continue
to be present and correctly shaped after future migrations / upgrades —
catching regressions that would silently break the dogfood loop.

The test deliberately uses the LIVE repo (not a fixture) since the
artifacts were authored against the live repo as part of Block 2.9's
authentic dogfood discipline. This is unusual for the kernel test
suite — most tests use fresh inits — but the assertion is shaped as
"if the artifacts exist, they're well-formed", so it's robust to a
fresh-init fixture too.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eightos._frontmatter import parse_file


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _exists(rel: str) -> bool:
    return (REPO_ROOT / rel).exists()


@pytest.mark.skipif(
    not _exists("ir/kernel/_calibration-policies/test-result-policy.policy.md"),
    reason="Block 2.9 dogfood artifacts not present (fresh repo or test fixture)",
)
def test_calibration_policy_artifact_well_formed():
    """The Block 2.9 calibration policy carries the expected frontmatter."""
    rec = parse_file(
        REPO_ROOT / "ir/kernel/_calibration-policies/test-result-policy.policy.md"
    )
    fm = rec.frontmatter
    assert fm["policy_id"] == "test-result-policy"
    assert fm["applies_to_scope"] == "kernel"
    assert fm["predictor"] == "kernel.test-pass-predictor"
    assert fm["ground_truth_resolver"] == "kernel.pytest-runner"
    assert fm["calibration_signal"] == "ground_truth"
    assert fm["holdout_rate"] == 0.5
    assert fm["authority_level"] == "hard"
    assert "_kernel.calibration-policy" in fm["projection_types"]


@pytest.mark.skipif(
    not _exists("ir/_kernel/resolver/kernel.test-pass-predictor.md"),
    reason="Block 2.9 dogfood artifacts not present",
)
def test_predictor_resolver_artifact_well_formed():
    """The vendored predictor resolver (I, R) carries the expected shape."""
    rec = parse_file(REPO_ROOT / "ir/_kernel/resolver/kernel.test-pass-predictor.md")
    fm = rec.frontmatter
    assert fm["resolver_id"] == "kernel.test-pass-predictor"
    assert fm["bridge"] is None
    assert fm["cost_model"] == "fixed"
    assert "kernel-development/test-result" in fm["capability"]
    cap = fm["capability"]["kernel-development/test-result"]
    for letter in ("sigma", "pi", "alpha", "rho"):
        assert "declared" in cap[letter]


@pytest.mark.skipif(
    not _exists("ir/_kernel/resolver/kernel.pytest-runner.md"),
    reason="Block 2.9 dogfood artifacts not present",
)
def test_pytest_runner_resolver_artifact_well_formed():
    """The vendored pytest-runner resolver (I, R) carries the expected shape."""
    rec = parse_file(REPO_ROOT / "ir/_kernel/resolver/kernel.pytest-runner.md")
    fm = rec.frontmatter
    assert fm["resolver_id"] == "kernel.pytest-runner"
    assert fm["bridge"] is None  # local subprocess, not an outside bridge
    cap = fm["capability"]["kernel-development/test-result"]
    # Pytest is ground truth in this domain by definition — saturated capability.
    for letter in ("sigma", "pi", "alpha", "rho"):
        assert cap[letter]["declared"] == 1.0


def test_predictor_function_is_pure_and_deterministic():
    """The predictor function returns the same output for the same input."""
    from eightos.resolvers import test_pass_predictor

    diff = {
        "files_changed": ["src/eightos/sdk/ir_ops.py"],
        "lines_changed": 50,
    }
    a = test_pass_predictor.predict(diff)
    b = test_pass_predictor.predict(diff)
    assert a == b
    # Touching SDK fires the "fail" rule.
    assert a["predicted_resolution"] is False
    assert a["probability"] == 0.65


def test_predictor_handles_test_changes():
    from eightos.resolvers import test_pass_predictor

    out = test_pass_predictor.predict({
        "files_changed": ["tests/test_init.py"],
        "lines_changed": 5,
    })
    assert out["predicted_resolution"] is True
    assert out["probability"] == 0.75


def test_predictor_handles_tiny_diffs():
    from eightos.resolvers import test_pass_predictor

    out = test_pass_predictor.predict({
        "files_changed": ["docs/README.md"],
        "lines_changed": 3,
    })
    assert out["predicted_resolution"] is True
    assert out["probability"] == 0.90
