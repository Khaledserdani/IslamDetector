import unittest

from agent_policy import PolicyViolation, validate_proposal


def valid_proposal():
    return {
        "task_id": "agent-003",
        "summary_ar": "اقتراح آمن لمراجعة تصميم الاتصال المحلي",
        "steps": [
            {"kind": "inspect", "target": "docs/agent/OLLAMA_LOCAL_AGENT_DESIGN_AR.md"},
            {"kind": "run_test", "target": "agent_unit_tests"},
        ],
        "needs_human_approval": True,
        "claims_to_verify": ["لم يتم تشغيل نموذج فعلي بعد"],
    }


class AgentPolicyTests(unittest.TestCase):
    def test_accepts_valid_allowlisted_proposal(self):
        result = validate_proposal(valid_proposal(), "agent-003")
        self.assertEqual(result["task_id"], "agent-003")
        self.assertEqual(len(result["steps"]), 2)
        self.assertIs(result["needs_human_approval"], True)

    def test_rejects_task_id_mismatch(self):
        with self.assertRaisesRegex(PolicyViolation, "does not match"):
            validate_proposal(valid_proposal(), "agent-004")

    def test_rejects_extra_top_level_field(self):
        proposal = valid_proposal()
        proposal["shell"] = "rm -rf /"
        with self.assertRaisesRegex(PolicyViolation, "exact allowed schema"):
            validate_proposal(proposal, "agent-003")

    def test_rejects_unknown_step_kind(self):
        proposal = valid_proposal()
        proposal["steps"][0]["kind"] = "execute_shell"
        with self.assertRaisesRegex(PolicyViolation, "not allowlisted"):
            validate_proposal(proposal, "agent-003")

    def test_rejects_non_string_step_kind_without_crashing(self):
        proposal = valid_proposal()
        proposal["steps"][0]["kind"] = []
        with self.assertRaisesRegex(PolicyViolation, "step kind"):
            validate_proposal(proposal, "agent-003")

    def test_rejects_arbitrary_inspection_path(self):
        proposal = valid_proposal()
        proposal["steps"][0]["target"] = "../../.env"
        with self.assertRaisesRegex(PolicyViolation, "inspect target"):
            validate_proposal(proposal, "agent-003")

    def test_rejects_unlisted_test_suite(self):
        proposal = valid_proposal()
        proposal["steps"][1]["target"] = "python -c 'print(1)'"
        with self.assertRaisesRegex(PolicyViolation, "test target"):
            validate_proposal(proposal, "agent-003")

    def test_rejects_missing_human_approval(self):
        proposal = valid_proposal()
        proposal["needs_human_approval"] = False
        with self.assertRaisesRegex(PolicyViolation, "must remain required"):
            validate_proposal(proposal, "agent-003")

    def test_rejects_step_extra_fields(self):
        proposal = valid_proposal()
        proposal["steps"][0]["path"] = "anything"
        with self.assertRaisesRegex(PolicyViolation, "only kind and target"):
            validate_proposal(proposal, "agent-003")

    def test_rejects_empty_or_oversized_steps(self):
        proposal = valid_proposal()
        proposal["steps"] = []
        with self.assertRaisesRegex(PolicyViolation, "between 1 and 5"):
            validate_proposal(proposal, "agent-003")
        proposal["steps"] = [{"kind": "run_test", "target": "agent_unit_tests"}] * 6
        with self.assertRaisesRegex(PolicyViolation, "between 1 and 5"):
            validate_proposal(proposal, "agent-003")

    def test_rejects_non_string_claim(self):
        proposal = valid_proposal()
        proposal["claims_to_verify"] = [123]
        with self.assertRaisesRegex(PolicyViolation, "non-empty bounded string"):
            validate_proposal(proposal, "agent-003")

    def test_android_source_write_requires_android_tests(self):
        proposal = {
            "task_id": "agent-003",
            "summary_ar": "تعديل واجهة Android",
            "steps": [{
                "kind": "write_file",
                "target": "agent/src/main/java/com/islamfreeagent/app/MainActivity.java",
                "content": "class MainActivity {}",
            }],
            "needs_human_approval": True,
            "claims_to_verify": [],
        }
        with self.assertRaisesRegex(PolicyViolation, "require android_unit_tests"):
            validate_proposal(proposal, "agent-003")
        proposal["steps"].append({"kind": "run_test", "target": "android_unit_tests"})
        self.assertEqual(len(validate_proposal(proposal, "agent-003")["steps"]), 2)

    def test_python_agent_write_requires_python_tests(self):
        proposal = {
            "task_id": "agent-003",
            "summary_ar": "تعديل منسق Python",
            "steps": [{
                "kind": "write_file",
                "target": "tools/islam_agent/local_agent.py",
                "content": "print('safe')",
            }],
            "needs_human_approval": True,
            "claims_to_verify": [],
        }
        with self.assertRaisesRegex(PolicyViolation, "require agent_unit_tests"):
            validate_proposal(proposal, "agent-003")
        proposal["steps"].append({"kind": "run_test", "target": "agent_unit_tests"})
        self.assertEqual(len(validate_proposal(proposal, "agent-003")["steps"]), 2)

    def test_rejects_non_object_proposal(self):
        with self.assertRaisesRegex(PolicyViolation, "JSON object"):
            validate_proposal([], "agent-003")


if __name__ == "__main__":
    unittest.main()
