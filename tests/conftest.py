"""Shared fixtures for the 8os test suite.

Each test gets a fresh empty repo via `repo` and chdirs into it so kernel
operations resolve `find_repo_root()` to the test's tmp dir. The
`run_op` fixture invokes the SDK runner in-process (fast, full coverage of
schemas + handlers); `cli_run` spawns the actual `8os` CLI subprocess to
exercise the wire format end-to-end.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import pytest


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty directory that becomes the cwd; init writes its `.8os/` here."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def run_op() -> Callable[[str, dict[str, Any]], dict[str, Any]]:
    """Run an op in-process; raises KernelError on failure."""
    from eightos.sdk._runner import run

    return run


@pytest.fixture
def cli_run(repo: Path) -> Callable[[str, dict[str, Any] | None], subprocess.CompletedProcess]:
    """Spawn `8os <op>` as a subprocess in `repo`. Returns CompletedProcess.

    Uses the project venv's interpreter so editable `eightos` is importable
    without going through `uv run` (faster, fewer moving parts).
    """

    def _run(op: str, payload: dict[str, Any] | None = None) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.setdefault("PYTHONUNBUFFERED", "1")
        cmd = [sys.executable, "-m", "eightos.cli", op]
        stdin_bytes = json.dumps(payload or {}).encode("utf-8")
        return subprocess.run(
            cmd,
            input=stdin_bytes,
            capture_output=True,
            cwd=str(repo),
            env=env,
            timeout=30,
        )

    return _run


@pytest.fixture
def initialized(repo: Path, run_op) -> Path:
    """A repo with a fresh kernel initialized."""
    from eightos import __version__ as KERNEL_VERSION

    run_op(
        "kernel.init",
        {
            "project_name": "test-project",
            "primary_scope_id": "test-scope",
            "primary_operator_id": "test-author",
            "kernel_version": KERNEL_VERSION,
        },
    )
    return repo
