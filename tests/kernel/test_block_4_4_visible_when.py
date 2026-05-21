"""Tests for Block 4.4 — `visible_when` predicate engine.

Per 8OS-BLOCK-1-SPEC v1.1 §4.4, `visible_when` becomes optional base
frontmatter (hard-authority records only). The kernel evaluates predicates
at every read op (get / list / deps) — invisible records reject from get,
silently filter from list, terminate the closure walk in deps.

Block 4.4 implements the engine and the schema-addition. Three placeholders
are documented but not closed in this binary:

1. Roles placeholder — `_kernel.role` not implemented; runtime caller_roles
   defaults to empty list.
2. Classification ordering placeholder — `data_classification_at_most` does
   string-equality only.
3. Runtime CallerContext placeholder (per discipline (B)) — read ops build
   default-empty CallerContext at runtime; predicates that reference roles
   / scope / caller identity therefore evaluate false at runtime in this
   binary. Test fixtures bypass the SDK runner for composition tests
   (15-18) by calling `evaluate_predicate(...)` directly.

The 25 tests enumerated in the Block 4.4 prompt:

Schema-addition (mirrors 4.1/4.3 template):
1. Authoring with visible_when (hard authority).
2. Authoring without visible_when.
3. visible_when: null (explicit no-predicate).
4. Convention-authored record with visible_when rejects.
5. Backward compat with v1.1.0-dev.3 records.

Predicate validation:
6. Empty predicate object {} rejects.
7. Empty `any: []` rejects.
8. Unknown leaf name rejects.
9. Multi-key leaf rejects.
10. Invalid authority_level value rejects.

Predicate evaluation — read-op integration (per (B), use predicates that
resolve correctly against empty default CallerContext):
11. kernel.ir.get returns IR_NOT_VISIBLE when predicate evaluates false.
12. kernel.ir.get returns the record when predicate evaluates true.
13. kernel.ir.list filters predicate-false records silently.
14. kernel.ir.deps stops at invisible records.

Predicate composition (direct evaluator unit tests; bypass SDK):
15. any composition.
16. all composition.
17. not composition (none-of-array semantics).
18. Nested composition.

Cross-op preservation:
19. visible_when preserved through kernel.ir.resolve.
20. visible_when preserved through kernel.ir.cancel.

Reindex --check:
21. Accepts records lacking visible_when.
22. Accepts records with visible_when: null.
23. Rejects malformed predicates on disk.
24. Rejects convention-authority records carrying visible_when (defense-in-depth).

Upgrade:
25. Upgrade dev.3 → current is clean (no body refreshes); KERNEL_VERSION import.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eightos import __version__ as KERNEL_VERSION
from eightos._frontmatter import parse_file, serialize
from eightos.errors import (
    IR_NOT_VISIBLE,
    SCHEMA_INVALID,
    VISIBILITY_PREDICATE_NOT_PERMITTED,
    KernelError,
)
from eightos.predicates import CallerContext, evaluate_predicate, parse_predicate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _author_hard(run_op, slug: str, *, scope: str = "_kernel",
                 visible_when: dict | None = None,
                 projection_types: list[str] | None = None,
                 frontmatter_extensions: dict | None = None,
                 depends_on: list[str] | None = None) -> str:
    """Author a hard-authority record (the only kind that may carry
    visible_when). Defaults to the _kernel scope which the existing
    init+test setup permits hard writes into.

    For records carrying `_kernel.scope` projection_types, supply
    appropriate frontmatter_extensions; for other kernel projection
    types, the caller supplies them via `frontmatter_extensions`.
    """
    payload = {
        "scope_id": scope,
        "slug": slug,
        "tier": 1,
        "intention_text": f"Hard-authority intention {slug!r}.",
        "authority_level": "hard",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
    }
    if projection_types:
        payload["projection_types"] = projection_types
    if frontmatter_extensions:
        payload["frontmatter_extensions"] = frontmatter_extensions
    if visible_when is not None:
        payload["visible_when"] = visible_when
    if depends_on:
        payload["depends_on"] = depends_on
    run_op("kernel.ir.new", payload)
    return slug


def _author_convention(run_op, slug: str, *,
                       visible_when: dict | None = None,
                       depends_on: list[str] | None = None) -> str:
    payload = {
        "scope_id": "test-scope",
        "slug": slug,
        "tier": 1,
        "intention_text": f"Convention intention {slug!r}.",
        "authority_level": "convention",
        "authored_by": "test-author",
    }
    if visible_when is not None:
        payload["visible_when"] = visible_when
    if depends_on:
        payload["depends_on"] = depends_on
    run_op("kernel.ir.new", payload)
    return slug


# ---------------------------------------------------------------------------
# Tests 1-5 — schema-addition
# ---------------------------------------------------------------------------


def test_authoring_with_visible_when_hard_authority(initialized: Path, run_op):
    repo = initialized
    _author_hard(run_op, "with-pred", visible_when={"any": [{"role": "editor"}]})
    rec = parse_file(repo / "ir" / "_kernel" / "with-pred.md")
    assert rec.frontmatter["visible_when"] == {"any": [{"role": "editor"}]}


def test_authoring_without_visible_when(initialized: Path, run_op):
    repo = initialized
    _author_convention(run_op, "no-pred")
    rec = parse_file(repo / "ir" / "test-scope" / "no-pred.md")
    assert "visible_when" not in rec.frontmatter


def test_visible_when_null_is_accepted(initialized: Path, run_op):
    repo = initialized
    run_op("kernel.ir.new", {
        "scope_id": "test-scope",
        "slug": "explicit-null",
        "tier": 1,
        "intention_text": "Explicit null predicate.",
        "authority_level": "convention",
        "authored_by": "test-author",
        "visible_when": None,
    })
    rec = parse_file(repo / "ir" / "test-scope" / "explicit-null.md")
    # null is "no predicate" — equivalent to absent; not written to fm.
    assert "visible_when" not in rec.frontmatter


def test_convention_authored_with_visible_when_rejects(initialized: Path, run_op):
    with pytest.raises(KernelError) as exc:
        _author_convention(run_op, "blocked", visible_when={"any": [{"role": "editor"}]})
    assert exc.value.code == VISIBILITY_PREDICATE_NOT_PERMITTED


def test_backward_compat_with_pre_block_4_4_record(initialized: Path, run_op):
    """Records authored under v1.1.0-dev.3 (no visible_when field) load and
    list normally."""
    repo = initialized
    _author_convention(run_op, "legacy")
    rec = parse_file(repo / "ir" / "test-scope" / "legacy.md")
    assert "visible_when" not in rec.frontmatter
    env = run_op("kernel.ir.list", {"scope_id": "test-scope", "status": ["open"]})
    ids = {r["ir_id"] for r in env["data"]["results"]}
    assert "legacy" in ids


# ---------------------------------------------------------------------------
# Tests 6-10 — predicate validation (write-time)
# ---------------------------------------------------------------------------


def test_empty_predicate_object_rejects(initialized: Path, run_op):
    with pytest.raises(KernelError) as exc:
        _author_hard(run_op, "empty-obj", visible_when={})
    assert exc.value.code == SCHEMA_INVALID


def test_empty_any_array_rejects(initialized: Path, run_op):
    with pytest.raises(KernelError) as exc:
        _author_hard(run_op, "empty-any", visible_when={"any": []})
    assert exc.value.code == SCHEMA_INVALID


def test_unknown_leaf_name_rejects(initialized: Path, run_op):
    with pytest.raises(KernelError) as exc:
        _author_hard(run_op, "unknown-leaf",
                     visible_when={"any": [{"unknown_leaf": "value"}]})
    assert exc.value.code == SCHEMA_INVALID


def test_multi_key_leaf_rejects(initialized: Path, run_op):
    with pytest.raises(KernelError) as exc:
        _author_hard(run_op, "multi-key",
                     visible_when={"any": [{"role": "x", "scope": "y"}]})
    assert exc.value.code == SCHEMA_INVALID


def test_invalid_authority_level_value_rejects(initialized: Path, run_op):
    with pytest.raises(KernelError) as exc:
        _author_hard(run_op, "bad-auth",
                     visible_when={"any": [{"authority_level": "supreme"}]})
    assert exc.value.code == SCHEMA_INVALID


# ---------------------------------------------------------------------------
# Tests 11-14 — read-op integration with default empty CallerContext
# Per (B): predicates referencing identity / role / scope evaluate false
# against the default empty context at runtime. Use simple "block everyone"
# patterns for false; use `not: [...]` for true (since the runtime caller
# is no-one and `not has-role-X` is true).
# ---------------------------------------------------------------------------


def test_get_returns_ir_not_visible_when_predicate_false(initialized: Path, run_op):
    _author_hard(run_op, "block-everyone",
                 visible_when={"any": [{"caller": "alice"}]})
    with pytest.raises(KernelError) as exc:
        run_op("kernel.ir.get", {"ir_id": "block-everyone"})
    assert exc.value.code == IR_NOT_VISIBLE


def test_get_returns_record_when_predicate_true(initialized: Path, run_op):
    """Predicate `not: [{caller: alice}]` evaluates true against the empty
    runtime caller (caller_id is None, not 'alice')."""
    _author_hard(run_op, "open-to-everyone",
                 visible_when={"not": [{"caller": "alice"}]})
    env = run_op("kernel.ir.get", {"ir_id": "open-to-everyone"})
    assert env["data"]["ir_id"] == "open-to-everyone"


def test_list_filters_predicate_false_records_silently(initialized: Path, run_op):
    _author_hard(run_op, "visible-by-not",
                 visible_when={"not": [{"caller": "alice"}]})
    _author_hard(run_op, "blocked-by-caller",
                 visible_when={"any": [{"caller": "alice"}]})
    env = run_op("kernel.ir.list", {"scope_id": "_kernel", "include_kernel": True})
    ids = {r["ir_id"] for r in env["data"]["results"]}
    assert "visible-by-not" in ids
    assert "blocked-by-caller" not in ids
    # The total count reflects visible records only.
    assert env["data"]["total_matching"] == env["data"]["returned"]


def test_deps_stops_at_invisible_records(initialized: Path, run_op):
    """Author root, level-1 (invisible to runtime caller), level-2.
    deps walk from root in reverse direction should reach level-1 only if
    visible; level-2 (its dependent) must not be surfaced when level-1
    terminates the walk."""
    _author_hard(run_op, "deps-root", visible_when={"not": [{"caller": "alice"}]})
    _author_hard(run_op, "deps-level1",
                 visible_when={"any": [{"caller": "alice"}]},
                 depends_on=["deps-root"])
    _author_hard(run_op, "deps-level2",
                 visible_when={"not": [{"caller": "alice"}]},
                 depends_on=["deps-level1"])

    env = run_op("kernel.ir.deps", {
        "ir_id": "deps-root",
        "direction": "reverse",
        "max_depth": 5,
    })
    ids_in_graph = {n["ir_id"] for n in env["data"]["graph"]}
    # Root itself is visible and in the graph.
    assert "deps-root" in ids_in_graph
    # level1 is invisible — terminates that branch.
    assert "deps-level1" not in ids_in_graph
    # level2 is past the invisible terminator and must not be surfaced
    # even though level2 itself would be visible to the runtime caller.
    assert "deps-level2" not in ids_in_graph


# ---------------------------------------------------------------------------
# Tests 15-18 — predicate composition (direct evaluator unit tests)
# ---------------------------------------------------------------------------


def test_any_composition():
    p = parse_predicate({"any": [{"role": "A"}, {"role": "B"}]})
    assert evaluate_predicate(p, CallerContext(caller_roles=("A",))) is True
    assert evaluate_predicate(p, CallerContext(caller_roles=("B",))) is True
    assert evaluate_predicate(p, CallerContext(caller_roles=("C",))) is False
    assert evaluate_predicate(p, CallerContext()) is False


def test_all_composition():
    p = parse_predicate({"all": [{"role": "A"}, {"scope": "S"}]})
    assert evaluate_predicate(
        p, CallerContext(caller_roles=("A",), caller_scope="S")
    ) is True
    assert evaluate_predicate(
        p, CallerContext(caller_roles=("A",), caller_scope="T")
    ) is False
    assert evaluate_predicate(p, CallerContext(caller_scope="S")) is False


def test_not_composition_none_of_array_semantics():
    """`not: [a, b]` means `not (a or b)` — i.e., none-of-array.
    `not (a or b) == (not a) and (not b)`."""
    p = parse_predicate({"not": [{"role": "A"}, {"role": "B"}]})
    # Has neither A nor B → both inner false → none-of true → predicate true.
    assert evaluate_predicate(p, CallerContext(caller_roles=("C",))) is True
    # Has A → some-of-array true → none-of false → predicate false.
    assert evaluate_predicate(p, CallerContext(caller_roles=("A",))) is False
    assert evaluate_predicate(p, CallerContext(caller_roles=("A", "C"))) is False


def test_nested_composition():
    p = parse_predicate({
        "any": [
            {"all": [{"role": "A"}, {"scope": "S"}]},
            {"role": "B"},
        ]
    })
    # Either (A and scope=S) OR role B.
    assert evaluate_predicate(
        p, CallerContext(caller_roles=("A",), caller_scope="S")
    ) is True
    assert evaluate_predicate(p, CallerContext(caller_roles=("B",))) is True
    assert evaluate_predicate(
        p, CallerContext(caller_roles=("A",), caller_scope="T")
    ) is False
    assert evaluate_predicate(p, CallerContext(caller_roles=("C",))) is False


# ---------------------------------------------------------------------------
# Tests 19-20 — cross-op preservation
# ---------------------------------------------------------------------------


def test_visible_when_preserved_through_resolve(initialized: Path, run_op):
    repo = initialized
    # Register a resolver in _kernel scope.
    run_op("kernel.ir.new", {
        "scope_id": "_kernel",
        "slug": "test-resolver-vw",
        "tier": 1,
        "intention_text": "Test resolver.",
        "projection_types": ["_kernel.resolver"],
        "authority_level": "hard",
        "authored_by": "test-author",
        "authored_via": "kernel.self",
        "frontmatter_extensions": {
            "resolver_id": "test-resolver-vw",
            "display_name": "test-resolver-vw",
            "bridge": None,
            "cost": {"clock_ms": 1, "coin_usd": 0, "carbon_g": 0},
            "capability": {
                "general": {
                    "sigma": {"declared": 0.9, "measured": None},
                    "pi": {"declared": 0.9, "measured": None},
                    "alpha": {"declared": 0.9, "measured": None},
                    "rho": {"declared": 0.9, "measured": None},
                }
            },
        },
    })
    pred = {"not": [{"caller": "alice"}]}
    _author_hard(run_op, "to-resolve-vw", visible_when=pred)
    run_op("kernel.ir.resolve", {
        "ir_id": "to-resolve-vw",
        "resolver_id": "test-resolver-vw",
        "resolution_text": "Done.",
        "cost_actual": {"clock_ms": 1, "coin_usd": 0, "carbon_g": 0},
    })
    rec = parse_file(repo / "ir" / "_kernel" / "to-resolve-vw.md")
    assert rec.frontmatter["status"] == "resolved"
    assert rec.frontmatter["visible_when"] == pred


def test_visible_when_preserved_through_cancel(initialized: Path, run_op):
    repo = initialized
    pred = {"not": [{"caller": "alice"}]}
    _author_hard(run_op, "to-cancel-vw", visible_when=pred)
    run_op("kernel.ir.cancel", {
        "ir_id": "to-cancel-vw",
        "cancelled_by": "test-author",
        "authored_via": "kernel.self",
    })
    rec = parse_file(repo / "ir" / "_kernel" / "to-cancel-vw.md")
    assert rec.frontmatter["status"] == "cancelled"
    assert rec.frontmatter["visible_when"] == pred


# ---------------------------------------------------------------------------
# Tests 21-24 — reindex --check
# ---------------------------------------------------------------------------


def test_reindex_check_accepts_records_without_visible_when(initialized: Path, run_op):
    _author_convention(run_op, "no-pred-check")
    run_op("kernel.reindex", {"mode": "check"})  # should not raise


def test_reindex_check_accepts_null_visible_when(initialized: Path, run_op):
    repo = initialized
    rec_path = repo / "ir" / "test-scope" / "null-pred-check.md"
    _author_convention(run_op, "null-pred-check")
    rec = parse_file(rec_path)
    rec.frontmatter["visible_when"] = None
    rec_path.write_text(serialize(rec))
    run_op("kernel.reindex", {"mode": "rebuild"})
    run_op("kernel.reindex", {"mode": "check"})  # should not raise


def test_reindex_check_rejects_malformed_predicate(initialized: Path, run_op):
    repo = initialized
    rec_path = repo / "ir" / "_kernel" / "broken-pred.md"
    _author_hard(run_op, "broken-pred",
                 visible_when={"not": [{"caller": "alice"}]})
    rec = parse_file(rec_path)
    # Direct-edit drift to a malformed predicate.
    rec.frontmatter["visible_when"] = {"any": []}  # empty array — invalid
    rec_path.write_text(serialize(rec))
    run_op("kernel.reindex", {"mode": "rebuild"})
    with pytest.raises(KernelError) as exc:
        run_op("kernel.reindex", {"mode": "check"})
    assert exc.value.code == SCHEMA_INVALID
    flagged = exc.value.extra_context["records_with_invalid_visible_when"]
    assert any("broken-pred" in entry["path"] for entry in flagged)


def test_reindex_check_rejects_visible_when_on_non_hard_record(initialized: Path, run_op):
    """Defense-in-depth: kernel.ir.new rejects this at write time, but a
    direct-edit drift would otherwise leave a non-hard record carrying
    visible_when on disk. Reindex --check catches it."""
    repo = initialized
    rec_path = repo / "ir" / "test-scope" / "drift-pred.md"
    _author_convention(run_op, "drift-pred")
    rec = parse_file(rec_path)
    # Direct-edit: convention record gains a predicate via filesystem drift.
    rec.frontmatter["visible_when"] = {"not": [{"caller": "alice"}]}
    rec_path.write_text(serialize(rec))
    run_op("kernel.reindex", {"mode": "rebuild"})
    with pytest.raises(KernelError) as exc:
        run_op("kernel.reindex", {"mode": "check"})
    assert exc.value.code == SCHEMA_INVALID
    flagged = exc.value.extra_context["records_with_invalid_visible_when"]
    assert any(
        "drift-pred" in e["path"] and "non-hard" in e["problem"]
        for e in flagged
    )


# ---------------------------------------------------------------------------
# Test 25 — upgrade is clean
# ---------------------------------------------------------------------------


def test_upgrade_from_dev3_to_current_is_clean(repo: Path, run_op):
    """Block 4.4 changes no vendored projection bodies — the predicate
    schema lives in kernel.ir.new's input schema, not in any _kernel.*
    projection body. Upgrade-mode reports refreshed.vendored_projection_bodies: [].
    (Per Block 4.3 F1: KERNEL_VERSION import only; no hard-coded version
    strings.)"""
    run_op("kernel.init", {
        "project_name": "test-project",
        "primary_scope_id": "test-scope",
        "primary_operator_id": "test-author",
        "kernel_version": KERNEL_VERSION,
    })
    (repo / ".8os" / "version").write_text("1.1.0-dev.3\n")

    env = run_op("kernel.init", {
        "project_name": "test-project",
        "primary_scope_id": "test-scope",
        "primary_operator_id": "test-author",
        "kernel_version": KERNEL_VERSION,
    })
    assert env["data"]["mode"] == "upgrade"
    assert env["data"]["previous_version"] == "1.1.0-dev.3"
    assert env["data"]["kernel_version"] == KERNEL_VERSION
    assert env["data"]["refreshed"]["vendored_projection_bodies"] == []
    assert env["data"]["added"]["vendored_projection_bodies"] == []

    env_again = run_op("kernel.init", {
        "project_name": "test-project",
        "primary_scope_id": "test-scope",
        "primary_operator_id": "test-author",
        "kernel_version": KERNEL_VERSION,
    })
    assert env_again["data"]["mode"] == "noop"
