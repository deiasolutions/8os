"""Visibility-predicate parsing, validation, and evaluation (v1.1 §4.4).

Block 4.4. The `visible_when` field on (I, R) records carries an opaque
structured predicate the kernel evaluates at read time (`kernel.ir.get`,
`kernel.ir.list`, `kernel.ir.deps`). When the predicate evaluates false
for a caller, the record is treated as not-visible per axiom 3 (the
record's existence is suppressed in queries; `kernel.ir.get` returns
`IR_NOT_VISIBLE`).

The parsed form of a predicate is just the validated raw dict — there is
no separate AST. `parse_predicate` is therefore idempotent and effectively
just `validate_predicate(raw); return raw`. Evaluation walks the dict
recursively.

## Predicate shape

```yaml
visible_when:
  any:                                    # logical OR of children
    - role: editor
    - scope: public-scope
  all:                                    # logical AND of children
    - authority_level: hard
    - caller: alice
  not:                                    # NONE of children (de Morgan)
    - role: blocked
```

Multiple top-level operators on the same predicate compose via implicit
AND. Each composite operator's children may be leaf predicates or nested
predicates — composition is freely recursive.

## Leaf predicates

| Leaf | Evaluation |
|---|---|
| `role: <id>` | `<id>` is in caller's role list |
| `authority_level: <level>` | caller's authority is at least `<level>` (rank: uncalibrated < convention < hard) |
| `scope: <scope-id>` | caller's calling scope matches |
| `caller: <author>` | caller's identity matches |
| `data_classification_at_most: <c>` | caller's max-permitted classification matches `<c>` (string equality; ordering plugs in when classification-ordering machinery lands) |

## Block 4.4 implementation gaps (the three placeholders)

1. **Roles placeholder:** `_kernel.role` projection type isn't implemented;
   `caller_roles` is fixture-supplied for tests and defaults to `[]` at
   runtime. Role-based predicates therefore evaluate against an empty
   role list at runtime. Plugs in when role machinery lands.

2. **Classification ordering placeholder:** the
   `data_classification_at_most` leaf does string-equality matching only
   in this binary. Application-defined ordering (e.g., `pii-tokenized` >
   `pii-free`) plugs in when classification-ordering machinery lands.

3. **Runtime CallerContext placeholder:** the read ops build a
   default-empty `CallerContext` at runtime (no caller fields in their
   input schemas — that surface stays minimal until policy machinery
   lands to consume it). Predicates referencing roles / scope / caller
   identity will most often evaluate false at runtime; tests for
   composition semantics bypass the SDK runner and call
   `evaluate_predicate(...)` directly with fixture contexts.

All three placeholders plug in together when the policy / role /
classification-ordering work lands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .errors import SCHEMA_INVALID, KernelError

# Authority hierarchy — must match Block 4.2's `_AUTHORITY_RANK` in
# `src/eightos/sdk/ir_ops.py`. Duplicated here to avoid an SDK ↔ predicates
# import cycle; the values track v1.1 §2.4 / §18.3.
_AUTHORITY_RANK: dict[str, int] = {
    "uncalibrated": 0,
    "convention": 1,
    "hard": 2,
}

_LEAF_NAMES = frozenset({
    "role",
    "authority_level",
    "scope",
    "caller",
    "data_classification_at_most",
})

_COMPOSITE_NAMES = frozenset({"any", "all", "not"})

# Type alias for clarity; the parsed form is the validated raw dict.
ParsedPredicate = dict[str, Any]


@dataclass(frozen=True)
class CallerContext:
    """The caller's invocation context as the predicate evaluator sees it.

    Block 4.4 builds default-empty contexts at runtime (see module-level
    placeholder note 3). Tests construct contexts directly to exercise
    composition semantics.
    """

    caller_id: str | None = None
    caller_scope: str | None = None
    caller_roles: tuple[str, ...] = field(default_factory=tuple)
    caller_authority_level: str = "uncalibrated"
    caller_data_classification_at_most: str | None = None


# ---------------------------------------------------------------------------
# Validation / parsing
# ---------------------------------------------------------------------------


def validate_predicate(raw: Any, *, path: str = "visible_when") -> None:
    """Validate predicate shape; raise SCHEMA_INVALID with a structured path.

    Rules:
    - top-level: dict with at least one of {any, all, not}; no other keys.
    - any/all/not: non-empty array of (leaf | nested predicate).
    - leaf: single-key dict whose key is one of the five permitted names.
    - authority_level leaf: value is one of {uncalibrated, convention, hard}.
    """
    _validate_predicate_node(raw, path=path)


def parse_predicate(raw: Any) -> ParsedPredicate:
    """Validate and return the predicate (the validated raw dict IS the
    parsed form — there is no separate AST). Idempotent."""
    validate_predicate(raw)
    return raw


def _validate_predicate_node(node: Any, *, path: str) -> None:
    if not isinstance(node, dict):
        raise KernelError(
            SCHEMA_INVALID,
            f"predicate at {path} must be an object",
            input_field=path,
            offending_value=node,
        )
    keys = set(node.keys())
    unknown = keys - _COMPOSITE_NAMES
    if unknown:
        raise KernelError(
            SCHEMA_INVALID,
            f"predicate at {path} has unknown composite operator(s) "
            f"{sorted(unknown)!r}; permitted: any, all, not",
            input_field=path,
            offending_value=sorted(unknown),
        )
    if not keys:
        raise KernelError(
            SCHEMA_INVALID,
            f"predicate at {path} is empty; supply at least one of any, "
            "all, not (use null at the field level to indicate no predicate)",
            input_field=path,
        )
    for op in ("any", "all", "not"):
        if op not in node:
            continue
        children = node[op]
        if not isinstance(children, list):
            raise KernelError(
                SCHEMA_INVALID,
                f"predicate at {path}.{op} must be an array",
                input_field=f"{path}.{op}",
                offending_value=children,
            )
        if not children:
            raise KernelError(
                SCHEMA_INVALID,
                f"predicate at {path}.{op} is empty; arrays must have at "
                "least one member (drop the operator if you mean no constraint)",
                input_field=f"{path}.{op}",
            )
        for i, child in enumerate(children):
            child_path = f"{path}.{op}[{i}]"
            _validate_leaf_or_predicate(child, path=child_path)


def _validate_leaf_or_predicate(node: Any, *, path: str) -> None:
    if not isinstance(node, dict):
        raise KernelError(
            SCHEMA_INVALID,
            f"predicate child at {path} must be an object",
            input_field=path,
            offending_value=node,
        )
    keys = set(node.keys())
    # Disambiguate leaf vs nested predicate by which keyset matches.
    if keys & _LEAF_NAMES and keys & _COMPOSITE_NAMES:
        raise KernelError(
            SCHEMA_INVALID,
            f"predicate child at {path} mixes leaf and composite keys "
            f"{sorted(keys)!r}; a child is either a leaf (one of "
            f"{sorted(_LEAF_NAMES)!r}) or a nested predicate (one of "
            f"{sorted(_COMPOSITE_NAMES)!r}), not both",
            input_field=path,
            offending_value=sorted(keys),
        )
    if keys & _LEAF_NAMES:
        _validate_leaf(node, path=path)
    elif keys & _COMPOSITE_NAMES:
        _validate_predicate_node(node, path=path)
    else:
        raise KernelError(
            SCHEMA_INVALID,
            f"predicate child at {path} has unknown keys {sorted(keys)!r}; "
            f"expected a leaf (one of {sorted(_LEAF_NAMES)!r}) or a nested "
            f"predicate (one of {sorted(_COMPOSITE_NAMES)!r})",
            input_field=path,
            offending_value=sorted(keys),
        )


def _validate_leaf(node: dict[str, Any], *, path: str) -> None:
    if len(node) != 1:
        raise KernelError(
            SCHEMA_INVALID,
            f"leaf predicate at {path} must have exactly one key (got "
            f"{sorted(node.keys())!r})",
            input_field=path,
            offending_value=sorted(node.keys()),
        )
    [(name, value)] = node.items()
    if name not in _LEAF_NAMES:
        raise KernelError(
            SCHEMA_INVALID,
            f"leaf predicate at {path} has unknown name {name!r}; "
            f"permitted: {sorted(_LEAF_NAMES)!r}",
            input_field=path,
            offending_value=name,
        )
    if not isinstance(value, str) or not value.strip():
        raise KernelError(
            SCHEMA_INVALID,
            f"leaf predicate at {path}.{name} must be a non-empty string "
            f"(got {value!r})",
            input_field=f"{path}.{name}",
            offending_value=value,
        )
    if name == "authority_level" and value not in _AUTHORITY_RANK:
        raise KernelError(
            SCHEMA_INVALID,
            f"leaf predicate at {path}.authority_level must be one of "
            f"{sorted(_AUTHORITY_RANK)!r} (got {value!r})",
            input_field=f"{path}.authority_level",
            offending_value=value,
        )


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate_predicate(parsed: ParsedPredicate, ctx: CallerContext) -> bool:
    """Evaluate a parsed predicate against a caller context.

    The parsed predicate is assumed valid per `validate_predicate`. Multiple
    top-level operators compose via implicit AND. Composite operators:
    `any` is logical OR; `all` is logical AND; `not` is none-of-array (true
    when every member evaluates false).
    """
    return _eval_node(parsed, ctx)


def _eval_node(node: dict[str, Any], ctx: CallerContext) -> bool:
    keys = set(node.keys())
    if keys & _LEAF_NAMES:
        return _eval_leaf(node, ctx)
    # Composite. Multiple top-level keys AND together.
    results: list[bool] = []
    if "any" in node:
        results.append(any(_eval_child(c, ctx) for c in node["any"]))
    if "all" in node:
        results.append(all(_eval_child(c, ctx) for c in node["all"]))
    if "not" in node:
        results.append(not any(_eval_child(c, ctx) for c in node["not"]))
    return all(results) if results else False


def _eval_child(node: Any, ctx: CallerContext) -> bool:
    return _eval_node(node, ctx)


def _eval_leaf(node: dict[str, Any], ctx: CallerContext) -> bool:
    [(name, value)] = node.items()
    if name == "role":
        return value in ctx.caller_roles
    if name == "authority_level":
        return _AUTHORITY_RANK.get(ctx.caller_authority_level, 0) >= _AUTHORITY_RANK[value]
    if name == "scope":
        return ctx.caller_scope == value
    if name == "caller":
        return ctx.caller_id == value
    if name == "data_classification_at_most":
        # v1.1 §4.4 + Block 4.4 placeholder: string-equality match only.
        # Application-defined ordering (e.g., pii-tokenized > pii-free) plugs
        # in when classification-ordering machinery lands. Until then, this
        # leaf evaluates true only when the caller's max-permitted
        # classification matches the leaf value verbatim.
        return ctx.caller_data_classification_at_most == value
    # `_validate_leaf` has already filtered unknown names; defensive only.
    return False
