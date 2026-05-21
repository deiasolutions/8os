"""SCAN dogfood orchestration — Block 3 Piece 5.

Runs the SCAN-pillar daily briefing flow end-to-end through the
factory. Authors nothing new; expects the workload root, scope, four
resolver records, the decomposer, the Anthropic bridge, and the
standing authorization to all already be in the live repo.

Usage:
    uv run python scripts/run-scan-dogfood.py [--max-ticks N]

Without OAuth the Anthropic bridge falls back to stub responses; the
decomposer's parser will reject those (stub text is not JSON), so a
real run requires Claude Code installed and authenticated on this
machine.

Side effects in the repo (committed by this run):
- ir/dogfood-scan/scan-daily-briefing/_node.md (root expanded)
- ir/dogfood-scan/scan-daily-briefing/scan-*.md (4 children)
- .8os/dogfood-scan/artifacts/<brief-id>.md (the briefing artifact)
- .8os/events/log/<date>.jsonl (every dispatch + crossing)
- Indexes refreshed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from eightos.factory import tick as factory_tick
from eightos.sdk._runner import run as run_op


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the SCAN dogfood end-to-end.")
    parser.add_argument(
        "--max-ticks",
        type=int,
        default=10,
        help="Safety cap on tick count (default: 10).",
    )
    parser.add_argument(
        "--scope",
        default="dogfood-scan",
        help="Scope to walk (default: dogfood-scan).",
    )
    args = parser.parse_args(argv)

    repo = Path.cwd()
    print(f"Running SCAN dogfood in {repo}\n")

    # Refresh indexes so the workload root / resolvers / scope are visible.
    print("Reindexing...")
    run_op("kernel.reindex", {"mode": "full"})

    print(f"Ticking scope {args.scope!r} until no leaves remain "
          f"(max {args.max_ticks} ticks)\n")
    tick_count = 0
    total_cost_usd = 0.0
    total_clock_ms = 0.0

    failures = 0
    while tick_count < args.max_ticks:
        tick_count += 1
        summary = factory_tick(repo, args.scope)
        leaves = summary["leaves_found"]
        print(f"--- Tick {tick_count}: leaves={leaves}")
        if leaves == 0:
            print("    (no leaves; workload complete)")
            break
        # Detect dispatch failures (e.g., rate-limit) and abort rather than
        # cycling through retries which compound the rate-limit window.
        if any(not d["ok"] for d in summary["dispatched"]):
            failures += 1
        else:
            failures = 0
        for d in summary["dispatched"]:
            iid = d["intention_id"]
            rid = d.get("resolver_id")
            ok = d["ok"]
            if d.get("materialized_children") is not None:
                tag = f"materialized {d['materialized_children']} children"
            elif ok:
                tag = "resolved"
            else:
                tag = f"FAILED: {d.get('error')}"
            print(f"    {iid} -> {rid} :: {tag}")
            cost = _last_event_cost(repo, iid)
            if cost:
                total_cost_usd += cost.get("coin_usd") or 0.0
                total_clock_ms += cost.get("clock_ms") or 0.0
                print(
                    f"        cost: clock_ms={cost.get('clock_ms')}, "
                    f"coin_usd={cost.get('coin_usd')}, "
                    f"carbon_g={cost.get('carbon_g')}"
                )
        if failures:
            print(
                f"\nDispatch failed on tick {tick_count}; aborting to avoid "
                f"rate-limit / wasted retries. Investigate then re-run."
            )
            return 1

    print()
    print(f"Total ticks: {tick_count}")
    print(f"Total clock_ms: {total_clock_ms:.0f}")
    print(f"Total coin_usd: ${total_cost_usd:.4f}")

    # Locate the briefing artifact.
    artifacts_dir = repo / ".8os" / "dogfood-scan" / "artifacts"
    if artifacts_dir.exists():
        briefing_files = sorted(artifacts_dir.glob("*.md"))
        if briefing_files:
            print()
            print("=" * 70)
            print(f"Briefing artifact: {briefing_files[-1].relative_to(repo)}")
            print("=" * 70)
            print(briefing_files[-1].read_text())
    return 0


def _last_event_cost(repo: Path, intention_id: str) -> dict[str, Any] | None:
    """Look up the latest event for this (I, R) by scanning the JSONL stream."""
    from eightos._events import iter_events
    last_cost: dict[str, Any] | None = None
    for _path, _line, ev in iter_events(repo):
        if ev.get("ir_node_id") == intention_id:
            cost = ev.get("cost_actual") or {}
            if isinstance(cost, dict) and cost:
                last_cost = cost
    return last_cost


if __name__ == "__main__":
    sys.exit(main())
