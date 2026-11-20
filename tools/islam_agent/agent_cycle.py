#!/usr/bin/env python3
"""Repeatable, bounded local audit cycle for the ISLAM assistant.

Each cycle selects the next unfinished task for visibility, runs the deterministic
project audit, and appends a durable JSONL event. It never edits project memory,
source files, Git refs, or pull requests. Ollama is intentionally not required.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from task_queue import load_memory


ROOT = Path(__file__).resolve().parents[2]
AUDIT_SCRIPT = ROOT / "tools" / "islam_agent" / "audit.py"
DEFAULT_LOG = ROOT / "artifacts" / "agent" / "cycle_log.jsonl"
DEFAULT_REPORT_DIR = ROOT / "artifacts" / "agent" / "reports"
AUDIT_TIMEOUT_SECONDS = 600


def select_next_task(memory: dict) -> dict | None:
    """Prefer resuming in-progress work, then take the first pending task."""
    tasks = memory.get("next_tasks")
    if not isinstance(tasks, list):
        raise ValueError("memory next_tasks must be a list")
    for status in ("in_progress", "pending"):
        for task in tasks:
            if isinstance(task, dict) and task.get("status") == status:
                return {
                    "id": task.get("id"),
                    "title": task.get("title"),
                    "status": status,
                }
    return None


def _append_event(path: Path, event: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def run_cycle(
    root: Path = ROOT,
    *,
    log_path: Path | None = None,
    report_dir: Path | None = None,
    runner: Callable = subprocess.run,
    clock: Callable = lambda: datetime.now(timezone.utc),
) -> dict:
    """Run one audit and persist its result; errors are recorded, not hidden."""
    root = Path(root).resolve()
    memory_path = root / "docs" / "agent" / "agent_memory.json"
    log_path = Path(log_path) if log_path is not None else root / "artifacts" / "agent" / "cycle_log.jsonl"
    report_dir = Path(report_dir) if report_dir is not None else root / "artifacts" / "agent" / "reports"
    now = clock().astimezone(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%S%fZ")
    report_path = report_dir / f"audit-{stamp}.md"
    event = {
        "timestamp_utc": now.isoformat(timespec="seconds"),
        "task": None,
        "audit_status": "error",
        "exit_code": None,
        "report_path": str(report_path),
        "error": None,
    }
    try:
        memory = load_memory(memory_path)
        task = select_next_task(memory)
        event["task"] = task
        report_path.parent.mkdir(parents=True, exist_ok=True)
        result = runner(
            [sys.executable, str(root / "tools" / "islam_agent" / "audit.py"), "--report", str(report_path)],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=AUDIT_TIMEOUT_SECONDS,
            check=False,
        )
        event["exit_code"] = int(result.returncode)
        event["audit_status"] = "passed" if result.returncode == 0 else "failed"
        output = (result.stdout or "")[-4000:]
        event["output_tail"] = output
    except subprocess.TimeoutExpired:
        event["error"] = f"audit timed out after {AUDIT_TIMEOUT_SECONDS} seconds"
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        event["error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
    _append_event(log_path, event)
    return event


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", action="store_true", help="repeat until interrupted")
    parser.add_argument("--interval-seconds", type=int, default=21600,
                        help="delay between cycles in repeat mode (minimum 300)")
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--reports", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()
    if args.repeat and args.interval_seconds < 300:
        parser.error("--interval-seconds must be at least 300 in repeat mode")
    while True:
        event = run_cycle(ROOT, log_path=args.log, report_dir=args.reports)
        print(json.dumps(event, ensure_ascii=False, sort_keys=True), flush=True)
        if not args.repeat:
            return 0 if event["audit_status"] == "passed" else 1
        try:
            time.sleep(args.interval_seconds)
        except KeyboardInterrupt:
            print("ISLAM agent cycle stopped by user.", flush=True)
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
