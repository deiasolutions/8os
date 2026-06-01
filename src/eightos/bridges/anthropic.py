"""Anthropic Messages API bridge — first real outside-contact bridge.

Block 3 Piece 3. Closes OPEN-Q-006 by virtue of being the first bridge
implementation living under `src/eightos/bridges/` and registered via
the bridge (I, R)'s `implementation:` field.

Bridge function contract (called by `kernel.bridge.cross` when the
bridge (I, R)'s `implementation:` field resolves here):

    cross(bridge_id, payload, authorization, repo) -> {
        resolution: str | dict,
        cost_actual: {
            clock_ms: float,
            coin_usd: float,
            carbon_g: float,
            model_name: str | None,
            tokens_in: int | None,
            tokens_out: int | None,
        },
        audit: dict,  # extra info for the tier 3 event
    }

Auth: OAuth via the credential path Claude Code uses on this machine
(NOT `ANTHROPIC_API_KEY`). `_load_oauth_credentials` is the entry
point; see Block 3 Piece 3 commit body for current OAuth status (real
or stub).

If `_load_oauth_credentials` returns None (no credential available),
the bridge falls back to a deterministic stub response so Pieces 4–6
can run end-to-end against the stub. Tests exercising the real API
must be gated on credential availability via
`_oauth_credentials_available()` and skipped otherwise.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

# Sentinel for stub responses — keeps the dispatch path honest about
# which path produced the output.
_STUB_RESOLUTION_PREFIX = "[stub] "

_ANTHROPIC_DEFAULT_MODEL = "claude-haiku-4-5"

# Pricing per million tokens (USD). Updated 2026-04. The bridge (I, R)
# can later carry these in its frontmatter for live updates without
# code changes; for Piece 3 the values live here so the bridge module
# is self-contained.
_PRICING_USD_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-haiku-4-5": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-7": {"input": 15.00, "output": 75.00},
}


def cross(
    bridge_id: str,
    payload: dict[str, Any],
    authorization: dict[str, Any] | None,
    repo: Path,
) -> dict[str, Any]:
    """Cross the Anthropic bridge.

    `payload` is the caller's request shape. The Messages API form is:

        {
            "model": "<claude-...>",
            "messages": [{"role": "user", "content": "..."}],
            "max_tokens": 4096,
            "system": "...",  # optional
        }

    Other shapes (e.g., the factory's minimal `{intention_id,
    intention_text}` from Piece 1's bridge dispatch) are tolerated and
    coerced into a Messages API request with the intention_text as the
    user message.

    `authorization` is the standing-authorization (I, R)'s
    frontmatter, threaded by `kernel.bridge.cross` (when an
    authorization_id was provided). The bridge does not enforce
    authorization itself — that's the kernel's job — but receives the
    structure for audit purposes.

    `repo` is the 8os repo root. Used for credential lookup paths.
    """
    request = _coerce_to_messages_request(payload)
    creds = _load_oauth_credentials()
    if creds is None:
        return _stub_response(bridge_id, request)
    return _real_call(bridge_id, request, creds)


def _coerce_to_messages_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Coerce a caller's payload into a Messages API request shape.

    Accepts either a fully-formed Messages API request, or a
    factory-style minimal payload `{intention_id, intention_text}`
    which gets wrapped into a single user message.
    """
    if isinstance(payload, dict) and "messages" in payload:
        return {
            "model": payload.get("model") or _ANTHROPIC_DEFAULT_MODEL,
            "messages": payload["messages"],
            "max_tokens": payload.get("max_tokens", 4096),
            **({"system": payload["system"]} if payload.get("system") else {}),
        }
    intention_text = (
        payload.get("intention_text")
        if isinstance(payload, dict)
        else str(payload)
    )
    return {
        "model": _ANTHROPIC_DEFAULT_MODEL,
        "messages": [{"role": "user", "content": intention_text or "(no payload)"}],
        "max_tokens": 4096,
    }


def _load_oauth_credentials() -> dict[str, Any] | None:
    """Return a token bundle suitable for the Anthropic Messages API,
    or None if no credential is available.

    Mirrors Claude Code's OAuth path on this machine — same credential
    store, same refresh flow. Implementation status is tracked in the
    Block 3 Piece 3 commit body; see OPEN-Q-028 for any blockers.
    """
    # Probe order — first hit wins:
    # 1. CLAUDE_CODE_OAUTH_TOKEN env var (explicit override; useful for
    #    CI runners that ship a token through env).
    # 2. ~/.claude/credentials.json (Claude Code's default credential
    #    file when not using Keychain).
    # 3. macOS Keychain entry under "Claude Code-credentials" (the
    #    actual production storage location on this machine).
    # The third probe needs the `security` CLI; skipped if not present.
    env_token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if env_token:
        return {"access_token": env_token, "source": "env"}

    creds_file = Path.home() / ".claude" / "credentials.json"
    if creds_file.exists():
        try:
            import json

            data = json.loads(creds_file.read_text(encoding="utf-8"))
            token = (
                data.get("claudeAiOauth", {}).get("accessToken")
                if isinstance(data, dict)
                else None
            )
            if token:
                return {"access_token": token, "source": "file"}
        except (OSError, ValueError):
            pass

    keychain = _try_keychain_lookup()
    if keychain:
        return keychain

    return None


def _try_keychain_lookup() -> dict[str, Any] | None:
    """macOS Keychain lookup for Claude Code's stored OAuth token.

    Best-effort. If `security` CLI isn't available or the entry isn't
    present, returns None. Mr Code's OAuth investigation in Piece 3
    determined the entry name; if blocked, this function returns None
    and the bridge falls back to the stub.
    """
    import shutil
    import subprocess

    if not shutil.which("security"):
        return None
    # Common entry names to try; the production name lives in a
    # constant if/when investigation pins it down.
    for entry_name in ("Claude Code-credentials", "Claude Code"):
        try:
            r = subprocess.run(
                [
                    "security",
                    "find-generic-password",
                    "-s",
                    entry_name,
                    "-w",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (subprocess.TimeoutExpired, OSError):
            continue
        if r.returncode == 0 and r.stdout.strip():
            payload = r.stdout.strip()
            # Keychain may store either a raw token or a JSON blob with
            # accessToken/refreshToken. Handle both.
            try:
                import json

                data = json.loads(payload)
                token = (
                    data.get("claudeAiOauth", {}).get("accessToken")
                    if isinstance(data, dict)
                    else None
                )
                if token:
                    return {"access_token": token, "source": "keychain-json"}
            except ValueError:
                pass
            # Treat as raw bearer token.
            return {"access_token": payload, "source": "keychain-raw"}
    return None


def _oauth_credentials_available() -> bool:
    """Cheap check for test gating — returns True iff a credential
    can be loaded right now."""
    return _load_oauth_credentials() is not None


def _real_call(
    bridge_id: str,
    request: dict[str, Any],
    creds: dict[str, Any],
) -> dict[str, Any]:
    """Hit the Anthropic Messages API for real.

    OAuth bearer flow. Captures `usage.input_tokens` and
    `usage.output_tokens` from the response; computes
    `cost_actual.coin_usd` from `_PRICING_USD_PER_MTOK`.
    """
    # Lazy import — the bridge function is import-clean even if the
    # `anthropic` SDK isn't installed; the import only runs when a
    # real call actually fires.
    try:
        import urllib.error
        import urllib.request
        import json
    except ImportError as e:  # pragma: no cover — stdlib always present
        from ..errors import BRIDGE_FAILED, KernelError

        raise KernelError(BRIDGE_FAILED, f"stdlib import failed: {e}") from e

    body = json.dumps(request).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "oauth-2025-04-20",
            "authorization": f"Bearer {creds['access_token']}",
        },
        method="POST",
    )
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            response_text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        from ..errors import BRIDGE_FAILED, KernelError

        body_text = e.read().decode("utf-8", errors="replace")
        raise KernelError(
            BRIDGE_FAILED,
            f"Anthropic API HTTP {e.code}: {body_text[:500]}",
            input_field=None,
            offending_value=None,
            suggested_action="check OAuth token validity / API status",
        ) from e
    except urllib.error.URLError as e:
        from ..errors import BRIDGE_FAILED, KernelError

        raise KernelError(
            BRIDGE_FAILED,
            f"Anthropic API network error: {e.reason}",
        ) from e
    elapsed_ms = (time.monotonic() - start) * 1000.0

    response = json.loads(response_text)
    content = response.get("content") or []
    text_parts = [c.get("text", "") for c in content if c.get("type") == "text"]
    resolution_text = "".join(text_parts) or "(empty response)"
    usage = response.get("usage") or {}
    tokens_in = usage.get("input_tokens")
    tokens_out = usage.get("output_tokens")
    model = response.get("model") or request.get("model") or _ANTHROPIC_DEFAULT_MODEL
    coin_usd = _compute_cost(model, tokens_in or 0, tokens_out or 0)

    return {
        "resolution": resolution_text,
        "cost_actual": {
            "clock_ms": elapsed_ms,
            "coin_usd": coin_usd,
            "carbon_g": _estimate_carbon(tokens_in or 0, tokens_out or 0),
            "model_name": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        },
        "audit": {
            "source": creds.get("source"),
            "stop_reason": response.get("stop_reason"),
            "response_id": response.get("id"),
        },
    }


def _stub_response(bridge_id: str, request: dict[str, Any]) -> dict[str, Any]:
    """Deterministic canned response when no OAuth credential is available.

    Used by tests and as the Block 3 fallback path when OAuth
    investigation is blocked. Stub deliberately echoes the request's
    last user message so callers can sanity-check end-to-end wiring
    (the factory's prompt threads all the way through to the bridge).
    """
    last_msg = ""
    for msg in reversed(request.get("messages") or []):
        if msg.get("role") == "user":
            content = msg.get("content")
            last_msg = content if isinstance(content, str) else str(content)
            break
    text = (
        f"{_STUB_RESOLUTION_PREFIX}bridge={bridge_id} "
        f"model={request.get('model')!r}; received={last_msg[:200]!r}"
    )
    return {
        "resolution": text,
        "cost_actual": {
            "clock_ms": 1.0,
            "coin_usd": 0.0,
            "carbon_g": 0.0,
            "model_name": request.get("model"),
            "tokens_in": 0,
            "tokens_out": 0,
        },
        "audit": {"source": "stub", "reason": "no-oauth-credential-available"},
    }


def _compute_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Compute Messages API cost in USD from token counts.

    Anthropic returns model strings with a date suffix (e.g.,
    `claude-haiku-4-5-20251001`); the pricing map keys off the
    family-version stem. Try the literal key first, then strip
    a trailing `-YYYYMMDD` and retry.
    """
    prices = _PRICING_USD_PER_MTOK.get(model)
    if not prices:
        # Strip a trailing -<YYYYMMDD> if present.
        if len(model) >= 9 and model[-9] == "-" and model[-8:].isdigit():
            stem = model[:-9]
            prices = _PRICING_USD_PER_MTOK.get(stem)
    if not prices:
        return 0.0
    return (tokens_in * prices["input"] + tokens_out * prices["output"]) / 1_000_000


def _estimate_carbon(tokens_in: int, tokens_out: int) -> float:
    """Order-of-magnitude carbon estimate per LLM call.

    Symbolic; not used for VOI in v1.0. ~0.001 g CO2e per token is the
    rough industry figure for inference-time emissions, varying by
    model size and datacenter mix.
    """
    return (tokens_in + tokens_out) * 0.001
