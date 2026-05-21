"""kernel.test-pass-predictor — heuristic predictor for Block 2.9 dogfood.

A deliberately crude rule-based predictor that takes git-diff metadata as
input and returns a prediction about whether `uv run pytest` will exit 0.
Pure inside resolver, deterministic, near-zero cost. Block 2.9 is the
first prediction-economics dogfood; the loop's compositional correctness
is what's being tested, not the heuristic's quality. The calibrator will
refine the predictor's recorded capability vector empirically as the
corpus grows.

The vendored (I, R) at `ir/_kernel/resolver/kernel.test-pass-predictor.md`
references this module. Block 3's factory will dispatch the predictor
through the kernel; in Block 2.9 the function is invoked by hand during
each dogfood cycle.

Heuristic v0.1 (the rules below should NOT be tuned in Block 2.9):

- Test changes most often pass (the developer just wrote them) — 0.75.
- SDK or index changes often break things — 0.65 fail.
- Tiny changes (<10 lines): mostly pass — 0.90.
- Default: weak prior, mostly pass — 0.65.
"""

from __future__ import annotations

import subprocess
from typing import Any


_SDK_INDEX_PATHS = ("src/eightos/sdk/", "src/eightos/_indexes")
_TEST_PATHS = ("tests/",)


def predict(diff_metadata: dict[str, Any]) -> dict[str, Any]:
    """Predict test-suite outcome from git-diff metadata.

    Inputs:
        diff_metadata: {files_changed: [<path>, ...], lines_changed: <int>}

    Returns:
        {predicted_resolution: bool, probability: float}

    Pure function. Same input → same output across runs.
    """
    files_changed = diff_metadata.get("files_changed") or []
    lines_changed = int(diff_metadata.get("lines_changed") or 0)

    touches_tests = any(
        f.startswith(p) for f in files_changed for p in _TEST_PATHS
    )
    touches_sdk_index = any(
        f.startswith(p) for f in files_changed for p in _SDK_INDEX_PATHS
    )

    if touches_tests:
        return {"predicted_resolution": True, "probability": 0.75}
    if touches_sdk_index:
        return {"predicted_resolution": False, "probability": 0.65}
    if lines_changed < 10:
        return {"predicted_resolution": True, "probability": 0.90}
    return {"predicted_resolution": True, "probability": 0.65}


def adapt(structured: dict[str, Any]) -> dict[str, Any]:
    """Adapter convention (Block 3 Piece 1): normalize structured prediction.

    Converts the dict returned by `predict()` into the factory's flat
    `{resolution_text, resolution_value, cost_actual}` shape. Predictions
    don't write resolutions per se — Piece 2's predictor-dispatch path
    will route adapter output into a `_kernel.prediction` (I, R) instead
    — but the convention is uniform across all resolvers so the dispatcher
    treats predictors and ground-truth resolvers the same way at the
    adapter boundary.
    """
    verdict = "PASS" if structured["predicted_resolution"] else "FAIL"
    return {
        "resolution_text": (
            f"predicted {verdict} with probability {structured['probability']:.2f}"
        ),
        "resolution_value": structured["predicted_resolution"],
        "probability": structured["probability"],
        "cost_actual": {
            "clock_ms": 5.0,
            "coin_usd": 0.0,
            "carbon_g": 0.001,
        },
    }


def predict_from_intention(intention_id: str) -> dict[str, Any]:
    """Factory dispatch entry point. The (I, R)'s `implementation:` field
    points here.

    Per the factory's `impl(intention_id)` contract (Block 3 Piece 1),
    this function takes only the intention id. The current repo is
    discovered via `eightos.factory.context.get_repo()`, set by the
    factory's tick at batch start. The intention id is recorded in the
    output's collapsed_summary downstream but the predictor itself
    only consults the working-tree diff.
    """
    from eightos.factory import context

    repo = str(context.get_repo())
    diff = diff_metadata_from_git(repo)
    out = predict(diff)
    out["intention_id"] = intention_id
    out["files_changed"] = len(diff["files_changed"])
    out["lines_changed"] = diff["lines_changed"]
    return out


def diff_metadata_from_git(repo: str = ".") -> dict[str, Any]:
    """Compute working-tree diff metadata for the current state vs HEAD.

    Reads:
      - `git diff HEAD --name-only` for the changed-file set (staged +
        unstaged, since both are part of "what would be committed").
      - `git diff HEAD --shortstat` for the lines-changed total.

    Returns:
        {files_changed: [<path>, ...], lines_changed: <int>}

    Untracked files are not included by `git diff HEAD`. For Block 2.9's
    dogfood that is fine: the predictor reasons over what would be
    committed, and untracked files require explicit `git add` first.
    """
    name_only = subprocess.run(
        ["git", "diff", "HEAD", "--name-only"],
        capture_output=True,
        text=True,
        cwd=repo,
        check=False,
    )
    files_changed = [
        line.strip() for line in name_only.stdout.splitlines() if line.strip()
    ]

    shortstat = subprocess.run(
        ["git", "diff", "HEAD", "--shortstat"],
        capture_output=True,
        text=True,
        cwd=repo,
        check=False,
    )
    lines_changed = 0
    for fragment in shortstat.stdout.split(","):
        fragment = fragment.strip()
        if "insertion" in fragment or "deletion" in fragment:
            try:
                lines_changed += int(fragment.split()[0])
            except (ValueError, IndexError):
                pass

    return {"files_changed": files_changed, "lines_changed": lines_changed}
