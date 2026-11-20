#!/usr/bin/env python3
"""Human review gate for one locally saved ISLAM proposal."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from agent_policy import PolicyViolation, validate_proposal
from local_workflow import LocalAgentWorkflow
from checkpointed_runner import CheckpointedPlanRunner
from tool_runner import SafeToolRunner


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PENDING = ROOT / "artifacts" / "agent" / "pending_proposal.json"
DEFAULT_STATE = ROOT / "artifacts" / "agent" / "review"


class _NoProposalAgent:
    def propose(self, task, context=None):
        raise RuntimeError("review mode never generates proposals")


def approval_phrase(task_id: str) -> str:
    return f"أوافق على تنفيذ الاقتراح {task_id}"


def review_pending(
    pending_path: Path,
    *,
    approval_text: str,
    workflow: LocalAgentWorkflow | None = None,
    state_dir: Path = DEFAULT_STATE,
) -> tuple[dict, list[dict]]:
    """Validate a saved proposal and execute only after exact typed approval."""
    path = Path(pending_path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PolicyViolation(f"cannot read pending proposal: {exc}") from None
    if len(raw) > 16 * 1024:
        raise PolicyViolation("pending proposal exceeds the 16 KiB limit")
    try:
        record = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise PolicyViolation("pending proposal is not valid UTF-8 JSON") from None

    required = {
        "schema_version", "created_at_utc", "task", "model", "proposal",
        "awaiting_human_approval", "executed",
    }
    if not isinstance(record, dict) or set(record) != required:
        raise PolicyViolation("pending record does not match the exact saved schema")
    if record["schema_version"] != 1:
        raise PolicyViolation("unsupported pending proposal schema version")
    task = record["task"]
    if not isinstance(task, dict) or set(task) != {"id", "title", "acceptance", "status"}:
        raise PolicyViolation("pending task metadata is invalid")
    task_id = task["id"]
    if not isinstance(task_id, str) or not task_id.strip():
        raise PolicyViolation("pending task id is invalid")
    if any(not isinstance(task[k], str) or not task[k].strip() for k in ("title", "acceptance", "status")):
        raise PolicyViolation("pending task metadata contains invalid text")
    if task["status"] not in {"pending", "in_progress"}:
        raise PolicyViolation("task is not in a runnable state")
    if not isinstance(record["model"], str) or not record["model"].strip() or len(record["model"]) > 128:
        raise PolicyViolation("pending model name is invalid")
    if record["awaiting_human_approval"] is not True or record["executed"] is not False:
        raise PolicyViolation("proposal is not pending and unexecuted")

    proposal = validate_proposal(record["proposal"], task_id)
    if approval_text != approval_phrase(task_id):
        raise PolicyViolation("typed approval phrase did not match exactly")

    # Stable identity makes interrupted executions resumable without changing the plan.
    canonical = json.dumps(
        {"task_id": task_id, "proposal": proposal},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    safe_state = Path(state_dir)
    checkpoint = safe_state / f"{digest}.checkpoint.json"
    lock = safe_state / f"{digest}.lock"
    active_workflow = workflow or LocalAgentWorkflow(
        _NoProposalAgent(), CheckpointedPlanRunner(SafeToolRunner())
    )
    return active_workflow.approve_and_execute(
        {
            "model": record["model"],
            "proposal": proposal,
            "awaiting_human_approval": True,
            "executed": False,
        },
        task_id,
        human_approved=True,
        checkpoint_path=checkpoint,
        lock_path=lock,
        run_id=digest[:32],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pending", type=Path, default=DEFAULT_PENDING)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
    args = parser.parse_args()
    try:
        record = json.loads(args.pending.read_text(encoding="utf-8"))
        task_id = record.get("task", {}).get("id") if isinstance(record, dict) else None
        if not isinstance(task_id, str) or not task_id.strip():
            raise PolicyViolation("pending task id is missing")
        print(json.dumps({
            "task_id": task_id,
            "task_title": record["task"].get("title"),
            "model": record.get("model"),
            "summary_ar": record.get("proposal", {}).get("summary_ar"),
            "steps": record.get("proposal", {}).get("steps"),
            "claims_to_verify": record.get("proposal", {}).get("claims_to_verify"),
            "awaiting_human_approval": record.get("awaiting_human_approval"),
            "executed": record.get("executed"),
        }, ensure_ascii=False, indent=2))
        print("للتنفيذ اكتب العبارة التالية حرفياً؛ أي إدخال آخر يلغي العملية:")
        phrase = input(approval_phrase(task_id) + "\n> ")
        state, results = review_pending(
            args.pending, approval_text=phrase, state_dir=args.state_dir
        )
        print(json.dumps({
            "state": state.get("state"),
            "completed_steps": state.get("completed_steps"),
            "results": results,
        }, ensure_ascii=False, indent=2))
        return 0 if state.get("state") == "completed" else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)[:500]}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
