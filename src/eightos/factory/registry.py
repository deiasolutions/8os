"""Factory registry — load resolver implementations by import path.

Block 3 Piece 1, expanded in Piece 5. Each resolver (I, R) under
`ir/_kernel/resolver/<id>.md` declares zero, one, or both of:

- `implementation: <module>:<function>` — for inside resolvers; the
  function is the resolution body. Block 3 Piece 1.
- `module: <module-path>` — for bridge-crossing resolvers that need
  custom prompt-building or output-parsing logic. Used to discover
  the adapter (`adapt`) and an optional `build_payload(intention_text)
  -> dict` function the dispatcher uses to assemble the bridge payload
  with system + user messages. Block 3 Piece 5.

Plus an output-mode declaration:
- `produces: value | graph` — default `value`. When `graph`, the
  factory's tick takes the graph-producing branch — calls the
  materializer with the resolution_value as graph spec instead of
  calling `kernel.ir.resolve` on the parent (decomposer pattern).
  Block 3 Piece 5.

Plus a standing authorization:
- `standing_authorization: <auth-id>` — for bridge-crossing resolvers,
  the (I, R) id of the standing `_kernel.authorization` record that
  authorizes their crossing. Block 3 Piece 4.

See OPEN-Q-026 for why none of these fields are declared in the
vendored `_kernel.resolver` body and why the records carrying them are
hand-authored rather than authored via `kernel.ir.new`.

Adapter convention: same module as `implementation`, function name
`adapt`. For bridge-crossing resolvers without `implementation`, the
registry tries `module` instead. If neither yields an `adapt`, the
registry returns `adapters.default_adapter`.

Payload-builder convention (bridge-crossing only): looks for
`build_payload(intention_text)` in the module discovered via
`implementation` then `module`. Returns `None` when no module is
declared or the module has no `build_payload` function — the
dispatcher's bridge path falls back to the minimal `{intention_id,
intention_text}` payload.

Caching is per-registry-instance (per-tick by default, since `tick`
creates a fresh `Registry`). Lazy: implementation modules are only
imported when `load_impl()` / `load_adapter()` / `load_payload_builder()`
is called.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .._frontmatter import parse_file
from .._paths import kernel_record_path
from . import adapters


class FactoryError(Exception):
    """Factory-level error. Distinct from kernel SCHEMA_INVALID etc.

    The factory is above the kernel. SDK-boundary errors propagate as
    `KernelError` from the SDK; factory-internal errors raise this.
    """


@dataclass(frozen=True)
class ResolverEntry:
    resolver_id: str
    bridge: str | None
    implementation: str | None  # "module.path:function" or None
    module: str | None  # bare module path for adapter/payload-builder discovery
    standing_authorization: str | None
    produces: str  # "value" (default) or "graph"

    @classmethod
    def from_frontmatter(cls, fm: dict) -> "ResolverEntry":
        return cls(
            resolver_id=fm["resolver_id"],
            bridge=fm.get("bridge"),
            implementation=fm.get("implementation"),
            module=fm.get("module"),
            standing_authorization=fm.get("standing_authorization"),
            produces=fm.get("produces") or "value",
        )

    def load_impl(self) -> Callable:
        if not self.implementation:
            raise FactoryError(
                f"resolver {self.resolver_id!r} has no `implementation:` "
                f"field; inside dispatch requires one. Bridge-crossing "
                f"resolvers go through kernel.bridge.cross instead."
            )
        return _import_callable(self.implementation)

    def _resolve_module_path(self) -> str | None:
        """Return the Python module path to look for `adapt` / `build_payload`.

        Inside resolvers' module is derived from `implementation`'s
        prefix; bridge-crossing resolvers can declare `module:`
        explicitly. Returns None when neither is set.
        """
        if self.implementation:
            return self.implementation.split(":", 1)[0]
        if self.module:
            return self.module
        return None

    def load_adapter(self) -> Callable:
        module_path = self._resolve_module_path()
        if module_path is None:
            return adapters.default_adapter
        module = importlib.import_module(module_path)
        return getattr(module, "adapt", adapters.default_adapter)

    def load_payload_builder(self) -> Callable | None:
        """Discover an optional `build_payload(intention_text) -> dict`.

        Used by the dispatcher's bridge path to assemble a richer
        Messages API payload (with system + user messages) for
        bridge-crossing resolvers that need it (decomposer,
        score-relevance, generate-briefing, recomposer). Returns None
        when the resolver's module has no such function — the
        dispatcher then falls back to the minimal echo payload.
        """
        module_path = self._resolve_module_path()
        if module_path is None:
            return None
        module = importlib.import_module(module_path)
        return getattr(module, "build_payload", None)


class Registry:
    """Per-tick cache of resolver records and their loaded implementations.

    Construct one per `tick`; the cache lifetime equals the registry's.
    Records are read from disk lazily (on first `get`); implementation
    modules are imported lazily (on first `load_impl` / `load_adapter`).
    """

    def __init__(self, repo: Path):
        self.repo = repo
        self._cache: dict[str, ResolverEntry] = {}

    def get(self, resolver_id: str) -> ResolverEntry:
        if resolver_id not in self._cache:
            path = kernel_record_path(self.repo, "resolver", resolver_id)
            if not path.exists():
                raise FactoryError(
                    f"resolver {resolver_id!r} not registered "
                    f"(no {path.relative_to(self.repo)})"
                )
            fm = parse_file(path).frontmatter
            self._cache[resolver_id] = ResolverEntry.from_frontmatter(fm)
        return self._cache[resolver_id]


def _import_callable(spec: str) -> Callable:
    if ":" not in spec:
        raise FactoryError(
            f"implementation {spec!r} must be 'module.path:function_name'"
        )
    module_path, func_name = spec.split(":", 1)
    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        raise FactoryError(
            f"could not import implementation module {module_path!r}: {e}"
        ) from e
    try:
        return getattr(module, func_name)
    except AttributeError as e:
        raise FactoryError(
            f"module {module_path!r} has no function {func_name!r}"
        ) from e
