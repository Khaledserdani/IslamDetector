import tempfile
import unittest
from pathlib import Path

from agent_policy import PolicyViolation, validate_proposal
from tool_runner import SafeToolRunner


class SafeWriterTests(unittest.TestCase):
    def test_writes_allowlisted_file_and_reports_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "docs/agent/agent_worklog.md"
            result = SafeToolRunner(root=root)._write_file(
                "docs/agent/agent_worklog.md", "# Work log\n"
            )
            self.assertEqual(target.read_text(encoding="utf-8"), "# Work log\n")
            self.assertEqual(result["status"], "written")
            self.assertEqual(len(result["sha256"]), 64)

    def test_refuses_unlisted_and_traversal_paths(self):
        runner = SafeToolRunner()
        for target in ("../../.env", "docs/agent/agent_memory.json", "README.md"):
            with self.subTest(target=target):
                with self.assertRaises(PolicyViolation):
                    runner._write_file(target, "not allowed")

    def test_refuses_symlink_target(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            (root / "docs/agent").mkdir(parents=True)
            outside_file = Path(outside) / "secret"
            outside_file.write_text("keep", encoding="utf-8")
            (root / "docs/agent/agent_worklog.md").symlink_to(outside_file)
            with self.assertRaises(PolicyViolation):
                SafeToolRunner(root=root)._write_file("docs/agent/agent_worklog.md", "overwrite")
            self.assertEqual(outside_file.read_text(encoding="utf-8"), "keep")

    def test_proposal_requires_content_and_exact_write_target(self):
        proposal = {
            "task_id": "t1", "summary_ar": "كتابة ملف مسموح",
            "steps": [{"kind": "write_file", "target": "docs/agent/agent_worklog.md", "content": "hello"}],
            "needs_human_approval": True, "claims_to_verify": [],
        }
        self.assertEqual(validate_proposal(proposal, "t1")["steps"][0]["content"], "hello")
        proposal["steps"] = [{"kind": "write_file", "target": "../../.env", "content": "secret"}]
        with self.assertRaises(PolicyViolation):
            validate_proposal(proposal, "t1")


if __name__ == "__main__":
    unittest.main()
