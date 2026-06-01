"""eightos.api — the public engine-port surface (in-process transport).

This is the ONLY supported import surface for consumers (the DES, sd-ortrta,
PyOrtrta). It is a thin typed facade over kernel internals: it re-exports and
lightly wraps them, and *references* canonical contracts — the Block-1 op
schemas, base frontmatter, projection declarations — rather than restating them.

Engine-port spec: ``docs/spec/drafts/8OS-ENGINE-PORT-SPEC`` (when promoted).

Slice 1 (this cut): op dispatch, leaf reads, the cost/record types, and three
pure-ish helpers. The simulate/real ``Session`` (spec §B) and leak containment
(spec §E) land in subsequent slices; nothing here changes existing behavior.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict

from ._events import make_event, write_event
from ._frontmatter import IRRecord
from ._projections import BASE_FRONTMATTER_FIELDS
from .factory.walker import find_dispatchable_leaves
from .sdk._runner import run as _run

__all__ = [
    "run",
    "leaves",
    "emit_marker",
    "cost_of",
    "is_feedable",
    "IRRecord",
    "CostVector",
    "Adapted",
    "Conformance",
    "Produces",
]


# ---- Types (mirror existing internal shapes; not new contracts) -------------


class CostVector(TypedDict):
    """The three-currency cost vector recorded on every tier-3 event."""

    clock_ms: float
    coin_usd: float
    carbon_g: float
    model_name: NotRequired[str | None]
    tokens_in: NotRequired[int | None]
    tokens_out: NotRequired[int | None]


class Adapted(TypedDict):
    """A resolver's adapted output (the factory adapter contract)."""

    resolution_text: str
    resolution_value: NotRequired[Any]
    cost_actual: CostVector


Produces = Literal["value", "graph"]


class Conformance(TypedDict):
    feedable: bool
    missing: list[str]


# Base fields a record must carry to be a feedable work intention. A subset of
# the canonical BASE_FRONTMATTER_FIELDS (asserted below so it cannot drift).
# Projection-specific required_frontmatter is validated authoritatively by
# ``kernel.ir.new`` — not duplicated here.
_FEEDABLE_REQUIRED: frozenset[str] = frozenset(
    {
        "id",
        "kind",
        "tier",
        "projection_types",
        "scope",
        "status",
        "authored_by",
        "authored_on",
        "authority_level",
        "authored_via",
    }
)
assert _FEEDABLE_REQUIRED <= BASE_FRONTMATTER_FIELDS  # stays in sync with canon


# ---- A. Op dispatch (promotes sdk._runner.run) ------------------------------


def run(op: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Dispatch any kernel op; return its success envelope.

    Op names and payload/return shapes are defined by the Block-1 spec and the
    per-op JSON schemas in ``eightos.schemas`` — not restated here. Raises
    ``eightos.errors.KernelError`` on failure.
    """
    return _run(op, payload)


# ---- C. Orchestration primitives --------------------------------------------


def leaves(repo: str | Path, scope: str) -> list[IRRecord]:
    """Dispatchable leaves in ``ir/<scope>/`` (open, deps resolved, non-config).

    Wraps ``factory.walker.find_dispatchable_leaves``.
    """
    return find_dispatchable_leaves(Path(repo), scope)


def emit_marker(
    repo: str | Path,
    *,
    kind: str,
    payload: dict[str, Any],
    resolver_id: str = "engine.marker",
    batch_id: str | None = None,
) -> str:
    """Emit an engine-authored tier-3 marker event; return its ``event_id``.

    A supported replacement for hand-importing ``_events``/``_atomic`` from a
    consumer (axiom-8-clean: engine self-claims are recorded the supported way).
    ``payload`` is carried verbatim on the event's intention.
    """
    intention: dict[str, Any] = {"kind": kind, **payload}
    if batch_id is not None:
        intention["batch_id"] = batch_id
    event = make_event(
        event_type="engine.marker",
        ir_node_id=batch_id or kind,
        ir_node_path_at_event="<n/a — engine marker>",
        resolver_id=resolver_id,
        bridge_id=None,
        intention=intention,
        resolution={"text": f"engine marker: {kind}", "authority_level": "convention"},
        outcome="accepted",
    )
    write_event(Path(repo), event)
    return event["event_id"]


# ---- D. Cost surface (pure read) --------------------------------------------


def cost_of(obj: dict[str, Any]) -> CostVector:
    """Read the cost vector off an op envelope or a tier-3 event.

    Looks for ``cost_actual`` at the top level or under ``data``; missing fields
    default to zero. Pure read; never mutates.
    """
    raw = obj.get("cost_actual")
    if raw is None and isinstance(obj.get("data"), dict):
        raw = obj["data"].get("cost_actual")
    raw = raw or {}
    return {
        "clock_ms": float(raw.get("clock_ms") or 0.0),
        "coin_usd": float(raw.get("coin_usd") or 0.0),
        "carbon_g": float(raw.get("carbon_g") or 0.0),
        "model_name": raw.get("model_name"),
        "tokens_in": raw.get("tokens_in"),
        "tokens_out": raw.get("tokens_out"),
    }


# ---- E. Conformance (references canon; base-level structural gate) ----------


def is_feedable(record: IRRecord) -> Conformance:
    """Whether an (I, R) carries the base structural fields to be fed to the factory.

    Checks presence of the canonical feedability base fields and a non-empty
    intention. Projection-specific ``required_frontmatter`` is validated
    authoritatively by ``kernel.ir.new``; this is the base-level structural gate.
    """
    fm = record.frontmatter or {}
    missing = [f for f in sorted(_FEEDABLE_REQUIRED) if fm.get(f) in (None, "")]
    if not (record.intention_text or "").strip():
        missing.append("intention_text")
    return {"feedable": not missing, "missing": missing}
