import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from agent_cycle import run_cycle, select_next_task


class AgentCycleTests(unittest.TestCase):
    def test_resumes_in_progress_before_pending(self):
        memory = {"next_tasks": [
            {"id": "p1", "title": "Pending", "status": "pending"},
            {"id": "i1", "title": "Resume", "status": "in_progress"},
        ]}
        self.assertEqual(select_next_task(memory)["id"], "i1")

    def test_selects_first_pending_when_no_in_progress(self):
        memory = {"next_tasks": [
            {"id": "b1", "title": "Blocked", "status": "blocked"},
            {"id": "p1", "title": "Pending", "status": "pending"},
        ]}
        self.assertEqual(select_next_task(memory)["id"], "p1")

    def test_returns_none_when_queue_has_no_runnable_task(self):
        self.assertIsNone(select_next_task({"next_tasks": [
            {"id": "b1", "status": "blocked"},
            {"id": "c1", "status": "completed"},
        ]}))

    def test_cycle_runs_audit_and_appends_durable_event(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            memory_dir = root / "docs" / "agent"
            memory_dir.mkdir(parents=True)
            (memory_dir / "agent_memory.json").write_text(json.dumps({
                "schema_version": 1,
                "project": "test",
                "updated_at": "2026-11-20",
                "known_constraints": [],
                "next_tasks": [{"id": "t1", "title": "Task", "status": "pending", "acceptance": "pass"}],
            }), encoding="utf-8")
            runner = Mock(return_value=SimpleNamespace(returncode=0, stdout="audit ok"))
            log = root / "cycle.jsonl"
            report_dir = root / "reports"
            fixed = datetime(2026, 11, 20, tzinfo=timezone.utc)
            event = run_cycle(root, log_path=log, report_dir=report_dir, runner=runner, clock=lambda: fixed)
            self.assertEqual(event["audit_status"], "passed")
            self.assertEqual(event["task"]["id"], "t1")
            runner.assert_called_once()
            saved = json.loads(log.read_text(encoding="utf-8").strip())
            self.assertEqual(saved["exit_code"], 0)
            self.assertEqual(saved["task"]["id"], "t1")
            self.assertIn("audit-", Path(saved["report_path"]).name)

    def test_audit_failure_is_logged_without_mutating_memory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            memory_dir = root / "docs" / "agent"
            memory_dir.mkdir(parents=True)
            memory = {
                "schema_version": 1,
                "project": "test",
                "updated_at": "2026-11-20",
                "known_constraints": [],
                "next_tasks": [{"id": "t1", "title": "Task", "status": "in_progress", "acceptance": "pass"}],
            }
            memory_file = memory_dir / "agent_memory.json"
            original = json.dumps(memory)
            memory_file.write_text(original, encoding="utf-8")
            runner = Mock(return_value=SimpleNamespace(returncode=3, stdout="test failed"))
            event = run_cycle(root, log_path=root / "cycle.jsonl", report_dir=root / "reports", runner=runner)
            self.assertEqual(event["audit_status"], "failed")
            self.assertEqual(event["exit_code"], 3)
            self.assertEqual(memory_file.read_text(encoding="utf-8"), original)

    def test_invalid_memory_fails_closed_and_is_logged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            memory_dir = root / "docs" / "agent"
            memory_dir.mkdir(parents=True)
            (memory_dir / "agent_memory.json").write_text("{}", encoding="utf-8")
            runner = Mock()
            event = run_cycle(root, log_path=root / "cycle.jsonl", runner=runner)
            self.assertEqual(event["audit_status"], "error")
            runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
