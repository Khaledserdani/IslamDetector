"""Crash-safe local checkpoints and single-process ownership lock.

Checkpoint data is local JSON only. This module does not contact GitHub,
Ollama, or execute task steps.
"""
from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


SCHEMA_VERSION = 1
VALID_STATES = {"running", "paused", "completed"}
MAX_COMPLETED_STEPS = 100
MAX_STEP_ID_CHARS = 120
MAX_TASK_ID_CHARS = 120


class CheckpointError(ValueError):
    """Raised when checkpoint data or lock ownership is invalid."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validate_checkpoint(data: object, expected_task_id: str | None = None) -> dict:
    if not isinstance(data, dict):
        raise CheckpointError("checkpoint must be a JSON object")
    required = {
        "schema_version",
        "task_id",
        "run_id",
        "state",
        "completed_steps",
        "last_result",
        "updated_at",
    }
    if set(data) != required:
        raise CheckpointError("checkpoint fields do not match the exact schema")
    if data["schema_version"] != SCHEMA_VERSION:
        raise CheckpointError("unsupported checkpoint schema version")
    task_id = data["task_id"]
    run_id = data["run_id"]
    if not isinstance(task_id, str) or not task_id.strip() or len(task_id) > MAX_TASK_ID_CHARS:
        raise CheckpointError("invalid task_id")
    if expected_task_id is not None and task_id != expected_task_id:
        raise CheckpointError("checkpoint task_id does not match requested task")
    if not isinstance(run_id, str) or not run_id.strip() or len(run_id) > MAX_TASK_ID_CHARS:
        raise CheckpointError("invalid run_id")
    if not isinstance(data["state"], str) or data["state"] not in VALID_STATES:
        raise CheckpointError("invalid checkpoint state")
    steps = data["completed_steps"]
    if not isinstance(steps, list) or len(steps) > MAX_COMPLETED_STEPS:
        raise CheckpointError("completed_steps must be a bounded list")
    if any(not isinstance(step, str) or not step.strip() or len(step) > MAX_STEP_ID_CHARS for step in steps):
        raise CheckpointError("completed_steps contains an invalid step identifier")
    if len(steps) != len(set(steps)):
        raise CheckpointError("completed_steps contains duplicate identifiers")
    result = data["last_result"]
    if result is not None and not isinstance(result, dict):
        raise CheckpointError("last_result must be an object or null")
    if not isinstance(data["updated_at"], str) or not data["updated_at"].strip():
        raise CheckpointError("updated_at must be a non-empty string")
    # Round-trip to ensure returned state is detached from caller-owned objects.
    return json.loads(json.dumps(data, ensure_ascii=False))


def new_checkpoint(task_id: str, run_id: str) -> dict:
    return validate_checkpoint({
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "run_id": run_id,
        "state": "running",
        "completed_steps": [],
        "last_result": None,
        "updated_at": _utc_now(),
    })


def load_checkpoint(path: Path, expected_task_id: str | None = None) -> dict:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise CheckpointError("checkpoint does not exist; cannot resume") from None
    except (OSError, json.JSONDecodeError):
        raise CheckpointError("checkpoint is unreadable or invalid JSON") from None
    return validate_checkpoint(raw, expected_task_id=expected_task_id)


def save_checkpoint(path: Path, checkpoint: object) -> dict:
    checked = validate_checkpoint(checkpoint)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=target.name + ".", suffix=".tmp", dir=target.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(checked, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, target)
        # Persist the directory entry where supported.
        if hasattr(os, "O_DIRECTORY"):
            directory_fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return checked


def record_step(checkpoint: object, step_id: str, result: dict | None = None) -> dict:
    checked = validate_checkpoint(checkpoint)
    if checked["state"] != "running":
        raise CheckpointError("only a running checkpoint can record steps")
    if not isinstance(step_id, str) or not step_id.strip() or len(step_id) > MAX_STEP_ID_CHARS:
        raise CheckpointError("invalid step_id")
    if step_id in checked["completed_steps"]:
        raise CheckpointError("step is already recorded as completed")
    if len(checked["completed_steps"]) >= MAX_COMPLETED_STEPS:
        raise CheckpointError("completed step limit reached")
    if result is not None and not isinstance(result, dict):
        raise CheckpointError("result must be an object or null")
    checked["completed_steps"].append(step_id)
    checked["last_result"] = result
    checked["updated_at"] = _utc_now()
    return checked


def set_checkpoint_state(checkpoint: object, state: str) -> dict:
    checked = validate_checkpoint(checkpoint)
    if not isinstance(state, str) or state not in VALID_STATES:
        raise CheckpointError("invalid checkpoint state")
    allowed = {
        "running": {"paused", "completed"},
        "paused": {"running"},
        "completed": set(),
    }
    if state not in allowed[checked["state"]]:
        raise CheckpointError("checkpoint state transition is not allowed")
    checked["state"] = state
    checked["updated_at"] = _utc_now()
    return checked


@contextmanager
def exclusive_run_lock(lock_path: Path, run_id: str) -> Iterator[None]:
    """Acquire an exclusive lock; never auto-break a possibly live/stale lock."""
    if not isinstance(run_id, str) or not run_id.strip() or len(run_id) > MAX_TASK_ID_CHARS:
        raise CheckpointError("invalid run_id")
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"run_id": run_id, "pid": os.getpid(), "created_at": _utc_now()})
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise CheckpointError("another run owns the lock; inspect it before recovery") from None
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        yield
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
