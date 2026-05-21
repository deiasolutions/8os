"""Atomic write/rename helpers.

Strategy: write each file to a sibling temp file in the destination directory,
then `os.replace` to the final name (POSIX-atomic on the same filesystem).
For multi-file mutations, callers stage every output under
`.8os/.staging/<op-id>/` first (full validation), then promote each staged
file with `os.replace`. This is best-effort multi-file atomicity; a crash
between two replaces leaves a partial state recoverable by `8os reindex`.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Iterable

from ._paths import ensure_dir


def atomic_write_text(path: Path, content: str) -> None:
    """Write text to `path` via a same-directory temp file + os.replace."""
    ensure_dir(path.parent)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    os.replace(tmp, path)


def atomic_write_bytes(path: Path, content: bytes) -> None:
    ensure_dir(path.parent)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as f:
        f.write(content)
    os.replace(tmp, path)


def append_jsonl_line(path: Path, obj: dict) -> None:
    """Append a single canonical-JSON line to `path` (creates if missing).

    JSONL lines are individually atomic at the OS level for small payloads;
    we rely on the OS append guarantee for single-writer correctness.
    """
    ensure_dir(path.parent)
    line = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")


def remove_dir_if_empty(p: Path) -> None:
    try:
        p.rmdir()
    except OSError:
        pass


def cleanup_staging(staging_root: Path) -> None:
    """Remove a staging tree, ignoring errors. Called on op success or failure."""
    if staging_root.exists():
        shutil.rmtree(staging_root, ignore_errors=True)


class StagedFile:
    """A planned (final_path, content) pair to commit atomically."""

    __slots__ = ("final_path", "content_text", "content_bytes")

    def __init__(
        self,
        final_path: Path,
        content_text: str | None = None,
        content_bytes: bytes | None = None,
    ) -> None:
        if (content_text is None) == (content_bytes is None):
            raise ValueError("exactly one of content_text/content_bytes required")
        self.final_path = final_path
        self.content_text = content_text
        self.content_bytes = content_bytes


def commit_staged(staged: Iterable[StagedFile]) -> None:
    """Write every staged file with atomic_write semantics.

    The order is: ensure parent dirs first, then write all temp files, then
    rename them all in. A crash between two renames leaves partial state
    that `8os reindex` can recover from.
    """
    items = list(staged)
    # Phase 1: write all temps next to their final destinations.
    tmps: list[tuple[Path, Path]] = []
    try:
        for s in items:
            ensure_dir(s.final_path.parent)
            tmp = s.final_path.with_name(s.final_path.name + ".tmp")
            if s.content_text is not None:
                with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                    f.write(s.content_text)
            else:
                with open(tmp, "wb") as f:
                    f.write(s.content_bytes or b"")
            tmps.append((tmp, s.final_path))
    except Exception:
        # Tear down any temps we managed to create.
        for tmp, _ in tmps:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        raise

    # Phase 2: rename each temp to its final destination.
    for tmp, final in tmps:
        os.replace(tmp, final)
