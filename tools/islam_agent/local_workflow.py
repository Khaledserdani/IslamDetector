"""Explicit-approval bridge between the local proposal model and safe runner."""
from __future__ import annotations

from pathlib import Path

from agent_policy import PolicyViolation, validate_proposal
from checkpointed_runner import CheckpointedPlanRunner


class LocalAgentWorkflow:
    """Keep proposal generation and execution separate by an explicit approval gate."""

    def __init__(self, proposal_agent, plan_runner: CheckpointedPlanRunner | None = None) -> None:
        if not callable(getattr(proposal_agent, "propose", None)):
            raise TypeError("proposal_agent must provide propose(task, context)")
        self.proposal_agent = proposal_agent
        self.plan_runner = plan_runner or CheckpointedPlanRunner()

    def propose(self, task: object, context: object = None) -> dict:
        """Return a validated proposal only; this method never executes tools."""
        result = self.proposal_agent.propose(task, context)
        if not isinstance(result, dict) or set(result) != {
            "model", "proposal", "awaiting_human_approval", "executed"
        }:
            raise PolicyViolation("proposal agent returned an unexpected result schema")
        if result["awaiting_human_approval"] is not True or result["executed"] is not False:
            raise PolicyViolation("proposal agent must return an unexecuted plan awaiting approval")
        task_id = task.get("id") if isinstance(task, dict) else None
        approved = validate_proposal(result["proposal"], task_id)
        return {
            "model": result["model"],
            "proposal": approved,
            "awaiting_human_approval": True,
            "executed": False,
        }

    def approve_and_execute(
        self,
        proposal_result: object,
        expected_task_id: str,
        *,
        human_approved: bool = False,
        checkpoint_path: Path,
        lock_path: Path,
        run_id: str,
    ) -> tuple[dict, list[dict]]:
        """Execute only after the caller explicitly supplies human_approved=True."""
        if human_approved is not True:
            raise PolicyViolation("explicit human approval is required before execution")
        if not isinstance(proposal_result, dict) or set(proposal_result) != {
            "model", "proposal", "awaiting_human_approval", "executed"
        }:
            raise PolicyViolation("approval must reference a valid pending proposal result")
        if proposal_result["awaiting_human_approval"] is not True or proposal_result["executed"] is not False:
            raise PolicyViolation("proposal is not in a pending, unexecuted state")
        proposal = validate_proposal(proposal_result["proposal"], expected_task_id)
        return self.plan_runner.execute(
            proposal,
            expected_task_id,
            checkpoint_path=checkpoint_path,
            lock_path=lock_path,
            run_id=run_id,
            human_approved=True,
        )
