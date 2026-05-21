"""8os CLI — subprocess wire format per Block 1 §7.1.

Usage:
    8os <op>            # JSON object on stdin → JSON object on stdout
    8os --version       # print kernel ABI semver
    8os --list-ops      # print canonical op names

Exit codes:
    0  on success (envelope on stdout)
    1  on error   (envelope on stderr)

stdout and stderr never interleave — each carries exactly one JSON document
per invocation. Use `--no-stdin` to invoke ops whose input is the empty
object `{}`.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from typing import Any

from . import __version__ as KERNEL_VERSION
from ._envelope import error_from_exception
from .errors import INVALID_STATE, KernelError
from .sdk import OP_HANDLERS, canonicalize
from .sdk._runner import run as run_op


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="8os", add_help=True)
    parser.add_argument("op", nargs="?", help="operation name (e.g. kernel.init)")
    parser.add_argument("--version", action="store_true", help="print kernel version and exit")
    parser.add_argument(
        "--list-ops",
        action="store_true",
        help="print every registered op name and exit",
    )
    parser.add_argument(
        "--no-stdin",
        action="store_true",
        help="treat stdin as the empty object {}",
    )
    args = parser.parse_args(argv)

    if args.version:
        print(KERNEL_VERSION)
        return 0
    if args.list_ops:
        for name in sorted(OP_HANDLERS):
            print(name)
        return 0
    if not args.op:
        parser.print_help(sys.stderr)
        return 1

    payload: Any
    if args.no_stdin:
        payload = {}
    else:
        raw = sys.stdin.read()
        if not raw.strip():
            payload = {}
        else:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as je:
                exc = KernelError(
                    "SCHEMA_INVALID",
                    f"stdin is not valid JSON: {je.msg}",
                    input_field="stdin",
                )
                _emit_error(args.op, exc)
                return 1
    if not isinstance(payload, dict):
        exc = KernelError(
            "SCHEMA_INVALID",
            "input payload must be a JSON object",
            input_field="$",
            offending_value=payload,
        )
        _emit_error(args.op, exc)
        return 1

    try:
        canonical = canonicalize(args.op)
    except KeyError:
        exc = KernelError(
            "SCHEMA_INVALID",
            f"unknown operation {args.op!r}",
            input_field="op",
            offending_value=args.op,
            suggested_action=f"one of {sorted(OP_HANDLERS)}",
        )
        _emit_error(args.op, exc)
        return 1

    try:
        envelope = run_op(canonical, payload)
    except KernelError as ke:
        _emit_error(canonical, ke)
        return 1
    except Exception as exc:
        # Unexpected exceptions surface as INVALID_STATE so callers always get
        # a structured envelope; the traceback goes into context for triage.
        wrapped = KernelError(
            INVALID_STATE,
            f"unexpected kernel exception: {exc.__class__.__name__}: {exc}",
            extra_context={"traceback": traceback.format_exc()},
        )
        _emit_error(canonical, wrapped)
        return 1

    sys.stdout.write(json.dumps(envelope, sort_keys=True, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return 0


def _emit_error(op: str, exc: KernelError) -> None:
    envelope = error_from_exception(op, exc)
    sys.stderr.write(json.dumps(envelope, sort_keys=True, ensure_ascii=False) + "\n")
    sys.stderr.flush()


if __name__ == "__main__":
    sys.exit(main())
