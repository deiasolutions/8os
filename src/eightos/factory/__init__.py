"""Factory — the layer above the kernel that walks (I, R) graphs and dispatches resolvers.

Block 3 Piece 1. The factory is a Python package that uses only the
existing SDK operations. It is not an SDK extension and not a
kernel layer; it is a consumer of the kernel.

Single entry point: `tick(repo_root, scope)`. One tick = one walk + one
batch of dispatches. The factory does not loop internally; the caller
(test, script, or eventually a daemon) calls tick repeatedly until the
graph is fully resolved.

Five factory shapes from Block 2.9 (each gets implemented across
Pieces 1-6):

  Shape 1 — Predictor dispatch (Piece 2)
  Shape 2 — Holdout-aware concurrency (Piece 2)
  Shape 3 — Recursive pytest-as-self-test (handled by tests/factory/
            being a separate collection from tests/kernel/)
  Shape 4 — Resolution payload heterogeneity (this Piece, via the
            adapter convention in `adapters.py`)
  Shape 5 — Bridge-vs-inside dispatch differentiation (this Piece, via
            the two-case dispatcher in `dispatcher.py`)

This Piece (Piece 1) implements Shapes 4 and 5 plus the walker, registry,
and tick entry point. Predictor dispatch and parallel/holdout semantics
land in Piece 2.
"""

from __future__ import annotations

from .tick import FactoryError, tick

__all__ = ["FactoryError", "tick"]
