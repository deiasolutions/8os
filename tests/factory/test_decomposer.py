"""Decomposer module tests — prompt construction, response parsing, adapter.

Block 3 Piece 4. The decomposer is a bridge-crossing resolver; its
work happens via the Anthropic Messages API. These tests cover the
parts of the module that don't require crossing the bridge:

- `load_prompt` returns the vendored prompt verbatim.
- `build_payload` assembles a Messages API request with the prompt
  as system message and the PRISM-IR body as user message.
- `parse_response` handles pure JSON, JSON inside markdown fences,
  and JSON embedded in prose. Validation rejects missing keys,
  duplicate node_ids, and dangling depends_on.
- `adapt` extracts the graph spec from a canned bridge response.
- `decompose` end-to-end against a mocked SDK runner — exercises
  the call path without hitting the real API.

The real-API end-to-end test lives in `test_decomposer_e2e.py` and is
gated on `RUN_REAL_BRIDGE_TESTS=1`.
"""

from __future__ import annotations

import json

import pytest

from eightos.factory import decomposer
from eightos.factory.decomposer import (
    BRIDGE_ID,
    DEFAULT_MODEL,
    RESOLVER_ID,
    STANDING_AUTHORIZATION_ID,
    DecomposerError,
    adapt,
    build_payload,
    decompose,
    load_prompt,
    parse_response,
)


# ---- prompt loading --------------------------------------------------------


def test_load_prompt_returns_nonempty_string():
    text = load_prompt()
    assert isinstance(text, str)
    assert len(text) > 0
    # Sanity: the prompt mentions PRISM-IR, since that's its job.
    assert "PRISM-IR" in text


def test_load_prompt_specifies_json_output():
    text = load_prompt()
    # Critical instruction — if this is missing, the LLM may emit prose.
    assert "JSON" in text
    assert "node_id" in text
    assert "intention_text" in text
    assert "depends_on" in text
    assert "prism_operator" in text


# ---- payload construction --------------------------------------------------


def test_build_payload_assembles_messages_request():
    body = "v: 1.1\nid: x\nintention: test\nnodes: []\nedges: []"
    payload = build_payload(body)
    assert payload["model"] == DEFAULT_MODEL
    assert payload["system"] == load_prompt()
    assert payload["messages"] == [{"role": "user", "content": body}]
    assert payload["max_tokens"] > 0


def test_build_payload_overrides_model():
    payload = build_payload("body", model="claude-haiku-4-5")
    assert payload["model"] == "claude-haiku-4-5"


def test_build_payload_overrides_max_tokens():
    payload = build_payload("body", max_tokens=2048)
    assert payload["max_tokens"] == 2048


# ---- parse_response: happy paths -------------------------------------------


def _minimal_spec_json() -> str:
    return json.dumps(
        {
            "nodes": [
                {
                    "node_id": "fetch",
                    "intention_text": "Fetch data.",
                    "depends_on": [],
                    "prism_operator": {
                        "op": "script",
                        "resolver": "fetch-data",
                        "model": None,
                    },
                },
                {
                    "node_id": "summarize",
                    "intention_text": "Summarize the fetched data.",
                    "depends_on": ["fetch"],
                    "prism_operator": {
                        "op": "llm",
                        "resolver": "summarizer",
                        "model": None,
                    },
                },
            ]
        }
    )


def test_parse_response_pure_json():
    spec = parse_response(_minimal_spec_json())
    assert len(spec["nodes"]) == 2
    assert spec["nodes"][0]["node_id"] == "fetch"
    assert spec["nodes"][1]["depends_on"] == ["fetch"]


def test_parse_response_with_json_fence():
    raw = f"```json\n{_minimal_spec_json()}\n```"
    spec = parse_response(raw)
    assert len(spec["nodes"]) == 2


def test_parse_response_with_unlabeled_fence():
    raw = f"```\n{_minimal_spec_json()}\n```"
    spec = parse_response(raw)
    assert len(spec["nodes"]) == 2


def test_parse_response_with_prose_prefix():
    raw = (
        "Here is the decomposition:\n\n"
        f"{_minimal_spec_json()}\n\n"
        "Hope that helps."
    )
    spec = parse_response(raw)
    assert len(spec["nodes"]) == 2


def test_parse_response_handles_null_prism_operator():
    raw = json.dumps(
        {
            "nodes": [
                {
                    "node_id": "x",
                    "intention_text": "Do x.",
                    "depends_on": [],
                    "prism_operator": None,
                }
            ]
        }
    )
    spec = parse_response(raw)
    assert spec["nodes"][0]["prism_operator"] is None


def test_parse_response_trims_whitespace_in_intention_text():
    raw = json.dumps(
        {
            "nodes": [
                {
                    "node_id": "x",
                    "intention_text": "  Do x.  \n",
                    "depends_on": [],
                    "prism_operator": None,
                }
            ]
        }
    )
    spec = parse_response(raw)
    assert spec["nodes"][0]["intention_text"] == "Do x."


# ---- parse_response: error paths -------------------------------------------


def test_parse_response_no_json_raises():
    with pytest.raises(DecomposerError, match="no JSON object found"):
        parse_response("just prose, no json here")


def test_parse_response_invalid_json_raises():
    # Looks like JSON but isn't parseable.
    with pytest.raises(DecomposerError):
        parse_response("{not: valid, json: at all}")


def test_parse_response_missing_nodes_key_raises():
    with pytest.raises(DecomposerError, match="missing 'nodes'"):
        parse_response('{"foo": "bar"}')


def test_parse_response_nodes_not_list_raises():
    with pytest.raises(DecomposerError):
        parse_response('{"nodes": "not a list"}')


def test_parse_response_duplicate_node_id_raises():
    raw = json.dumps(
        {
            "nodes": [
                {
                    "node_id": "x",
                    "intention_text": "First.",
                    "depends_on": [],
                    "prism_operator": None,
                },
                {
                    "node_id": "x",
                    "intention_text": "Second.",
                    "depends_on": [],
                    "prism_operator": None,
                },
            ]
        }
    )
    with pytest.raises(DecomposerError, match="duplicates"):
        parse_response(raw)


def test_parse_response_dangling_depends_on_raises():
    raw = json.dumps(
        {
            "nodes": [
                {
                    "node_id": "x",
                    "intention_text": "Do x.",
                    "depends_on": ["nonexistent"],
                    "prism_operator": None,
                }
            ]
        }
    )
    with pytest.raises(DecomposerError, match="not a node in this spec"):
        parse_response(raw)


def test_parse_response_empty_intention_text_raises():
    raw = json.dumps(
        {
            "nodes": [
                {
                    "node_id": "x",
                    "intention_text": "   ",
                    "depends_on": [],
                    "prism_operator": None,
                }
            ]
        }
    )
    with pytest.raises(DecomposerError, match="intention_text"):
        parse_response(raw)


def test_parse_response_missing_node_id_raises():
    raw = json.dumps(
        {
            "nodes": [
                {
                    "intention_text": "Do x.",
                    "depends_on": [],
                    "prism_operator": None,
                }
            ]
        }
    )
    with pytest.raises(DecomposerError, match="node_id missing"):
        parse_response(raw)


def test_parse_response_invalid_prism_operator_raises():
    raw = json.dumps(
        {
            "nodes": [
                {
                    "node_id": "x",
                    "intention_text": "Do x.",
                    "depends_on": [],
                    "prism_operator": "should be an object",
                }
            ]
        }
    )
    with pytest.raises(DecomposerError, match="prism_operator"):
        parse_response(raw)


# ---- adapt -----------------------------------------------------------------


def test_adapt_extracts_graph_spec():
    bridge_result = {
        "resolution": _minimal_spec_json(),
        "cost_actual": {
            "clock_ms": 1234.5,
            "coin_usd": 0.013,
            "carbon_g": 2.0,
            "model_name": "claude-sonnet-4-6",
            "tokens_in": 1500,
            "tokens_out": 400,
        },
        "audit": {"source": "real"},
    }
    out = adapt(bridge_result)
    assert "resolution_text" in out
    assert out["resolution_value"]["nodes"][0]["node_id"] == "fetch"
    assert out["cost_actual"]["coin_usd"] == 0.013


def test_adapt_with_missing_resolution_raises():
    with pytest.raises(DecomposerError, match="no 'resolution'"):
        adapt({"cost_actual": {}})


def test_adapt_with_dict_resolution_serializes_first():
    # Some bridge shapes may pass resolution as already-parsed JSON.
    bridge_result = {
        "resolution": json.loads(_minimal_spec_json()),
        "cost_actual": {},
    }
    out = adapt(bridge_result)
    assert out["resolution_value"]["nodes"][0]["node_id"] == "fetch"


def test_adapt_zero_costs_default_when_missing():
    bridge_result = {"resolution": _minimal_spec_json()}
    out = adapt(bridge_result)
    assert out["cost_actual"] == {
        "clock_ms": 0.0,
        "coin_usd": 0.0,
        "carbon_g": 0.0,
    }


def test_adapt_non_dict_input_raises():
    with pytest.raises(DecomposerError, match="must be a dict"):
        adapt("not a dict")


# ---- decompose end-to-end against a mocked runner --------------------------


def test_decompose_against_mocked_runner(monkeypatch):
    """Verify decompose() correctly assembles the cross payload and parses
    the response — without hitting the real Anthropic API."""
    captured: dict[str, dict] = {}

    def fake_run_op(op: str, payload: dict) -> dict:
        captured["op"] = op  # type: ignore[assignment]
        captured["payload"] = payload
        # Return a canonical bridge.cross success envelope.
        return {
            "data": {
                "response": {
                    "resolution": _minimal_spec_json(),
                    "cost_actual": {
                        "clock_ms": 1500.0,
                        "coin_usd": 0.02,
                        "carbon_g": 1.5,
                        "model_name": DEFAULT_MODEL,
                        "tokens_in": 1000,
                        "tokens_out": 300,
                    },
                    "audit": {"source": "mock"},
                },
                "cost_actual": {},
                "raw_payload_ref": None,
            },
            "event_id": "evt_mock",
            "indexes_updated": [],
        }

    monkeypatch.setattr(
        "eightos.sdk._runner.run", fake_run_op
    )
    # Re-import to pick up the patch on the module-level reference.
    monkeypatch.setattr(
        decomposer, "decompose", decomposer.decompose
    )

    body = "v: 1.1\nid: scan\nintention: test\nnodes: []\nedges: []"
    out = decompose(body, for_ir_id="some-intention")

    assert captured["op"] == "kernel.bridge.cross"
    payload = captured["payload"]
    assert payload["bridge_id"] == BRIDGE_ID
    assert payload["resolver_id"] == RESOLVER_ID
    assert payload["for_ir_id"] == "some-intention"
    assert payload["authorization_id"] == STANDING_AUTHORIZATION_ID
    inner = payload["payload"]
    assert inner["model"] == DEFAULT_MODEL
    assert inner["system"] == load_prompt()
    assert inner["messages"][0]["content"] == body

    assert out["resolution_value"]["nodes"][0]["node_id"] == "fetch"
    assert out["cost_actual"]["coin_usd"] == 0.02
