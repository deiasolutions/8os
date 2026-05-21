"""kernel.pytest-runner — ground-truth resolver for Block 2.9 dogfood.

Runs `uv run pytest` in a subprocess and records the result. This is the
ground-truth resolver that the calibration policy
`test-result-policy` names alongside the heuristic predictor at
`kernel.test-pass-predictor`. Together they form the (predictor,
ground-truth-resolver) pair that the v1.0 selector + VOI + calibrator
machinery exercises in Block 2.9's dogfood.

The vendored (I, R) at `ir/_kernel/resolver/kernel.pytest-runner.md`
references this module. Block 3's factory will dispatch the runner
through the kernel; in Block 2.9 the function is invoked by hand once
per dogfood cycle (or per holdout decision when the selector says
escalate or run-both-with-comparison).

Bridge decision (`bridge: null`):

The runner lives entirely inside the kernel project. It runs pytest on
the kernel's own source tree — self-observation, not outside-call.
Axiom 0's `outside is opaque, kernel observes through bridges but
cannot decompose` does not apply: pytest's source is in
`src/python/.../pytest/` somewhere, but the *test suite being run* is
in `tests/`, which is kernel-internal. The subprocess is a process
boundary, not an inside/outside boundary.

A different test-runner shape would warrant a bridge: e.g., dispatching
to a CI service that runs the suite remotely. That's an outside bridge.
Block 2.9's pytest-runner is local; bridge: null is correct.

Cost vector rationale:
- clock_ms 30000 — pytest currently runs in ~25s; 30s is a comfortable
  declaration. The calibrator will refine empirically per v1.0 §3.5
  cost-vector update mechanics.
- coin_usd 0 — local compute, no external API.
- carbon_g 0.5 — order-of-magnitude estimate for a 30s Python process
  on a developer laptop. Symbolic; not used for VOI in v1.0.

Capability vector rationale (σ=π=α=ρ=1.0):

Pytest is ground truth in this domain by definition. If pytest exits 0,
tests pass. If pytest exits non-zero, tests fail. There is no source of
truth more authoritative for the question "do the kernel's tests pass."
Hence the capability vector is fully saturated: σ (quality) is perfect
because the resolver gives the literal answer; π (preference) is
perfect because the resolver always prefers correctness; α (autonomy)
is perfect because no human input is required; ρ (reliability) is
perfect modulo subprocess crashes (which would surface as kernel
errors, not as miscalibration).
"""

from __future__ import annotations

import subprocess
import time
from typing import Any


_PYTEST_TIMEOUT_SECONDS = 1800  # 30 minutes — matches policy ground_truth_timeout


def resolve(intention_id: str, repo: str = ".") -> dict[str, Any]:
    """Resolve a test-result intention by actually running pytest.

    Inputs:
        intention_id: the (I, R) id this resolution is for. Recorded
            in the result for traceability; the runner itself doesn't
            consult intention frontmatter.
        repo: working directory for the subprocess (defaults to cwd).

    Returns:
        {
            actual_resolution: bool,    # True if pytest exited 0
            exit_code: int,
            elapsed_ms: float,
            stdout_tail: str,            # last ~2KB of stdout for audit
            intention_id: str,           # echoed back for traceability
        }

    Raises:
        subprocess.TimeoutExpired if pytest exceeds 30 minutes.
    """
    start = time.monotonic()
    proc = subprocess.run(
        ["uv", "run", "pytest", "--tb=no", "-q"],
        capture_output=True,
        timeout=_PYTEST_TIMEOUT_SECONDS,
        cwd=repo,
        check=False,
    )
    elapsed_ms = (time.monotonic() - start) * 1000.0
    stdout_text = proc.stdout.decode("utf-8", errors="replace")
    return {
        "actual_resolution": proc.returncode == 0,
        "exit_code": proc.returncode,
        "elapsed_ms": elapsed_ms,
        "stdout_tail": stdout_text[-2000:],
        "intention_id": intention_id,
    }


def adapt(structured: dict[str, Any]) -> dict[str, Any]:
    """Adapter convention (Block 3 Piece 1): normalize structured runner output.

    Converts the dict returned by `resolve()` into the factory's flat
    `{resolution_text, resolution_value, cost_actual}` shape that
    `kernel.ir.resolve` consumes. coin_usd stays at 0 (local subprocess);
    carbon_g matches the resolver (I, R)'s declared symbolic value.
    """
    verdict = "PASS" if structured["actual_resolution"] else "FAIL"
    tail = structured.get("stdout_tail", "")[-500:]
    return {
        "resolution_text": (
            f"pytest exit code {structured['exit_code']}. {verdict}. "
            f"Elapsed {structured['elapsed_ms']:.0f}ms. Tail: {tail}"
        ),
        "resolution_value": structured["actual_resolution"],
        "cost_actual": {
            "clock_ms": float(structured["elapsed_ms"]),
            "coin_usd": 0.0,
            "carbon_g": 0.5,
        },
    }
