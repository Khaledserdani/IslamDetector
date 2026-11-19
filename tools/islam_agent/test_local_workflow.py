import tempfile
import unittest
from pathlib import Path

from agent_policy import PolicyViolation
from checkpointed_runner import CheckpointedPlanRunner
from local_workflow import LocalAgentWorkflow
from tool_runner import SafeToolRunner


class FakeProposalAgent:
    def __init__(self, proposal):
        self.value = proposal
        self.calls = 0

    def propose(self, task, context=None):
        self.calls += 1
        return {
            "model": "fake-local-model",
            "proposal": self.value,
            "awaiting_human_approval": True,
            "executed": False,
        }


def valid_proposal():
    return {
        "task_id": "agent-003",
        "summary_ar": "فحص ملف مسموح",
        "steps": [{
            "kind": "inspect",
            "target": "docs/agent/OLLAMA_LOCAL_AGENT_DESIGN_AR.md",
        }],
        "needs_human_approval": True,
        "claims_to_verify": [],
    }


class LocalAgentWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        target = self.root / "docs/agent/OLLAMA_LOCAL_AGENT_DESIGN_AR.md"
        target.parent.mkdir(parents=True)
        target.write_text("workflow evidence", encoding="utf-8")
        self.checkpoint = self.root / "state/checkpoint.json"
        self.lock = self.root / "state/run.lock"
        self.agent = FakeProposalAgent(valid_proposal())
        self.workflow = LocalAgentWorkflow(
            self.agent,
            CheckpointedPlanRunner(SafeToolRunner(root=self.root)),
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_proposal_generation_never_executes(self):
        pending = self.workflow.propose({
            "id": "agent-003", "title": "Inspect", "acceptance": "Read allowlisted file"
        })
        self.assertTrue(pending["awaiting_human_approval"])
        self.assertFalse(pending["executed"])
        self.assertFalse(self.checkpoint.exists())

    def test_execution_is_blocked_without_explicit_approval(self):
        pending = self.workflow.propose({
            "id": "agent-003", "title": "Inspect", "acceptance": "Read allowlisted file"
        })
        with self.assertRaisesRegex(PolicyViolation, "explicit human approval"):
            self.workflow.approve_and_execute(
                pending, "agent-003", checkpoint_path=self.checkpoint,
                lock_path=self.lock, run_id="integration-001",
            )
        self.assertFalse(self.checkpoint.exists())

    def test_explicit_approval_executes_and_persists_evidence(self):
        pending = self.workflow.propose({
            "id": "agent-003", "title": "Inspect", "acceptance": "Read allowlisted file"
        })
        state, results = self.workflow.approve_and_execute(
            pending, "agent-003", human_approved=True,
            checkpoint_path=self.checkpoint, lock_path=self.lock,
            run_id="integration-002",
        )
        self.assertEqual(state["state"], "completed")
        self.assertEqual(len(state["completed_steps"]), 1)
        self.assertEqual(results[0]["content"], "workflow evidence")
        self.assertTrue(self.checkpoint.is_file())

    def test_rejects_altered_pending_proposal(self):
        pending = self.workflow.propose({
            "id": "agent-003", "title": "Inspect", "acceptance": "Read allowlisted file"
        })
        pending["executed"] = True
        with self.assertRaisesRegex(PolicyViolation, "pending, unexecuted"):
            self.workflow.approve_and_execute(
                pending, "agent-003", human_approved=True,
                checkpoint_path=self.checkpoint, lock_path=self.lock,
                run_id="integration-003",
            )
        self.assertFalse(self.checkpoint.exists())


if __name__ == "__main__":
    unittest.main()
