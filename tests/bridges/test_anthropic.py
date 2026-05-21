"""Anthropic bridge module tests.

Block 3 Piece 3. The bridge function's stub path is exercised directly
(no credential needed); the real-API path is gated on
`RUN_REAL_BRIDGE_TESTS=1` AND a usable OAuth credential being present
on the machine — both must be true for the integration test to fire.
The integration test is opt-in to avoid spurious API spend during
normal `uv run pytest` runs.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from eightos.bridges import anthropic


def test_stub_response_shape():
    """The stub returns the documented {resolution, cost_actual, audit} shape."""
    out = anthropic._stub_response(
        "anthropic",
        {"messages": [{"role": "user", "content": "hello"}], "model": "claude-haiku-4-5"},
    )
    assert "resolution" in out
    assert "cost_actual" in out
    assert "audit" in out
    assert anthropic._STUB_RESOLUTION_PREFIX in out["resolution"]
    assert out["audit"]["source"] == "stub"
    for key in ("clock_ms", "coin_usd", "carbon_g", "model_name", "tokens_in", "tokens_out"):
        assert key in out["cost_actual"]


def test_stub_echoes_last_user_message():
    """Stub echoes the last user-role message so end-to-end wiring is sanity-checkable."""
    out = anthropic._stub_response(
        "anthropic",
        {
            "messages": [
                {"role": "system", "content": "ignore"},
                {"role": "user", "content": "first message"},
                {"role": "assistant", "content": "ignored"},
                {"role": "user", "content": "expected echo content"},
            ],
            "model": "claude-haiku-4-5",
        },
    )
    assert "expected echo content" in out["resolution"]


def test_coerce_factory_minimal_payload():
    """A factory-style {intention_id, intention_text} payload coerces into a Messages API request."""
    req = anthropic._coerce_to_messages_request(
        {"intention_id": "leaf-1", "intention_text": "Decompose this PRISM-IR doc."}
    )
    assert req["model"] == anthropic._ANTHROPIC_DEFAULT_MODEL
    assert req["messages"] == [
        {"role": "user", "content": "Decompose this PRISM-IR doc."}
    ]
    assert req["max_tokens"] == 4096
    assert "system" not in req


def test_coerce_passes_through_messages_api_request():
    """A fully-formed Messages API request passes through with defaults filled in."""
    req = anthropic._coerce_to_messages_request(
        {
            "messages": [{"role": "user", "content": "hi"}],
            "model": "claude-sonnet-4-6",
            "max_tokens": 1024,
            "system": "You are a helpful assistant.",
        }
    )
    assert req["model"] == "claude-sonnet-4-6"
    assert req["max_tokens"] == 1024
    assert req["system"] == "You are a helpful assistant."


def test_compute_cost_known_model():
    """Known models compute non-zero cost from token counts."""
    cost = anthropic._compute_cost("claude-haiku-4-5", 1_000_000, 0)
    # Haiku input price: $0.80 per million tokens.
    assert cost == pytest.approx(0.80)


def test_compute_cost_unknown_model_returns_zero():
    """Unknown models default to zero cost (no pricing data)."""
    assert anthropic._compute_cost("unknown-model", 1000, 1000) == 0.0


def test_estimate_carbon_scales_with_tokens():
    a = anthropic._estimate_carbon(1000, 0)
    b = anthropic._estimate_carbon(0, 1000)
    c = anthropic._estimate_carbon(500, 500)
    assert a == b == c


def test_cross_uses_stub_when_no_credential(monkeypatch):
    """When credential discovery returns None, cross() returns a stub response."""
    monkeypatch.setattr(anthropic, "_load_oauth_credentials", lambda: None)
    out = anthropic.cross(
        "anthropic",
        {"intention_text": "test"},
        None,
        Path("/nonexistent"),
    )
    assert anthropic._STUB_RESOLUTION_PREFIX in out["resolution"]
    assert out["audit"]["source"] == "stub"


def test_oauth_credentials_available_returns_bool(tmp_path, monkeypatch):
    """The gating helper returns False under known-clean conditions."""
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    # Also stub keychain lookup to None for determinism.
    monkeypatch.setattr(anthropic, "_try_keychain_lookup", lambda: None)
    assert anthropic._oauth_credentials_available() is False


def test_env_token_takes_precedence(monkeypatch, tmp_path):
    """CLAUDE_CODE_OAUTH_TOKEN env var wins over file/keychain."""
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "test-token-from-env")
    creds = anthropic._load_oauth_credentials()
    assert creds is not None
    assert creds["access_token"] == "test-token-from-env"
    assert creds["source"] == "env"


# Integration test — gated on opt-in env var AND credential availability.
# Costs ~fractions-of-a-cent per run; do not enable in CI by default.
@pytest.mark.skipif(
    os.environ.get("RUN_REAL_BRIDGE_TESTS") != "1"
    or not anthropic._oauth_credentials_available(),
    reason="integration test (real Anthropic API) gated on RUN_REAL_BRIDGE_TESTS=1 + valid OAuth credential",
)
def test_real_api_call_returns_messages_response(tmp_path):
    """Hits the real Anthropic Messages API end-to-end. Opt-in via env var."""
    out = anthropic.cross(
        "anthropic",
        {
            "messages": [{"role": "user", "content": "Reply with exactly one word: hello"}],
            "model": "claude-haiku-4-5",
            "max_tokens": 16,
        },
        None,
        tmp_path,
    )
    # Real API response — non-stub.
    assert anthropic._STUB_RESOLUTION_PREFIX not in out["resolution"]
    assert "hello" in out["resolution"].lower()
    # Cost actually captured.
    assert out["cost_actual"]["tokens_in"] is not None
    assert out["cost_actual"]["tokens_out"] is not None
    assert out["cost_actual"]["coin_usd"] > 0
    assert out["audit"]["source"] in ("env", "file", "keychain-json", "keychain-raw")
