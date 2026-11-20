import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from autonomous_lab import run_autonomous_lab_proposal, _compact_result
from tool_runner import SafeToolRunner


def record(steps):
    return {
        "schema_version": 1,
        "created_at_utc": "2026-11-20T20:00:00+00:00",
        "task": {"id": "lab-auto-1", "title": "اختبار المختبر الكهربائي"},
        "model": "test-local-model",
        "proposal": {
            "task_id": "lab-auto-1",
            "summary_ar": "تشغيل تجربة مختبرية آمنة والتحقق من النتيجة",
            "steps": steps,
            "needs_human_approval": True,
            "claims_to_verify": [],
        },
        "awaiting_human_approval": True,
        "executed": False,
    }


class AutonomousLabTests(unittest.TestCase):
    def test_dc_lab_runs_without_project_write_approval_and_saves_evidence(self):
        proposal = record([{
            "kind": "simulate_circuit",
            "target": "dc_resistive_network",
            "circuit": {
                "ground": "0",
                "resistors": [
                    {"a": "supply", "b": "mid", "ohms": 1000},
                    {"a": "mid", "b": "0", "ohms": 1000},
                ],
                "voltage_sources": [{"positive": "supply", "negative": "0", "volts": 10}],
            },
        }])
        with tempfile.TemporaryDirectory() as directory:
            result = run_autonomous_lab_proposal(
                proposal, report_dir=Path(directory),
                clock=lambda: datetime(2026, 11, 20, 21, 0, tzinfo=timezone.utc),
            )
            self.assertEqual(result["status"], "verified")
            self.assertTrue(result["verified_numerically"])
            report = json.loads(Path(result["report_path"]).read_text(encoding="utf-8"))
            self.assertTrue(report["verified_numerically"])
            self.assertAlmostEqual(report["results"][0]["result"]["node_voltages_v"]["mid"], 5.0)
            self.assertTrue(report["human_review_required_for_project_changes"])

    def test_mixed_lab_and_write_plan_is_not_auto_executed(self):
        proposal = record([
            {"kind": "simulate_circuit", "target": "dc_resistive_network", "circuit": {
                "ground": "0",
                "resistors": [{"a": "v", "b": "0", "ohms": 1000}],
                "voltage_sources": [{"positive": "v", "negative": "0", "volts": 5}],
            }},
            {"kind": "write_file", "target": "docs/agent/agent_worklog.md", "content": "# change"},
        ])
        class NeverRun:
            def execute_autonomous_lab_plan(self, *_args):
                raise AssertionError("mixed plan must not reach the executor")
        with tempfile.TemporaryDirectory() as directory:
            result = run_autonomous_lab_proposal(
                proposal, report_dir=Path(directory), runner=NeverRun()
            )
            self.assertEqual(result["status"], "needs_human_review")
            self.assertFalse(list(Path(directory).glob("*.json")))

    def test_failed_numerical_verification_is_recorded_as_failed(self):
        class FailedRunner:
            def execute_autonomous_lab_plan(self, *_args):
                return [{"kind": "simulate_circuit", "status": "passed",
                         "result": {"verified_numerically": False}}]
        with tempfile.TemporaryDirectory() as directory:
            result = run_autonomous_lab_proposal(
                record([{"kind": "simulate_circuit", "target": "dc_resistive_network",
                        "circuit": {"ground": "0", "resistors": [{"a": "v", "b": "0", "ohms": 1000}],
                                    "voltage_sources": [{"positive": "v", "negative": "0", "volts": 5}]}}]),
                report_dir=Path(directory), runner=FailedRunner(),
            )
            self.assertEqual(result["status"], "failed")
            self.assertFalse(result["verified_numerically"])


    def test_identical_experiment_is_not_run_twice(self):
        proposal = record([{
            "kind": "simulate_circuit",
            "target": "dc_resistive_network",
            "circuit": {
                "ground": "0",
                "resistors": [{"a": "v", "b": "0", "ohms": 1000}],
                "voltage_sources": [{"positive": "v", "negative": "0", "volts": 5}],
            },
        }])
        class NeverRun:
            def execute_autonomous_lab_plan(self, *_args):
                raise AssertionError("duplicate experiment must not be simulated again")
        with tempfile.TemporaryDirectory() as directory:
            first = run_autonomous_lab_proposal(proposal, report_dir=Path(directory))
            second = run_autonomous_lab_proposal(
                proposal, report_dir=Path(directory), runner=NeverRun()
            )
            self.assertEqual(first["status"], "verified")
            self.assertEqual(second["status"], "duplicate")
            self.assertEqual(first["report_path"], second["report_path"])

    def test_long_numeric_trace_is_compacted(self):
        result = _compact_result({"trace": list(range(1500))})
        self.assertEqual(result["trace"]["sample_count"], 1500)
        self.assertEqual(result["trace"]["first"], 0)
        self.assertEqual(result["trace"]["last"], 1499)

    def test_tool_runner_rejects_any_non_lab_step_in_autonomous_mode(self):
        proposal = record([{"kind": "run_test", "target": "agent_unit_tests"}])
        with self.assertRaises(Exception):
            SafeToolRunner().execute_autonomous_lab_plan(proposal["proposal"], "lab-auto-1")


if __name__ == "__main__":
    unittest.main()
