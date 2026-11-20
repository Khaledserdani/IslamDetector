import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from subprocess import CompletedProcess

from agent_policy import PolicyViolation
from tool_runner import AGENT_TEST_MODULES, SafeToolRunner, ToolExecutionError


def proposal(steps):
    return {
        "task_id": "agent-003",
        "summary_ar": "اختبار منفذ الأدوات الآمن",
        "steps": steps,
        "needs_human_approval": True,
        "claims_to_verify": [],
    }


class SafeToolRunnerTests(unittest.TestCase):
    def test_inspects_only_allowlisted_file_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "docs/agent/OLLAMA_LOCAL_AGENT_DESIGN_AR.md"
            target.parent.mkdir(parents=True)
            target.write_text("read-only evidence", encoding="utf-8")
            runner = SafeToolRunner(root=root)
            result = runner.execute_plan(
                proposal([{"kind": "inspect", "target": "docs/agent/OLLAMA_LOCAL_AGENT_DESIGN_AR.md"}]),
                "agent-003",
                human_approved=True,
            )
            self.assertEqual(result[0]["content"], "read-only evidence")
            self.assertEqual(target.read_text(encoding="utf-8"), "read-only evidence")

    def test_rejects_unapproved_path_before_reading(self):
        runner = SafeToolRunner()
        with self.assertRaisesRegex(PolicyViolation, "inspect target"):
            runner.execute_plan(
                proposal([{"kind": "inspect", "target": "../../.env"}]),
                "agent-003",
                human_approved=True,
            )

    @patch("tool_runner.subprocess.run")
    def test_requires_explicit_human_approval(self, run):
        runner = SafeToolRunner()
        with self.assertRaisesRegex(PolicyViolation, "explicit human approval"):
            runner.execute_plan(
                proposal([{"kind": "run_test", "target": "agent_unit_tests"}]),
                "agent-003",
            )
        run.assert_not_called()

    @patch("tool_runner.subprocess.run")
    def test_runs_complete_fixed_test_command_without_shell(self, run):
        run.return_value = CompletedProcess(args=["python", "-m", "unittest"], returncode=0, stdout="OK")
        runner = SafeToolRunner()
        result = runner.execute_plan(
            proposal([{"kind": "run_test", "target": "agent_unit_tests"}]),
            "agent-003",
            human_approved=True,
        )
        self.assertEqual(result[0]["status"], "passed")
        kwargs = run.call_args.kwargs
        command = run.call_args.args[0]
        self.assertIs(kwargs["shell"], False)
        self.assertEqual(kwargs["timeout"], 120)
        self.assertEqual(command[1:4], ["-m", "unittest", "-v"])
        self.assertEqual(tuple(command[4:]), AGENT_TEST_MODULES)
        self.assertEqual(len(AGENT_TEST_MODULES), 10)
        self.assertIn("test_agent_cycle", AGENT_TEST_MODULES)
        self.assertIn("test_orchestrator", AGENT_TEST_MODULES)

    def test_failed_tests_stop_later_steps(self):
        with patch("tool_runner.subprocess.run") as run:
            run.return_value = CompletedProcess(args=["python"], returncode=1, stdout="failure")
            runner = SafeToolRunner()
            results = runner.execute_plan(
                proposal([
                    {"kind": "run_test", "target": "agent_unit_tests"},
                    {"kind": "inspect", "target": "tools/islam_agent/ollama_client.py"},
                ]),
                "agent-003",
                human_approved=True,
            )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "failed")

    def test_rejects_unknown_test_name(self):
        runner = SafeToolRunner()
        with self.assertRaisesRegex(PolicyViolation, "test target"):
            runner.execute_plan(
                proposal([{"kind": "run_test", "target": "python -c print(1)"}]),
                "agent-003",
                human_approved=True,
            )


if __name__ == "__main__":
    unittest.main()
