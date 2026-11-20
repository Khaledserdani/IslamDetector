import json
import tempfile
import unittest
from pathlib import Path

from orchestrator import LocalAgentOrchestrator, OrchestrationError


class FakeWorkflow:
    def __init__(self, result=None, error=None):
        self.result = result or {
            "model": "fake-model",
            "proposal": {
                "task_id": "agent-007",
                "summary_ar": "خطة تحقق آمنة",
                "steps": [{"kind": "run_test", "target": "agent_unit_tests"}],
                "needs_human_approval": True,
                "claims_to_verify": [],
            },
            "awaiting_human_approval": True,
            "executed": False,
        }
        self.error = error
        self.calls = 0

    def propose(self, task, context=None):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


def write_memory(path, status="pending"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema_version": 1,
        "project": "test",
        "updated_at": "2026-11-20",
        "known_constraints": [],
        "next_tasks": [{
            "id": "agent-007",
            "title": "Build proposal orchestrator",
            "acceptance": "Validated proposal awaits human approval",
            "status": status,
        }],
    }), encoding="utf-8")


class OrchestratorTests(unittest.TestCase):
    def test_selects_task_and_persists_pending_proposal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            memory = root / "memory.json"
            proposal = root / "pending.json"
            write_memory(memory)
            workflow = FakeWorkflow()
            result = LocalAgentOrchestrator(workflow).run_once(memory, proposal)
            saved = json.loads(proposal.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "proposal_saved")
            self.assertEqual(saved["task"]["id"], "agent-007")
            self.assertTrue(saved["awaiting_human_approval"])
            self.assertFalse(saved["executed"])
            self.assertEqual(workflow.calls, 1)

    def test_does_not_overwrite_existing_pending_proposal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            memory, proposal = root / "memory.json", root / "pending.json"
            write_memory(memory)
            proposal.write_text("keep-me", encoding="utf-8")
            with self.assertRaisesRegex(OrchestrationError, "already exists"):
                LocalAgentOrchestrator(FakeWorkflow()).run_once(memory, proposal)
            self.assertEqual(proposal.read_text(encoding="utf-8"), "keep-me")

    def test_no_runnable_task_does_not_call_model_or_write_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            memory, proposal = root / "memory.json", root / "pending.json"
            write_memory(memory, status="blocked")
            workflow = FakeWorkflow()
            result = LocalAgentOrchestrator(workflow).run_once(memory, proposal)
            self.assertEqual(result["status"], "no_task")
            self.assertEqual(workflow.calls, 0)
            self.assertFalse(proposal.exists())

    def test_model_failure_does_not_write_pending_proposal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            memory, proposal = root / "memory.json", root / "pending.json"
            write_memory(memory)
            workflow = FakeWorkflow(error=RuntimeError("local model unavailable"))
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                LocalAgentOrchestrator(workflow).run_once(memory, proposal)
            self.assertFalse(proposal.exists())

    def test_rejects_workflow_result_that_claims_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            memory, proposal = root / "memory.json", root / "pending.json"
            write_memory(memory)
            bad = FakeWorkflow()
            bad.result["executed"] = True
            with self.assertRaisesRegex(OrchestrationError, "unexecuted"):
                LocalAgentOrchestrator(bad).run_once(memory, proposal)
            self.assertFalse(proposal.exists())


if __name__ == "__main__":
    unittest.main()
