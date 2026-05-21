"""(I, R) markdown frontmatter — parse and serialize.

Format:

    ---
    <yaml frontmatter>
    ---

    # Intention
    <prose>

    # Resolution
    <prose>

The frontmatter is canonical YAML (sorted keys, LF). The body is preserved
verbatim on read; on write the body is constructed from `intention_text` and
optional `resolution_text`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._yaml import dump_yaml, load_yaml


@dataclass
class IRRecord:
    frontmatter: dict[str, Any]
    intention_text: str
    resolution_text: str | None  # None until resolved


def serialize(record: IRRecord) -> str:
    """Render an IRRecord to canonical markdown."""
    fm = dump_yaml(record.frontmatter).rstrip("\n")
    parts = ["---", fm, "---", "", "# Intention", "", record.intention_text.rstrip()]
    if record.resolution_text is not None:
        parts += ["", "# Resolution", "", record.resolution_text.rstrip()]
    return "\n".join(parts) + "\n"


def parse(text: str) -> IRRecord:
    """Parse a markdown (I, R) record into an IRRecord."""
    if not text.startswith("---\n"):
        raise ValueError("(I, R) record must begin with YAML frontmatter delimiter")
    rest = text[4:]
    end = rest.find("\n---\n")
    if end < 0:
        # Allow trailing closing delimiter at EOF
        end = rest.find("\n---")
        if end < 0:
            raise ValueError("(I, R) record missing closing frontmatter delimiter")
        body = ""
        fm_text = rest[:end]
    else:
        fm_text = rest[:end]
        body = rest[end + len("\n---\n") :]
    fm = load_yaml(fm_text) or {}

    intention_text, resolution_text = _split_body(body)
    return IRRecord(
        frontmatter=fm,
        intention_text=intention_text,
        resolution_text=resolution_text,
    )


def parse_file(path: Path) -> IRRecord:
    return parse(path.read_text(encoding="utf-8"))


def _split_body(body: str) -> tuple[str, str | None]:
    """Split the body on `# Intention` and `# Resolution` headers."""
    # Find the headers; tolerant to leading blank lines.
    lines = body.splitlines()
    sections: dict[str, list[str]] = {"intention": [], "resolution": []}
    current: str | None = None
    saw_resolution_header = False
    for ln in lines:
        stripped = ln.strip()
        if stripped == "# Intention":
            current = "intention"
            continue
        if stripped == "# Resolution":
            current = "resolution"
            saw_resolution_header = True
            continue
        if current is not None:
            sections[current].append(ln)
    intention_text = _trim("\n".join(sections["intention"]))
    resolution_text = _trim("\n".join(sections["resolution"])) if saw_resolution_header else None
    return intention_text, resolution_text


def _trim(s: str) -> str:
    return s.strip("\n")
