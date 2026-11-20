import json
import tempfile
import unittest
from pathlib import Path

from agent_policy import PolicyViolation
from checkpointed_runner import CheckpointedPlanRunner
from local_workflow import LocalAgentWorkflow
from review_pending import approval_phrase, review_pending
from tool_runner import SafeToolRunner


class NoProposalAgent:
    def propose(self, task, context=None):
        raise AssertionError("review must not call proposal generation")


def record():
    return {
        "schema_version": 1,
        "created_at_utc": "2026-11-20T10:00:00+00:00",
        "task": {
            "id": "agent-007",
            "title": "Review proposal",
            "acceptance": "Run a fixed test suite",
            "status": "in_progress",
        },
        "model": "local-test-model",
        "proposal": {
            "task_id": "agent-007",
            "summary_ar": "تشغيل مجموعة الاختبارات الثابتة",
            "steps": [{"kind": "run_test", "target": "agent_unit_tests"}],
            "needs_human_approval": True,
            "claims_to_verify": [],
        },
        "awaiting_human_approval": True,
        "executed": False,
    }


class ReviewPendingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.pending = self.root / "pending.json"
        self.state = self.root / "state"
        self.pending.write_text(json.dumps(record()), encoding="utf-8")
        self.workflow = LocalAgentWorkflow(
            NoProposalAgent(),
            CheckpointedPlanRunner(SafeToolRunner(root=self.root)),
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_wrong_phrase_rejected_before_checkpoint_or_execution(self):
        with self.assertRaisesRegex(PolicyViolation, "did not match"):
            review_pending(
                self.pending, approval_text="نعم", workflow=self.workflow,
                state_dir=self.state,
            )
        self.assertFalse(self.state.exists())

    def test_exact_phrase_runs_only_allowlisted_step(self):
        from unittest.mock import patch
        from subprocess import CompletedProcess
        with patch("tool_runner.subprocess.run") as run:
            run.return_value = CompletedProcess(
                args=["python", "-m", "unittest"], returncode=0, stdout="OK"
            )
            state, results = review_pending(
                self.pending, approval_text=approval_phrase("agent-007"),
                workflow=self.workflow, state_dir=self.state,
            )
        self.assertEqual(state["state"], "completed")
        self.assertEqual(results[0]["status"], "passed")
        self.assertEqual(run.call_args.kwargs["shell"], False)

    def test_rejects_tampered_or_extra_record_fields(self):
        value = record()
        value["unexpected"] = "reject"
        self.pending.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(PolicyViolation, "exact saved schema"):
            review_pending(self.pending, approval_text=approval_phrase("agent-007"), state_dir=self.state)
        self.assertFalse(self.state.exists())

    def test_rejects_wrong_task_identity_in_proposal(self):
        value = record()
        value["proposal"]["task_id"] = "agent-999"
        self.pending.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(PolicyViolation, "task_id"):
            review_pending(self.pending, approval_text=approval_phrase("agent-007"), state_dir=self.state)

    def test_rejects_unconfirmed_task_state(self):
        value = record()
        value["task"]["status"] = "completed"
        self.pending.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(PolicyViolation, "not in a runnable"):
            review_pending(self.pending, approval_text=approval_phrase("agent-007"), state_dir=self.state)


if __name__ == "__main__":
    unittest.main()
