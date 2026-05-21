"""Synthetic graph-producing resolver for tick tests.

Returns a canned graph spec; the materializer turns it into two
child (I, R)s under the leaf being dispatched.
"""

from __future__ import annotations

from typing import Any


def produce_graph(intention_id: str) -> dict[str, Any]:
    """Return a structured output that adapt() can convert to a graph spec."""
    return {
        "intention_id": intention_id,
        "graph_spec": {
            "nodes": [
                {
                    "node_id": "child-a",
                    "intention_text": "Child A.",
                    "depends_on": [],
                    "prism_operator": None,
                },
                {
                    "node_id": "child-b",
                    "intention_text": "Child B.",
                    "depends_on": ["child-a"],
                    "prism_operator": None,
                },
            ]
        },
    }


def adapt(structured: dict[str, Any]) -> dict[str, Any]:
    """Adapter — surface the graph spec on resolution_value."""
    return {
        "resolution_text": "Decomposed into 2 children.",
        "resolution_value": structured["graph_spec"],
        "cost_actual": {
            "clock_ms": 0.0,
            "coin_usd": 0.0,
            "carbon_g": 0.0,
        },
    }
