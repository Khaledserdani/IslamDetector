import json
import tempfile
import unittest
from pathlib import Path

from orchestrator import LocalAgentOrchestrator, OrchestrationError, _bounded_project_context


class FakeWorkflow:
    def __init__(self, result=None, error=None):
        self.result = result if result is not None else {
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
    def _run_bad_result(self, result):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            memory, proposal = root / "memory.json", root / "pending.json"
            write_memory(memory)
            with self.assertRaises(OrchestrationError):
                LocalAgentOrchestrator(FakeWorkflow(result=result)).run_once(memory, proposal)
            self.assertFalse(proposal.exists())

    def test_context_prioritizes_named_file_and_keeps_full_small_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "tools/islam_agent/orchestrator.py"
            target.parent.mkdir(parents=True)
            source = "# context marker\\n" + ("x" * 2500)
            target.write_text(source, encoding="utf-8")
            (root / "tools/islam_agent/local_agent.py").write_text(
                "# secondary context", encoding="utf-8"
            )
            context = _bounded_project_context(
                root, {"title": "Improve orchestrator.py", "acceptance": "keep task context"}
            )
            self.assertTrue(context)
            self.assertTrue(context[0].startswith("FILE: tools/islam_agent/orchestrator.py"))
            self.assertIn("x" * 2000, context[0])

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
        result = FakeWorkflow().result
        result["executed"] = True
        self._run_bad_result(result)

    def test_rejects_non_object_workflow_result(self):
        self._run_bad_result(["not", "an", "object"])

    def test_rejects_extra_workflow_result_fields(self):
        result = FakeWorkflow().result
        result["unexpected"] = "must not pass"
        self._run_bad_result(result)

    def test_rejects_proposal_for_another_task(self):
        result = FakeWorkflow().result
        result["proposal"]["task_id"] = "agent-999"
        self._run_bad_result(result)

    def test_rejects_unallowlisted_proposal_step(self):
        result = FakeWorkflow().result
        result["proposal"]["steps"][0]["target"] = "../../secrets"
        self._run_bad_result(result)

    def test_rejects_invalid_model_name(self):
        result = FakeWorkflow().result
        result["model"] = " "
        self._run_bad_result(result)

    def test_rejects_oversized_model_name(self):
        result = FakeWorkflow().result
        result["model"] = "m" * 129
        self._run_bad_result(result)


if __name__ == "__main__":
    unittest.main()
