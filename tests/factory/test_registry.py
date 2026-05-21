"""Registry tests — resolver lookup, implementation loading, adapter convention."""

from __future__ import annotations

import pytest

from eightos.factory import adapters
from eightos.factory.registry import FactoryError, Registry, ResolverEntry


def test_registry_loads_resolver_record(initialized, author_resolver):
    author_resolver(
        "syn-1",
        bridge=None,
        implementation="tests.factory._fake_resolvers:simple_resolve",
    )
    reg = Registry(initialized)
    entry = reg.get("syn-1")
    assert isinstance(entry, ResolverEntry)
    assert entry.resolver_id == "syn-1"
    assert entry.bridge is None
    assert entry.implementation == "tests.factory._fake_resolvers:simple_resolve"


def test_registry_caches_per_instance(initialized, author_resolver):
    author_resolver("cached", implementation="tests.factory._fake_resolvers:simple_resolve")
    reg = Registry(initialized)
    a = reg.get("cached")
    b = reg.get("cached")
    assert a is b


def test_registry_unknown_resolver_raises(initialized):
    reg = Registry(initialized)
    with pytest.raises(FactoryError, match="not registered"):
        reg.get("does-not-exist")


def test_registry_load_impl_returns_callable(initialized, author_resolver):
    author_resolver("inside-1", implementation="tests.factory._fake_resolvers:simple_resolve")
    impl = Registry(initialized).get("inside-1").load_impl()
    out = impl("any-id")
    assert out["intention_id"] == "any-id"
    assert out["ok"] is True


def test_registry_load_impl_no_implementation_raises(initialized, author_resolver):
    # Bridge-crossing resolvers may omit `implementation:`.
    author_resolver("bridge-only", bridge="fake-bridge", implementation=None)
    with pytest.raises(FactoryError, match="no `implementation:` field"):
        Registry(initialized).get("bridge-only").load_impl()


def test_registry_load_impl_bad_format_raises(initialized, author_resolver):
    author_resolver("malformed", implementation="missing.colon.separator")
    with pytest.raises(FactoryError, match="must be 'module.path:function_name'"):
        Registry(initialized).get("malformed").load_impl()


def test_registry_load_impl_missing_module_raises(initialized, author_resolver):
    author_resolver("ghost-mod", implementation="no.such.module:f")
    with pytest.raises(FactoryError, match="could not import"):
        Registry(initialized).get("ghost-mod").load_impl()


def test_registry_load_impl_missing_function_raises(initialized, author_resolver):
    author_resolver(
        "ghost-fn",
        implementation="tests.factory._fake_resolvers:no_such_function",
    )
    with pytest.raises(FactoryError, match="has no function"):
        Registry(initialized).get("ghost-fn").load_impl()


def test_registry_adapter_convention_uses_module_adapt(initialized, author_resolver):
    author_resolver(
        "with-adapter",
        implementation="tests.factory._fake_resolvers:simple_resolve_with_adapter",
    )
    adapter = Registry(initialized).get("with-adapter").load_adapter()
    out = adapter({"raw_value": 7, "elapsed_ms": 3.0})
    assert "adapted" in out["resolution_text"]
    assert out["resolution_value"] == 7
    assert out["cost_actual"]["clock_ms"] == 3.0


def test_registry_adapter_falls_back_to_default(initialized, author_resolver):
    author_resolver("no-adapt", implementation="tests.factory._no_adapter:resolve")
    adapter = Registry(initialized).get("no-adapt").load_adapter()
    assert adapter is adapters.default_adapter


def test_registry_adapter_for_bridge_only_is_default(initialized, author_resolver):
    author_resolver("bridge-only-2", bridge="fake-bridge", implementation=None)
    adapter = Registry(initialized).get("bridge-only-2").load_adapter()
    assert adapter is adapters.default_adapter
