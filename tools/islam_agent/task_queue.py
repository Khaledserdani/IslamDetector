#!/usr/bin/env python3
"""Local, dependency-free task queue for ISLAM FREE AUTONOMOUS LAB.

The queue edits only the project memory JSON. It never calls GitHub or a model.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MEMORY = ROOT / "docs" / "agent" / "agent_memory.json"
VALID_STATUSES = {"pending", "in_progress", "blocked", "completed"}
ALLOWED_TRANSITIONS = {
    "pending": {"in_progress"},
    "in_progress": {"pending", "blocked", "completed"},
    "blocked": {"pending"},
    "completed": set(),
}


def load_memory(path: Path) -> dict:
    memory = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(memory, dict) or memory.get("schema_version") != 1:
        raise ValueError("Unsupported or invalid project memory schema.")
    tasks = memory.get("next_tasks")
    if not isinstance(tasks, list):
        raise ValueError("next_tasks must be a list.")
    ids: list[str] = []
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise ValueError(f"Task at index {index} must be an object.")
        if not all(key in task for key in ("id", "title", "status", "acceptance")):
            raise ValueError(f"Task is missing required fields at index {index}.")
        if not isinstance(task["id"], str) or not task["id"].strip():
            raise ValueError(f"Task id at index {index} must be a non-empty string.")
        if not isinstance(task["title"], str) or not task["title"].strip():
            raise ValueError(f"Task title at index {index} must be a non-empty string.")
        if not isinstance(task["acceptance"], str) or not task["acceptance"].strip():
            raise ValueError(f"Task acceptance at index {index} must be a non-empty string.")
        if task["status"] not in VALID_STATUSES:
            raise ValueError(f"Invalid status for task {task['id']}: {task['status']}")
        ids.append(task["id"])
    if len(ids) != len(set(ids)):
        raise ValueError("Every task must have a unique id.")
    return memory


def write_memory_atomic(path: Path, memory: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(memory, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def transition(memory: dict, task_id: str, new_status: str, note: str = "") -> dict:
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Unknown status: {new_status}")
    matches = [task for task in memory["next_tasks"] if task["id"] == task_id]
    if len(matches) != 1:
        raise ValueError(f"Expected one task with id {task_id!r}; found {len(matches)}.")
    task = matches[0]
    old_status = task["status"]
    if new_status not in ALLOWED_TRANSITIONS[old_status]:
        raise ValueError(f"Transition not allowed: {old_status} -> {new_status}")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    task["status"] = new_status
    task["updated_at"] = now
    if note:
        task["last_note"] = note
    events = memory.setdefault("task_events", [])
    if not isinstance(events, list):
        raise ValueError("task_events must be a list.")
    events.append({"at": now, "task_id": task_id, "from": old_status, "to": new_status, "note": note})
    memory["updated_at"] = now[:10]
    return task


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memory", type=Path, default=DEFAULT_MEMORY)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="show task queue")
    next_parser = subparsers.add_parser("next", help="show the next pending task")
    change = subparsers.add_parser("set", help="safely change one task status")
    change.add_argument("task_id")
    change.add_argument("status", choices=sorted(VALID_STATUSES))
    change.add_argument("--note", default="")
    args = parser.parse_args()
    try:
        memory = load_memory(args.memory)
        if args.command == "list":
            for task in memory["next_tasks"]:
                print(f"{task['id']} [{task['status']}] {task['title']}")
            return 0
        if args.command == "next":
            task = next((item for item in memory["next_tasks"] if item["status"] == "pending"), None)
            if task is None:
                print("No pending tasks.")
            else:
                print(json.dumps(task, ensure_ascii=False, indent=2))
            return 0
        task = transition(memory, args.task_id, args.status, args.note)
        write_memory_atomic(args.memory, memory)
        print(f"Updated {task['id']}: {task['status']}")
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())