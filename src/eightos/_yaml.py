"""Canonical YAML serialization.

Block 1 §Conventions: sorted keys, LF line endings, no trailing whitespace.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def dump_yaml(data: Any) -> str:
    """Canonical YAML dump: sorted keys, LF newlines, no trailing whitespace."""
    text = yaml.safe_dump(
        data,
        sort_keys=True,
        default_flow_style=False,
        allow_unicode=True,
        width=10**9,  # never wrap; index files are machine-read
    )
    # safe_dump always uses '\n', but normalize defensively and strip trailing
    # whitespace per line to satisfy the canonical form.
    lines = [ln.rstrip() for ln in text.splitlines()]
    return "\n".join(lines) + "\n"


def load_yaml(text: str) -> Any:
    return yaml.safe_load(text)


def load_yaml_file(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))
