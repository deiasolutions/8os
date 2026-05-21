"""Walker tests — find_dispatchable_leaves filtering rules."""

from __future__ import annotations

from eightos.factory.walker import (
    KERNEL_CONFIGURATION_PROJECTION_TYPES,
    find_dispatchable_leaves,
)


def test_walker_returns_empty_for_unknown_scope(initialized):
    leaves = find_dispatchable_leaves(initialized, "no-such-scope")
    assert leaves == []


def test_walker_finds_open_intention(initialized, author_intention):
    author_intention("leaf-1")
    leaves = find_dispatchable_leaves(initialized, "test-scope")
    ids = [r.frontmatter["id"] for r in leaves]
    assert ids == ["leaf-1"]


def test_walker_skips_resolved(initialized, author_intention):
    author_intention("done", status="resolved")
    author_intention("open")
    ids = [r.frontmatter["id"] for r in find_dispatchable_leaves(initialized, "test-scope")]
    assert ids == ["open"]


def test_walker_respects_depends_on(initialized, author_intention):
    author_intention("dep", status="open")
    author_intention("leaf", depends_on=["dep"])
    # `leaf` is blocked because `dep` is open.
    ids = [r.frontmatter["id"] for r in find_dispatchable_leaves(initialized, "test-scope")]
    assert ids == ["dep"]


def test_walker_unblocks_when_depends_on_resolved(initialized, author_intention):
    author_intention("dep", status="resolved")
    author_intention("leaf", depends_on=["dep"])
    ids = sorted(r.frontmatter["id"] for r in find_dispatchable_leaves(initialized, "test-scope"))
    assert ids == ["leaf"]


def test_walker_treats_missing_dep_as_unresolved(initialized, author_intention):
    author_intention("leaf", depends_on=["ghost"])
    assert find_dispatchable_leaves(initialized, "test-scope") == []


def test_walker_excludes_kernel_configuration_types(initialized, author_intention):
    # All five v0.2 configuration types should be filtered out.
    for ptype in KERNEL_CONFIGURATION_PROJECTION_TYPES:
        slug = ptype.replace(".", "-")
        author_intention(f"cfg-{slug}", projection_types=[ptype])
    assert find_dispatchable_leaves(initialized, "test-scope") == []


def test_walker_excludes_all_kernel_projection_types(initialized, author_intention):
    # Operation-output _kernel.* projections (predictions, capability-
    # updates, calibration policies, etc.) are also excluded — the
    # factory dispatches resolvers against work intentions only, not
    # against system-internal records.
    for ptype in ("_kernel.prediction", "_kernel.calibration-policy",
                  "_kernel.capability-update", "_kernel.tier3-event"):
        slug = ptype.replace(".", "-").replace("_", "")
        author_intention(f"sys-{slug}", projection_types=[ptype])
    assert find_dispatchable_leaves(initialized, "test-scope") == []


def test_walker_finds_records_in_subdirectories(initialized, author_intention):
    # Records under nested subdirs (e.g., a workload's organizational
    # subdirectory) are still found by rglob. Use a plain work
    # intention with no kernel-* projection types so the walker
    # accepts it.
    p = initialized / "ir" / "test-scope" / "subdir"
    p.mkdir(parents=True, exist_ok=True)
    author_intention("nested-leaf")
    src = initialized / "ir" / "test-scope" / "nested-leaf.md"
    dst = p / "nested-leaf.md"
    dst.write_text(src.read_text())
    src.unlink()
    ids = [r.frontmatter["id"] for r in find_dispatchable_leaves(initialized, "test-scope")]
    assert "nested-leaf" in ids
