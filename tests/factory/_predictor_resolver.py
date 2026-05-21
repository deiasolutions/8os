"""Synthetic predictor implementation for Shape 1 tests.

Returns a deterministic prediction structured output. Adapter
includes the `probability` field so the factory's
`_author_prediction` helper has a probability to write into the
`_kernel.prediction` (I, R)'s frontmatter_extensions.
"""

from __future__ import annotations

from typing import Any


def predict(intention_id: str) -> dict[str, Any]:
    return {
        "intention_id": intention_id,
        "predicted_resolution": True,
        "probability": 0.85,
        "elapsed_ms": 2.0,
    }


def adapt(structured: dict[str, Any]) -> dict[str, Any]:
    return {
        "resolution_text": (
            f"predicted "
            f"{'PASS' if structured['predicted_resolution'] else 'FAIL'} "
            f"with probability {structured['probability']:.2f}"
        ),
        "resolution_value": structured["predicted_resolution"],
        "probability": structured["probability"],
        "cost_actual": {
            "clock_ms": float(structured.get("elapsed_ms", 0)),
            "coin_usd": 0.0,
            "carbon_g": 0.001,
        },
    }
