"""Factory tick-scoped context.

Block 3 Piece 2. Holds per-tick state (the repo path and the current
batch_id) that the dispatcher and inside resolvers may need without
threading it through every call signature.

`tick.py` sets the context at the start of a tick and clears it in a
finally block. Inside resolvers (e.g.,
`eightos.resolvers.test_pass_predictor.predict_from_intention`) call
the getters when they need access. The dispatcher's
`impl(intention_id)` signature stays uniform — no per-resolver
signature drift.

Module-level state, intentionally simple. If recursive `tick` calls
get added (e.g., the decomposer in Piece 4 manifests a sub-graph that
the same tick walks), this module needs push/pop semantics — save the
outer tick's repo/batch_id, set the inner's, restore on exit. The
current set/clear pair would silently overwrite the outer context
under recursion. Add the push/pop refactor when the first recursive
caller appears; do not pre-build it.

Other batch-scoped state the factory wants to thread later (current
scope, factory tick number, current dispatching resolver) can be
added here as additional set/get pairs. Keep flat until it becomes
unwieldy enough to refactor into a context object.
"""

from __future__ import annotations

from pathlib import Path

_repo: Path | None = None
_batch_id: str | None = None
_current_intention_id: str | None = None


def set_repo(repo: Path) -> None:
    """Set the current tick's repo. Called by `tick.tick` at start."""
    global _repo
    _repo = repo


def get_repo() -> Path:
    """Return the current tick's repo.

    Raises `RuntimeError` if called outside a tick (i.e., before
    `set_repo` has been called this process). Inside resolvers may
    call this without checking — if it raises, that's a real bug
    (the dispatcher should always set the context before invoking
    the impl).
    """
    if _repo is None:
        raise RuntimeError(
            "factory.context.get_repo() called outside a tick — "
            "the factory's tick entry point sets repo before dispatch."
        )
    return _repo


def set_batch_id(batch_id: str) -> None:
    """Set the current tick's batch_id. Called by `tick.tick` at start."""
    global _batch_id
    _batch_id = batch_id


def get_batch_id() -> str:
    """Return the current tick's batch_id.

    Raises `RuntimeError` outside a tick (same shape as `get_repo`).
    """
    if _batch_id is None:
        raise RuntimeError(
            "factory.context.get_batch_id() called outside a tick."
        )
    return _batch_id


def set_current_intention_id(intention_id: str | None) -> None:
    """Set the (I, R) being dispatched right now.

    Block 3 Piece 5 — used by the dispatcher just before invoking the
    inside resolver / bridge cross, so build_payload / adapt /
    inside-impl can read it without the dispatcher having to thread
    it through every signature. Set to None when leaving the dispatch
    of one leaf and before dispatching the next.
    """
    global _current_intention_id
    _current_intention_id = intention_id


def get_current_intention_id() -> str:
    """Return the intention id under dispatch right now.

    Raises `RuntimeError` when called outside an active dispatch.
    """
    if _current_intention_id is None:
        raise RuntimeError(
            "factory.context.get_current_intention_id() called outside a dispatch"
        )
    return _current_intention_id


def clear() -> None:
    """Clear the tick context. Called by `tick.tick` in finally."""
    global _repo, _batch_id, _current_intention_id
    _repo = None
    _batch_id = None
    _current_intention_id = None
