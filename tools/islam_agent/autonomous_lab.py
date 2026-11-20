"""Automatic execution and evidence logging for computational-only lab proposals.

This lane accepts only the fixed DC, RLC, and linear-AC simulators. It cannot
write source files, run shell commands, access GitHub, or control physical hardware.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from tool_runner import SafeToolRunner

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_DIR = ROOT / "artifacts" / "agent" / "lab_runs"
LAB_KINDS = {"simulate_circuit", "simulate_rlc", "simulate_ac_network"}
MAX_REPORT_BYTES = 1_000_000


class AutonomousLabError(RuntimeError):
    """Raised when an autonomous lab record cannot be safely created."""


def _compact_result(value):
    """Keep large transient traces useful without producing unbounded reports."""
    if isinstance(value, dict):
        return {key: _compact_result(item) for key, item in value.items()}
    if isinstance(value, list):
        if len(value) > 1000 and all(
            isinstance(item, (int, float)) and not isinstance(item, bool) for item in value
        ):
            return {
                "sample_count": len(value),
                "first": value[0],
                "last": value[-1],
                "minimum": min(value),
                "maximum": max(value),
                "note": "تم تلخيص السلسلة الطويلة؛ القيم الوسيطة لم تُحفظ في هذا التقرير.",
            }
        return [_compact_result(item) for item in value]
    return value


def _write_new_json(path: Path, payload: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    if len(encoded) > MAX_REPORT_BYTES:
        raise AutonomousLabError("lab report exceeds the 1 MB limit")
    fd, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary_name, path)
        os.unlink(temporary_name)
    except FileExistsError:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise AutonomousLabError("lab report already exists; refusing to overwrite evidence") from None
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def run_autonomous_lab_proposal(
    record: object,
    *,
    report_dir: Path = DEFAULT_REPORT_DIR,
    runner: SafeToolRunner | None = None,
    clock: Callable = lambda: datetime.now(timezone.utc),
) -> dict:
    """Run a proposal only when every step is a validated non-actuating lab simulation."""
    if not isinstance(record, dict) or set(record) != {
        "schema_version", "created_at_utc", "task", "model", "proposal",
        "awaiting_human_approval", "executed",
    }:
        raise AutonomousLabError("proposal record does not match the exact stored schema")
    if record["schema_version"] != 1 or record["awaiting_human_approval"] is not True or record["executed"] is not False:
        raise AutonomousLabError("only a fresh, pending, unexecuted proposal can enter the lab lane")
    task = record["task"]
    if not isinstance(task, dict) or not isinstance(task.get("id"), str) or not task["id"]:
        raise AutonomousLabError("proposal task identity is invalid")
    proposal = record["proposal"]
    if not isinstance(proposal, dict) or not isinstance(proposal.get("steps"), list) or not proposal["steps"]:
        raise AutonomousLabError("proposal contains no executable lab steps")
    if any(not isinstance(step, dict) or step.get("kind") not in LAB_KINDS for step in proposal["steps"]):
        return {"status": "needs_human_review", "reason": "proposal includes a non-laboratory operation"}

    canonical = json.dumps(
        {"task_id": task["id"], "proposal": proposal},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    output_dir = Path(report_dir)
    for existing in output_dir.glob(f"*-{digest[:12]}.json"):
        try:
            previous = json.loads(existing.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if isinstance(previous, dict) and previous.get("run_id") == digest[:16]:
            return {
                "status": "duplicate",
                "run_id": digest[:16],
                "report_path": str(existing),
                "verified_numerically": previous.get("verified_numerically") is True,
                "error": "لم تُعد التجربة نفسها؛ استُخدم سجلها السابق.",
            }

    executor = runner or SafeToolRunner()
    # The dedicated runner method revalidates every input and rejects all non-lab steps.
    results = []
    error = None
    try:
        results = executor.execute_autonomous_lab_plan(proposal, task["id"])
        for item in results:
            result = item.get("result")
            if not isinstance(result, dict) or result.get("verified_numerically") is not True:
                error = "المختبر لم يثبت تحققاً عددياً ناجحاً لكل خطوة."
                break
    except Exception as exc:
        error = f"{type(exc).__name__}: {str(exc)[:500]}"

    now = clock().astimezone(timezone.utc)
    report = {
        "schema_version": 1,
        "run_id": digest[:16],
        "created_at_utc": now.isoformat(timespec="seconds"),
        "task": {"id": task["id"], "title": str(task.get("title", ""))[:500]},
        "model": str(record["model"])[:128],
        "proposal_summary_ar": str(proposal.get("summary_ar", ""))[:500],
        "proposal": proposal,
        "execution_scope": "computational laboratory simulation only; no source writes, shell, network, GitHub, or physical hardware",
        "status": "verified" if error is None else "failed",
        "verified_numerically": error is None,
        "results": _compact_result(results),
        "error": error,
        "human_review_required_for_project_changes": True,
    }
    stamp = now.strftime("%Y%m%dT%H%M%S%fZ")
    destination = Path(report_dir) / f"{stamp}-{digest[:12]}.json"
    _write_new_json(destination, report)
    return {
        "status": report["status"],
        "run_id": report["run_id"],
        "report_path": str(destination),
        "verified_numerically": report["verified_numerically"],
        "error": error,
    }
