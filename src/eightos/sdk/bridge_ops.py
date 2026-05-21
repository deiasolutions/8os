"""kernel.bridge.cross — record-side of a bridge crossing (Block 1 v0.2 §4.4).

`kernel.bridge.add` was removed in v0.2 §4.8. Bridges are now (I, R)s of
projection_types: [_kernel.bridge] under ir/_kernel/bridge/<id>.md and are
authored through `kernel.ir.new`.

`cross` validates the bridge and resolver — both as kernel-configuration
(I, R)s — checks authorization if required, dispatches to the bridge's
outside-contact code if registered, writes a tier 3 event recording the
crossing, and returns the response.

Block 3 Piece 3 wires the real outside-contact dispatch (closes
OPEN-Q-006). When the bridge (I, R)'s frontmatter declares an
`implementation: <module>:<function>` field, `cross` imports that
function and calls it with `(bridge_id, payload, authorization, repo)`.
The function returns `{resolution, cost_actual, audit}`; `cross` records
the real cost and resolution in the tier 3 event. When `implementation:`
is absent, `cross` falls back to v0.2 echo behavior — preserving the
`kernel.self` cogito bridge and any other bridge authored before the
field convention existed.

The `implementation:` field is read directly from frontmatter; it is
not declared in the vendored `_kernel.bridge` projection body. Same
shape as resolvers' `implementation:` per OPEN-Q-026 (expanded to
cover bridges in Block 3 Piece 3). Consequence: bridges in Block 3
must be hand-authored as committed `.md` files; SDK-authored bridges
cannot carry `implementation:` until v1.0.1-full or v1.0.2 amends the
vendored body.
"""

from __future__ import annotations

from typing import Any

from .._atomic import append_jsonl_line
from .._events import make_event, write_raw_payload
from .._frontmatter import parse_file
from .._indexes import write_all
from .._paths import event_jsonl_path, kernel_record_path
from .._time import now_iso
from ..errors import (
    AUTHORIZATION_REQUIRED,
    BRIDGE_FAILED,
    BRIDGE_UNREACHABLE,
    NOT_FOUND,
    KernelError,
)
from ._common import repo_root_or_raise


def cross(payload: dict[str, Any]) -> dict[str, Any]:
    repo = repo_root_or_raise()
    bid = payload["bridge_id"]
    rid = payload["resolver_id"]
    for_ir = payload["for_ir_id"]
    auth_id = payload.get("authorization_id")
    user_payload = payload.get("payload")

    bridge_path = kernel_record_path(repo, "bridge", bid)
    if not bridge_path.exists():
        raise KernelError(
            NOT_FOUND,
            f"bridge {bid!r} not registered (no {bridge_path.relative_to(repo)})",
        )
    resolver_path = kernel_record_path(repo, "resolver", rid)
    if not resolver_path.exists():
        raise KernelError(
            NOT_FOUND,
            f"resolver {rid!r} not registered (no {resolver_path.relative_to(repo)})",
        )

    bridge_fm = parse_file(bridge_path).frontmatter
    if bridge_fm.get("requires_authorization") and not auth_id:
        raise KernelError(
            AUTHORIZATION_REQUIRED,
            f"bridge {bid!r} requires authorization; pass authorization_id",
            input_field="authorization_id",
        )

    if bridge_fm.get("bridge_status") == "quarantined":
        raise KernelError(BRIDGE_UNREACHABLE, f"bridge {bid!r} is quarantined")

    # Block 3 Piece 3: real outside-contact dispatch when the bridge
    # declares an `implementation:` field. Authorization frontmatter is
    # threaded so the bridge function can attach it to its audit.
    impl_spec = bridge_fm.get("implementation")
    auth_fm: dict[str, Any] | None = None
    if auth_id:
        auth_fm = _load_authorization_fm(repo, auth_id)

    if impl_spec:
        try:
            response = _dispatch_via_implementation(
                impl_spec, bid, user_payload, auth_fm, repo
            )
        except KernelError:
            raise  # Already a kernel error — propagate as-is.
        except Exception as e:  # noqa: BLE001 - bridge fault → BRIDGE_FAILED
            raise KernelError(
                BRIDGE_FAILED,
                f"bridge {bid!r} implementation {impl_spec!r} raised: "
                f"{type(e).__name__}: {e}",
            ) from e
        resolution_text = _stringify_resolution(response.get("resolution"))
        resolution_structured = response.get("resolution")
        cost = _normalize_cost(response.get("cost_actual"))
        audit = response.get("audit") or {}
    else:
        # v0.2 echo path — preserves backward compatibility for bridges
        # authored before the `implementation:` field convention. The
        # bootstrap `kernel.self` bridge takes this path.
        response = None
        resolution_text = "(payload returned to caller; no outside transport in v0.2)"
        resolution_structured = {"echo": user_payload}
        cost = {
            "clock_ms": 0,
            "coin_usd": 0,
            "carbon_g": 0,
            "model_name": None,
            "tokens_in": None,
            "tokens_out": None,
        }
        audit = {}

    ts = now_iso()
    event = make_event(
        event_type="resolution",
        ir_node_id=for_ir,
        ir_node_path_at_event=str(_locate(repo, for_ir)),
        resolver_id=rid,
        bridge_id=bid,
        intention={
            "text": f"Cross bridge {bid!r} for (I, R) {for_ir!r}.",
            "context_refs": [for_ir] if auth_id is None else [for_ir, auth_id],
            "scope": "_ops",
            "depth": 0,
        },
        resolution={
            "text": resolution_text,
            "structured": resolution_structured,
            "authority_level": bridge_fm.get("authority_level", "uncalibrated"),
            **({"audit": audit} if audit else {}),
        },
        cost_actual=cost,
        outcome="accepted",
        ts=ts,
    )
    raw_path: str | None = None
    if user_payload is not None:
        p = write_raw_payload(repo, event["event_id"], user_payload)
        raw_path = str(p.relative_to(repo))
        event["raw_payload_ref"] = raw_path

    append_jsonl_line(event_jsonl_path(repo, ts), event)
    write_all(repo)
    return {
        "data": {
            "response": (
                response if response is not None else {"echo": user_payload}
            ),
            "cost_actual": cost,
            "raw_payload_ref": raw_path,
        },
        "event_id": event["event_id"],
        "indexes_updated": ["resolver-to-events", "_checksum"],
    }


def _dispatch_via_implementation(
    impl_spec: str,
    bridge_id: str,
    user_payload: Any,
    authorization: dict[str, Any] | None,
    repo,
) -> dict[str, Any]:
    """Import `<module>:<function>` and call the bridge implementation."""
    import importlib

    if ":" not in impl_spec:
        raise KernelError(
            BRIDGE_FAILED,
            f"bridge implementation {impl_spec!r} must be 'module:function'",
        )
    module_path, func_name = impl_spec.split(":", 1)
    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        raise KernelError(
            BRIDGE_FAILED,
            f"could not import bridge module {module_path!r}: {e}",
        ) from e
    func = getattr(module, func_name, None)
    if func is None:
        raise KernelError(
            BRIDGE_FAILED,
            f"bridge module {module_path!r} has no function {func_name!r}",
        )
    return func(bridge_id, user_payload, authorization, repo)


def _load_authorization_fm(repo, auth_id: str) -> dict[str, Any] | None:
    """Look up the authorization (I, R)'s frontmatter via the id-to-path index."""
    from .._yaml import load_yaml_file

    idx = load_yaml_file(repo / ".8os" / "index" / "id-to-path.yml") or {}
    rel = idx.get(auth_id)
    if not rel:
        return None
    path = repo / rel
    if not path.exists():
        return None
    return parse_file(path).frontmatter


def _normalize_cost(cost: Any) -> dict[str, Any]:
    """Coerce a bridge function's cost_actual into the canonical shape.

    Missing keys default to 0/null. Bridge functions are encouraged to
    return all six fields, but tolerating partial returns keeps the
    contract forgiving while keeping the event log shape stable.
    """
    base = {
        "clock_ms": 0,
        "coin_usd": 0,
        "carbon_g": 0,
        "model_name": None,
        "tokens_in": None,
        "tokens_out": None,
    }
    if isinstance(cost, dict):
        for k in base:
            if k in cost:
                base[k] = cost[k]
    return base


def _stringify_resolution(resolution: Any) -> str:
    """Produce a string for the tier 3 event's `resolution.text` field."""
    if resolution is None:
        return ""
    if isinstance(resolution, str):
        return resolution
    return str(resolution)


def _locate(repo, ir_id: str) -> str:
    from .._yaml import load_yaml_file as _ly

    idx = _ly(repo / ".8os" / "index" / "id-to-path.yml") or {}
    return idx.get(ir_id, "<unknown>")
