"""JSON Schema loading and validation (Draft 2020-12)."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .errors import KERNEL_OUTPUT_INVALID, SCHEMA_INVALID, KernelError

# Schema kind discriminators within filenames.
_INPUT = "input"
_OUTPUT = "output"
_ERROR = "error"


def _schema_filename(op: str, version: int, kind: str) -> str:
    # Op names in the spec are dotted (e.g. kernel.ir.new). Filenames keep them.
    return f"{op}.v{version}.{kind}.json"


@lru_cache(maxsize=None)
def load_schema(op: str, version: int, kind: str) -> dict[str, Any]:
    """Load a schema bundled in the eightos.schemas package."""
    fname = _schema_filename(op, version, kind)
    with resources.files("eightos.schemas").joinpath(fname).open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=None)
def _validator(op: str, version: int, kind: str) -> Draft202012Validator:
    return Draft202012Validator(load_schema(op, version, kind))


def validate_input(op: str, payload: Any, *, version: int = 1) -> None:
    """Validate input payload against `<op>.v<version>.input.json`.

    On failure, raise SCHEMA_INVALID with a dotted path to the offending field.
    """
    try:
        _validator(op, version, _INPUT).validate(payload)
    except ValidationError as ve:
        raise KernelError(
            SCHEMA_INVALID,
            f"input failed schema validation for {op}: {ve.message}",
            input_field=_dotted_path(ve),
            offending_value=ve.instance if ve.path else None,
        ) from ve


def validate_output(op: str, payload: Any, *, version: int = 1) -> None:
    """Validate output envelope against `<op>.v<version>.output.json`.

    Output validation failure is a kernel bug, not user error: KERNEL_OUTPUT_INVALID.
    """
    try:
        _validator(op, version, _OUTPUT).validate(payload)
    except ValidationError as ve:
        raise KernelError(
            KERNEL_OUTPUT_INVALID,
            f"kernel produced an output that fails its own schema for {op}: "
            f"{ve.message}",
            input_field=_dotted_path(ve),
        ) from ve


def all_schema_filenames() -> list[str]:
    """Enumerate every schema file shipped in the package — used by `init`."""
    out: list[str] = []
    for p in resources.files("eightos.schemas").iterdir():
        name = p.name
        if name.endswith(".json"):
            out.append(name)
    out.sort()
    return out


def _dotted_path(ve: ValidationError) -> str | None:
    parts: list[str] = []
    for p in ve.absolute_path:
        parts.append(str(p))
    return ".".join(parts) if parts else None
