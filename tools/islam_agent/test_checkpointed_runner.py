import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_policy import PolicyViolation
from checkpoint import CheckpointError, load_checkpoint
from checkpointed_runner import CheckpointedPlanRunner
from tool_runner import SafeToolRunner


def proposal(steps):
    return {
        "task_id": "agent-003",
        "summary_ar": "خطة قابلة للاستئناف",
        "steps": steps,
        "needs_human_approval": True,
        "claims_to_verify": [],
    }


class CheckpointedRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.checkpoint = self.root / "checkpoint.json"
        self.lock = self.root / "run.lock"
        self.runner = CheckpointedPlanRunner(SafeToolRunner(root=self.root))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_saves_each_step_and_does_not_repeat_completed_plan(self):
        target = self.root / "docs/agent/OLLAMA_LOCAL_AGENT_DESIGN_AR.md"
        target.parent.mkdir(parents=True)
        target.write_text("evidence", encoding="utf-8")
        plan = proposal([{"kind": "inspect", "target": "docs/agent/OLLAMA_LOCAL_AGENT_DESIGN_AR.md"}])
        state, results = self.runner.execute(
            plan, "agent-003", checkpoint_path=self.checkpoint, lock_path=self.lock,
            run_id="run-001", human_approved=True,
        )
        self.assertEqual(state["state"], "completed")
        self.assertEqual(len(results), 1)
        state2, results2 = self.runner.execute(
            plan, "agent-003", checkpoint_path=self.checkpoint, lock_path=self.lock,
            run_id="run-001", human_approved=True,
        )
        self.assertEqual(state2["completed_steps"], state["completed_steps"])
        self.assertEqual(results2, [])

    def test_failed_test_pauses_then_resume_retries_only_failed_step(self):
        plan = proposal([
            {"kind": "run_test", "target": "agent_unit_tests"},
            {"kind": "inspect", "target": "tools/islam_agent/ollama_client.py"},
        ])
        with patch.object(self.runner.runner, "_run_tests", side_effect=[
            {"kind": "run_test", "target": "agent_unit_tests", "status": "failed", "exit_code": 1},
            {"kind": "run_test", "target": "agent_unit_tests", "status": "passed", "exit_code": 0},
        ]) as run_tests, patch.object(self.runner.runner, "_inspect", return_value={
            "kind": "inspect", "target": "tools/islam_agent/ollama_client.py", "status": "completed",
            "content": "read", "truncated": False,
        }) as inspect:
            paused, first_results = self.runner.execute(
                plan, "agent-003", checkpoint_path=self.checkpoint, lock_path=self.lock,
                run_id="run-002", human_approved=True,
            )
            self.assertEqual(paused["state"], "paused")
            self.assertEqual(first_results[0]["status"], "failed")
            resumed, second_results = self.runner.execute(
                plan, "agent-003", checkpoint_path=self.checkpoint, lock_path=self.lock,
                run_id="run-002", human_approved=True,
            )
        self.assertEqual(resumed["state"], "completed")
        self.assertEqual(len(resumed["completed_steps"]), 2)
        self.assertEqual(run_tests.call_count, 2)
        inspect.assert_called_once()
        self.assertEqual(len(second_results), 2)

    def test_requires_human_approval_before_creating_checkpoint(self):
        plan = proposal([{"kind": "run_test", "target": "agent_unit_tests"}])
        with self.assertRaisesRegex(PolicyViolation, "explicit human approval"):
            self.runner.execute(
                plan, "agent-003", checkpoint_path=self.checkpoint, lock_path=self.lock,
                run_id="run-003",
            )
        self.assertFalse(self.checkpoint.exists())

    def test_refuses_checkpoint_from_another_run(self):
        plan = proposal([{"kind": "run_test", "target": "agent_unit_tests"}])
        with patch.object(self.runner.runner, "_run_tests", return_value={
            "kind": "run_test", "target": "agent_unit_tests", "status": "failed", "exit_code": 1,
        }):
            self.runner.execute(
                plan, "agent-003", checkpoint_path=self.checkpoint, lock_path=self.lock,
                run_id="run-004", human_approved=True,
            )
        with self.assertRaisesRegex(CheckpointError, "run_id"):
            self.runner.execute(
                plan, "agent-003", checkpoint_path=self.checkpoint, lock_path=self.lock,
                run_id="run-005", human_approved=True,
            )

    def test_refuses_resume_when_plan_changes(self):
        first_plan = proposal([{"kind": "run_test", "target": "agent_unit_tests"}])
        with patch.object(self.runner.runner, "_run_tests", return_value={
            "kind": "run_test", "target": "agent_unit_tests", "status": "failed", "exit_code": 1,
        }):
            self.runner.execute(
                first_plan, "agent-003", checkpoint_path=self.checkpoint, lock_path=self.lock,
                run_id="run-plan", human_approved=True,
            )
        changed_plan = proposal([{"kind": "inspect", "target": "tools/islam_agent/ollama_client.py"}])
        with self.assertRaisesRegex(CheckpointError, "plan does not match"):
            self.runner.execute(
                changed_plan, "agent-003", checkpoint_path=self.checkpoint, lock_path=self.lock,
                run_id="run-plan", human_approved=True,
            )

    def test_refuses_checkpoint_for_different_task(self):
        plan = proposal([{"kind": "run_test", "target": "agent_unit_tests"}])
        with patch.object(self.runner.runner, "_run_tests", return_value={
            "kind": "run_test", "target": "agent_unit_tests", "status": "failed", "exit_code": 1,
        }):
            self.runner.execute(
                plan, "agent-003", checkpoint_path=self.checkpoint, lock_path=self.lock,
                run_id="run-006", human_approved=True,
            )
        with self.assertRaisesRegex(CheckpointError, "task_id"):
            load_checkpoint(self.checkpoint, expected_task_id="agent-004")


if __name__ == "__main__":
    unittest.main()
