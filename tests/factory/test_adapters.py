"""Adapter tests — default_adapter behavior."""

from __future__ import annotations

from eightos.factory.adapters import default_adapter


def test_default_adapter_stringifies_input():
    out = default_adapter({"a": 1, "b": "two"})
    # Stringification preserves the structured content for audit even
    # though no per-resolver normalization happened.
    assert "a" in out["resolution_text"]
    assert "two" in out["resolution_text"]


def test_default_adapter_emits_zero_cost_placeholder():
    out = default_adapter({"x": 1})
    assert out["cost_actual"] == {
        "clock_ms": 0.0,
        "coin_usd": 0.0,
        "carbon_g": 0.0,
    }


def test_default_adapter_resolution_value_is_none():
    out = default_adapter({"x": 1})
    assert out["resolution_value"] is None


def test_default_adapter_handles_non_dict_input():
    # Must not crash on lists/strings/numbers.
    out = default_adapter([1, 2, 3])
    assert out["resolution_text"] == "[1, 2, 3]"


def test_default_adapter_required_keys_present():
    out = default_adapter("anything")
    for key in ("resolution_text", "resolution_value", "cost_actual"):
        assert key in out
