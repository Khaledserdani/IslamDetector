import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from manager_audit import TEST_MODULES, audit, run_tests, validate_memory


class ManagerAuditTests(unittest.TestCase):
    def test_rejects_invalid_or_duplicate_task_memory(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "memory.json"
            path.write_text('{"schema_version":1,"project":"x","updated_at":"today","known_constraints":[],"next_tasks":[]}', encoding="utf-8")
            memory, error = validate_memory(path)
            self.assertIsNotNone(memory)
            self.assertIsNone(error)
            path.write_text('{"schema_version":1,"project":"x","updated_at":"today","known_constraints":[],"next_tasks":[{"id":"a","title":"A","acceptance":"A","status":"pending"},{"id":"a","title":"B","acceptance":"B","status":"pending"}]}', encoding="utf-8")
            memory, error = validate_memory(path)
            self.assertIsNone(memory)
            self.assertIn("Duplicate", error)

    def test_rejects_unknown_task_status(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "memory.json"
            path.write_text('{"schema_version":1,"project":"x","updated_at":"today","known_constraints":[],"next_tasks":[{"id":"a","title":"A","acceptance":"A","status":"running"}]}', encoding="utf-8")
            memory, error = validate_memory(path)
            self.assertIsNone(memory)
            self.assertIn("unknown status", error)

    def test_test_runner_uses_fixed_modules_no_shell_and_timeout(self):
        runner = Mock(return_value=SimpleNamespace(returncode=0, stdout="Ran tests"))
        with tempfile.TemporaryDirectory() as temp:
            result = run_tests(Path(temp), runner)
        self.assertEqual(result.returncode, 0)
        args, kwargs = runner.call_args
        self.assertEqual(args[0][0:3], [args[0][0], "-m", "unittest"])
        self.assertEqual(tuple(args[0][3:]), TEST_MODULES)
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["timeout"], 180)

    def test_test_runner_fails_closed_on_timeout(self):
        runner = Mock(side_effect=subprocess.TimeoutExpired("python", 180))
        with tempfile.TemporaryDirectory() as temp:
            result = run_tests(Path(temp), runner)
        self.assertEqual(result.returncode, 124)
        self.assertIn("timed out", result.stdout)

    def test_audit_does_not_run_tests_when_memory_is_invalid(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs/agent").mkdir(parents=True)
            (root / "docs/agent/agent_memory.json").write_text("{}", encoding="utf-8")
            runner = Mock()
            result = audit(root, runner)
        self.assertFalse(result["passed"])
        runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
