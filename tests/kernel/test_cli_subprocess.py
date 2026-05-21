"""End-to-end tests of the subprocess wire format (Block 1 §7.1).

These exercise the actual `8os` CLI: stdin JSON in, stdout/stderr JSON out,
exit code 0/1. Anything that passes the in-process suite but fails here
indicates a wire-format bug, not a kernel-logic bug.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from eightos import __version__ as KERNEL_VERSION


VALID_INIT = {
    "project_name": "subproc-project",
    "primary_scope_id": "subproc-scope",
    "primary_operator_id": "subproc-author",
    "kernel_version": KERNEL_VERSION,
}


def _envelope(out: bytes) -> dict:
    return json.loads(out.decode("utf-8"))


def test_cli_init_writes_success_to_stdout(repo: Path, cli_run):
    proc = cli_run("kernel.init", VALID_INIT)
    assert proc.returncode == 0, proc.stderr
    assert proc.stderr == b""
    env = _envelope(proc.stdout)
    assert env["status"] == "ok"
    assert env["op"] == "kernel.init"
    assert env["data"]["bootstrap_ir_id"] == "000-bootstrap"


def test_cli_short_alias_works(repo: Path, cli_run):
    """`8os init` is the short form of `8os kernel.init`."""
    proc = cli_run("init", VALID_INIT)
    assert proc.returncode == 0, proc.stderr
    env = _envelope(proc.stdout)
    assert env["op"] == "kernel.init"


def test_cli_unknown_op_writes_error_to_stderr(repo: Path, cli_run):
    proc = cli_run("kernel.does-not-exist")
    assert proc.returncode == 1
    assert proc.stdout == b""
    env = _envelope(proc.stderr)
    assert env["status"] == "error"
    assert env["code"] == "SCHEMA_INVALID"


def test_cli_init_at_matching_version_is_noop(repo: Path, cli_run):
    """v1.0 §7.2 wire-format check: a second init at matching version
    produces a success envelope on stdout with mode=noop, exit 0, and an
    empty stderr — not an ALREADY_EXISTS error. (Old behavior was the bug
    that Block 2.9's Task 0a fixed; this test now encodes the correct
    idempotency contract end-to-end.)"""
    cli_run("kernel.init", VALID_INIT)
    proc = cli_run("kernel.init", VALID_INIT)
    assert proc.returncode == 0, proc.stderr
    assert proc.stderr == b""
    env = _envelope(proc.stdout)
    assert env["status"] == "ok"
    assert env["data"]["mode"] == "noop"
    assert env["event_id"] is None


def test_cli_invalid_json_stdin(repo: Path, cli_run):
    """Garbled stdin produces SCHEMA_INVALID on stderr, not a stack trace."""
    import os
    import sys
    proc = subprocess.run(
        [sys.executable, "-m", "eightos.cli", "kernel.init"],
        input=b"{not valid json",
        capture_output=True,
        cwd=str(repo),
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
        timeout=15,
    )
    assert proc.returncode == 1
    env = _envelope(proc.stderr)
    assert env["code"] == "SCHEMA_INVALID"
