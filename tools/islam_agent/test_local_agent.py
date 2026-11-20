import json
import unittest
from types import SimpleNamespace

from agent_policy import PolicyViolation
from local_agent import LocalAgentError, LocalProposalAgent, SYSTEM_PROMPT


def valid_plan(task_id="agent-003"):
    return {
        "task_id": task_id,
        "summary_ar": "فحص تصميم العميل المحلي",
        "steps": [{"kind": "inspect", "target": "docs/agent/OLLAMA_LOCAL_AGENT_DESIGN_AR.md"}],
        "needs_human_approval": True,
        "claims_to_verify": [],
    }


class FakeClient:
    def __init__(self, content, done=True):
        self.content = content
        self.done = done
        self.messages = None

    def chat_json(self, messages):
        self.messages = messages
        return SimpleNamespace(model="fake-local-model", content=self.content, done=self.done)


class LocalProposalAgentTests(unittest.TestCase):
    def test_returns_valid_plan_without_executing_it(self):
        client = FakeClient(valid_plan())
        result = LocalProposalAgent(client).propose({
            "id": "agent-003", "title": "Local agent", "acceptance": "safe proposal",
            "private_extra": "must not be sent",
        }, ["short project context"])
        self.assertEqual(result["proposal"]["task_id"], "agent-003")
        self.assertTrue(result["awaiting_human_approval"])
        self.assertFalse(result["executed"])
        sent = json.loads(client.messages[1]["content"])
        self.assertNotIn("private_extra", sent["task"])
        self.assertIn("JSON", SYSTEM_PROMPT)
        self.assertIn("simulate_rlc", SYSTEM_PROMPT)
        self.assertIn("series_rlc", SYSTEM_PROMPT)
        self.assertIn("simulate_ac_network", SYSTEM_PROMPT)
        self.assertIn("linear_ac_network", SYSTEM_PROMPT)
        self.assertIn("design_circuit", SYSTEM_PROMPT)
        self.assertIn("circuit_design", SYSTEM_PROMPT)
        self.assertIn("validate_circuit_v2", SYSTEM_PROMPT)
        self.assertIn("pin_numbers", SYSTEM_PROMPT)
        self.assertIn("circuit_components.py", SYSTEM_PROMPT)

    def test_rejects_model_extra_fields(self):
        plan = valid_plan()
        plan["shell"] = "arbitrary"
        with self.assertRaises(PolicyViolation):
            LocalProposalAgent(FakeClient(plan)).propose({
                "id": "agent-003", "title": "task", "acceptance": "acceptance"
            })

    def test_rejects_task_id_mismatch(self):
        with self.assertRaisesRegex(PolicyViolation, "does not match"):
            LocalProposalAgent(FakeClient(valid_plan("agent-004"))).propose({
                "id": "agent-003", "title": "task", "acceptance": "acceptance"
            })

    def test_rejects_incomplete_model_response(self):
        with self.assertRaisesRegex(LocalAgentError, "did not complete"):
            LocalProposalAgent(FakeClient(valid_plan(), done=False)).propose({
                "id": "agent-003", "title": "task", "acceptance": "acceptance"
            })

    def test_rejects_oversized_context_before_calling_model(self):
        client = FakeClient(valid_plan())
        with self.assertRaisesRegex(LocalAgentError, "configured limit"):
            LocalProposalAgent(client).propose({
                "id": "agent-003", "title": "task", "acceptance": "acceptance"
            }, ["x" * 3000] * 5)
        self.assertIsNone(client.messages)

    def test_rejects_invalid_task(self):
        with self.assertRaisesRegex(LocalAgentError, "requires non-empty"):
            LocalProposalAgent(FakeClient(valid_plan())).propose({
                "id": "agent-003", "title": "", "acceptance": "acceptance"
            })


if __name__ == "__main__":
    unittest.main()
