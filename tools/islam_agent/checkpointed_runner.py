"""Checkpoint-aware orchestration for policy-approved, human-approved plans."""
from __future__ import annotations

from pathlib import Path

from agent_policy import PolicyViolation, validate_proposal
from checkpoint import (
    CheckpointError,
    load_checkpoint,
    new_checkpoint,
    record_step,
    save_checkpoint,
    set_checkpoint_state,
)
from tool_runner import SafeToolRunner, ToolExecutionError


class CheckpointedPlanRunner:
    """Execute allowlisted steps one at a time and persist each successful step."""

    def __init__(self, runner: SafeToolRunner | None = None) -> None:
        self.runner = runner or SafeToolRunner()

    @staticmethod
    def _step_id(step: dict, index: int) -> str:
        return f"{index + 1:03d}:{step['kind']}:{step['target']}"

    def execute(
        self,
        proposal: object,
        expected_task_id: str,
        *,
        checkpoint_path: Path,
        lock_path: Path,
        run_id: str,
        human_approved: bool = False,
    ) -> tuple[dict, list[dict]]:
        approved = validate_proposal(proposal, expected_task_id)
        if human_approved is not True:
            raise PolicyViolation("explicit human approval is required before tool execution")
        step_ids = [self._step_id(step, index) for index, step in enumerate(approved["steps"])]
        if len(step_ids) != len(set(step_ids)):
            raise PolicyViolation("plan contains duplicate step identities")

        from checkpoint import exclusive_run_lock

        with exclusive_run_lock(lock_path, run_id):
            path = Path(checkpoint_path)
            if path.exists():
                state = load_checkpoint(path, expected_task_id=expected_task_id)
                if state["run_id"] != run_id:
                    raise CheckpointError("checkpoint run_id does not match requested run")
            else:
                state = new_checkpoint(expected_task_id, run_id)
                save_checkpoint(path, state)

            if state["state"] == "completed":
                return state, []
            if state["state"] == "paused":
                state = set_checkpoint_state(state, "running")
                save_checkpoint(path, state)

            results: list[dict] = []
            for step, step_id in zip(approved["steps"], step_ids):
                if step_id in state["completed_steps"]:
                    continue
                try:
                    if step["kind"] == "inspect":
                        result = self.runner._inspect(step["target"])
                    elif step["kind"] == "run_test":
                        result = self.runner._run_tests(step["target"])
                    else:
                        raise PolicyViolation("step kind is not executable")
                except ToolExecutionError as exc:
                    state["last_result"] = {
                        "step_id": step_id,
                        "status": "error",
                        "error": str(exc)[:500],
                    }
                    state = set_checkpoint_state(state, "paused")
                    save_checkpoint(path, state)
                    raise

                results.append(result)
                if result["kind"] == "run_test" and result["status"] != "passed":
                    state["last_result"] = {
                        "step_id": step_id,
                        "status": "failed",
                        "exit_code": result.get("exit_code"),
                    }
                    state = set_checkpoint_state(state, "paused")
                    save_checkpoint(path, state)
                    return state, results

                state = record_step(
                    state,
                    step_id,
                    {"kind": result["kind"], "target": result["target"], "status": result["status"]},
                )
                save_checkpoint(path, state)

            if len(state["completed_steps"]) == len(step_ids):
                state = set_checkpoint_state(state, "completed")
                save_checkpoint(path, state)
            return state, results
