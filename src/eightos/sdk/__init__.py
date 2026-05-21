"""SDK operation registry.

Every operation is a function `def op(payload: dict) -> dict` that accepts a
validated input payload and returns the success envelope `data` portion. The
registry maps canonical op names (with the `kernel.` prefix) to handlers.

The runner in `_runner.py` wraps every handler with: input validation, error
translation, and output validation against the schemas in
`eightos.schemas`.
"""

from __future__ import annotations

from typing import Callable

from . import init_op, ir_ops, reindex_op
from . import bridge_ops, authorize_op, gatekeeper_op, selector_op
from . import event_op
from . import outside_http_op

# v1.1 SDK operation set. `kernel.ir.cancel` is new in v1.1; the
# `kernel.surrogate.train` interface stub from v0.1 is removed in v1.1
# (surrogate training is userspace; v1.1 does not commit the kernel to
# hosting a training pipeline — see v1.1 §3.0 and decisions log §4.4).
# The remaining ops are preserved unchanged from v1.0.1-partial.
# `kernel.resolver.add` and `kernel.bridge.add` were removed in v0.2;
# configuration is content authored through `kernel.ir.new`.
OP_HANDLERS: dict[str, Callable[[dict], dict]] = {
    "kernel.init": init_op.run,
    "kernel.reindex": reindex_op.run,
    "kernel.ir.new": ir_ops.new,
    "kernel.ir.get": ir_ops.get,
    "kernel.ir.list": ir_ops.list_,
    "kernel.ir.resolve": ir_ops.resolve,
    "kernel.ir.expand": ir_ops.expand,
    "kernel.ir.collapse": ir_ops.collapse,
    "kernel.ir.promote": ir_ops.promote,
    "kernel.ir.supersede": ir_ops.supersede,
    "kernel.ir.cancel": ir_ops.cancel,
    "kernel.ir.deps": ir_ops.deps,
    "kernel.bridge.cross": bridge_ops.cross,
    "kernel.authorize": authorize_op.run,
    "kernel.gatekeeper.check": gatekeeper_op.run,
    "kernel.selector.select": selector_op.run,
    "kernel.event.get": event_op.get,
    # v1.1 §11 (Block 4.8): kernel.outside.http is the canonical outside-
    # call primitive. Per §11.9 it is NOT counted among the SDK operations
    # (it lives in the outside-call category per axiom 0); the runner
    # dispatches it like any other op for uniformity.
    "kernel.outside.http": outside_http_op.run,
}


# Short-form aliases (without the `kernel.` prefix) for ergonomic CLI use.
OP_ALIASES: dict[str, str] = {
    name.removeprefix("kernel."): name for name in OP_HANDLERS
}


def canonicalize(op_name: str) -> str:
    """Map an op name (canonical or short alias) to its canonical form."""
    if op_name in OP_HANDLERS:
        return op_name
    if op_name in OP_ALIASES:
        return OP_ALIASES[op_name]
    raise KeyError(op_name)


__all__ = ["OP_HANDLERS", "OP_ALIASES", "canonicalize"]
