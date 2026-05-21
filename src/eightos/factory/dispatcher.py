"""Factory dispatcher — two-case dispatch (inside vs bridge).

Block 3 Piece 1, Shape 5; expanded in Piece 5. Inside resolvers
(`bridge: null`) get direct function calls. Bridge-crossing resolvers
(`bridge: <id>`) go through `kernel.bridge.cross`, which authorizes,
audits, and records the crossing.

The dispatcher's contract:

    dispatch(entry, intention, repo) -> dict

where the returned dict has been passed through the resolver's adapter
(per Shape 4), with shape `{resolution_text, resolution_value?,
cost_actual}`.

Bridge-cross payload (Piece 5 update): when the resolver declares a
`module:` (or has an `implementation:`) whose Python module exposes a
`build_payload(intention_text) -> dict` function, the dispatcher uses
that to assemble the bridge payload (typically a Messages API request
with system + user messages). Otherwise it falls back to the Piece 1
minimal `{"intention_id": <id>, "intention_text": <text>}` echo —
preserving backward compatibility for synthetic bridge resolvers in
tests.

This decouples bridge-crossing resolvers' prompt-construction from
the dispatcher: each LLM resolver's module owns its prompt and how it
shapes the user message; the dispatcher only routes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .._frontmatter import IRRecord
from ..sdk._runner import run as run_op
from . import context
from .registry import ResolverEntry


def dispatch(
    entry: ResolverEntry,
    intention: IRRecord,
    repo: Path,
) -> dict[str, Any]:
    """Dispatch one resolver against one intention; return adapted output.

    Inside path: `entry.load_impl()(intention.frontmatter["id"])`.
    Bridge path: `kernel.bridge.cross(...)` with the entry's bridge_id,
    standing authorization, and a minimal payload.

    The result is passed through `entry.load_adapter()` before return.
    """
    intention_id = intention.frontmatter["id"]

    # Block 3 Piece 5: thread the current intention id into factory.context
    # so build_payload / adapt / inside resolvers can read it without the
    # dispatcher having to pass it through every signature. Cleared in
    # the finally block so subsequent dispatches don't see stale state.
    context.set_current_intention_id(intention_id)
    try:
        if entry.bridge is None:
            impl = entry.load_impl()
            raw_result = impl(intention_id)
        else:
            builder = entry.load_payload_builder()
            if builder is not None:
                inner_payload = builder(intention.intention_text)
            else:
                inner_payload = {
                    "intention_id": intention_id,
                    "intention_text": intention.intention_text,
                }
            cross_payload = {
                "bridge_id": entry.bridge,
                "resolver_id": entry.resolver_id,
                "for_ir_id": intention_id,
                "authorization_id": entry.standing_authorization,
                "payload": inner_payload,
            }
            envelope = run_op("kernel.bridge.cross", cross_payload)
            raw_result = envelope["data"]["response"]

        adapter = entry.load_adapter()
        return adapter(raw_result)
    finally:
        context.set_current_intention_id(None)
