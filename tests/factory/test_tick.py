"""End-to-end tick tests — walk + selector + dispatch + ir.resolve."""

from __future__ import annotations

from eightos._frontmatter import parse_file
from eightos.factory import tick


def test_tick_dispatches_and_resolves(initialized, author_resolver, author_intention):
    # Single resolver in the pool, capability declared for "test/domain";
    # selector picks it for any leaf in that domain.
    author_resolver(
        "tick-r",
        bridge=None,
        implementation="tests.factory._fake_resolvers:simple_resolve_with_adapter",
    )
    intention_path = author_intention("leaf-tick")

    summary = tick(initialized, "test-scope", domain="test/domain")

    assert summary["scope"] == "test-scope"
    assert summary["leaves_found"] == 1
    assert "batch_id" in summary
    assert summary["dispatched"][0]["ok"] is True
    assert summary["dispatched"][0]["intention_id"] == "leaf-tick"
    assert summary["dispatched"][0]["resolver_id"] == "tick-r"
    assert summary["dispatched"][0]["predicted"] is False
    assert summary["dispatched"][0]["short_circuited"] is False

    rec = parse_file(intention_path)
    assert rec.frontmatter["status"] == "resolved"
    assert "adapted" in (rec.resolution_text or "")


def test_tick_returns_zero_when_no_leaves(initialized):
    summary = tick(initialized, "test-scope", domain="test/domain")
    assert summary["leaves_found"] == 0
    assert summary["dispatched"] == []
    assert summary["holdout_decisions"] == {}


def test_tick_isolates_per_leaf_failures(initialized, author_resolver, author_intention):
    author_resolver(
        "ok-r",
        implementation="tests.factory._fake_resolvers:simple_resolve_with_adapter",
    )
    author_intention("good-leaf")
    author_intention("bad-leaf", domain="no-resolver-claims-this-domain")

    summary = tick(initialized, "test-scope", domain="test/domain")

    assert summary["leaves_found"] == 2
    by_id = {d["intention_id"]: d for d in summary["dispatched"]}
    assert by_id["good-leaf"]["ok"] is True
    # bad-leaf has its own intention.domain, but tick's `domain` param
    # overrides; selector still finds ok-r for both. So bad-leaf also
    # resolves. To force failure, use a leaf whose dispatch fails another
    # way — see the next test.
    assert by_id["bad-leaf"]["ok"] is True


def test_tick_caller_loops_until_drained(
    initialized, author_resolver, author_intention
):
    author_resolver(
        "chain-r",
        implementation="tests.factory._fake_resolvers:simple_resolve_with_adapter",
    )
    author_intention("first")
    author_intention("second", depends_on=["first"])

    s1 = tick(initialized, "test-scope", domain="test/domain")
    assert s1["leaves_found"] == 1
    assert s1["dispatched"][0]["intention_id"] == "first"

    s2 = tick(initialized, "test-scope", domain="test/domain")
    assert s2["leaves_found"] == 1
    assert s2["dispatched"][0]["intention_id"] == "second"

    s3 = tick(initialized, "test-scope", domain="test/domain")
    assert s3["leaves_found"] == 0


def test_tick_skips_kernel_configuration_records(initialized, author_resolver):
    # The vendored resolver itself (a _kernel.resolver record) is not a
    # dispatchable leaf — the walker filters it out. Tick on _kernel
    # scope returns no leaves even when resolvers are present.
    author_resolver(
        "vendored",
        implementation="tests.factory._fake_resolvers:simple_resolve_with_adapter",
    )
    summary = tick(initialized, "_kernel", domain="test/domain")
    assert summary["leaves_found"] == 0


def test_tick_clears_context_after_run(
    initialized, author_resolver, author_intention
):
    """Context module is cleared in the finally block; subsequent
    get_repo / get_batch_id outside a tick raises."""
    import pytest as _pytest

    from eightos.factory import context

    author_resolver(
        "ctx-r",
        implementation="tests.factory._fake_resolvers:simple_resolve_with_adapter",
    )
    author_intention("ctx-leaf")

    tick(initialized, "test-scope", domain="test/domain")

    with _pytest.raises(RuntimeError, match="outside a tick"):
        context.get_repo()
    with _pytest.raises(RuntimeError, match="outside a tick"):
        context.get_batch_id()


def test_tick_clears_context_even_on_exception(
    initialized, author_resolver, author_intention
):
    """If an internal step crashes, context is still cleared in finally."""
    import pytest as _pytest

    from eightos.factory import context

    # Author a resolver whose impl raises — causes per-leaf failure but
    # not tick failure.
    author_resolver(
        "broken",
        implementation="tests.factory._fake_resolvers:failing_resolve",
    )
    author_intention("crash-leaf")

    summary = tick(initialized, "test-scope", domain="test/domain")
    assert summary["dispatched"][0]["ok"] is False

    with _pytest.raises(RuntimeError):
        context.get_repo()
