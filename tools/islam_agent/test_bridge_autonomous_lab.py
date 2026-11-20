import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bridge_server import BridgeApplication


class ScheduledLabBridgeTests(unittest.TestCase):

    def test_lab_proposal_is_not_executed_after_work_window_closes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            memory = root / "memory.json"
            memory.write_text(json.dumps({
                "schema_version": 1, "project": "test", "updated_at": "2026-11-20",
                "known_constraints": [],
                "next_tasks": [{"id": "lab-task", "title": "DC lab",
                    "acceptance": "Run a validated DC divider experiment", "status": "pending"}],
            }), encoding="utf-8")
            pending = root / "pending.json"
            app = BridgeApplication("123456", "local-test-model",
                memory_path=memory, proposal_path=pending, state_dir=root / "state")
            app.work_window = {"start": "20:00", "end": "06:00", "timezone": "Africa/Algiers"}
            record = {
                "schema_version": 1, "created_at_utc": "2026-11-20T20:00:00+00:00",
                "task": {"id": "lab-task", "title": "DC lab"},
                "model": "local-test-model",
                "proposal": {
                    "task_id": "lab-task", "summary_ar": "Run a 10V divider",
                    "steps": [{"kind": "simulate_circuit", "target": "dc_resistive_network",
                        "circuit": {"ground": "0",
                            "resistors": [{"a": "in", "b": "mid", "ohms": 1000},
                                          {"a": "mid", "b": "0", "ohms": 1000}],
                            "voltage_sources": [{"positive": "in", "negative": "0", "volts": 10}]}}],
                    "needs_human_approval": True, "claims_to_verify": [],
                },
                "awaiting_human_approval": True, "executed": False,
            }
            def fake_proposal(_memory_path, proposal_path):
                Path(proposal_path).write_text(json.dumps(record), encoding="utf-8")
                return {"status": "proposal_saved"}
            with patch("work_schedule.is_within_work_window", return_value=False):
                with patch("bridge_server.LocalAgentOrchestrator.run_once", side_effect=fake_proposal):
                    result = app.create_proposal(auto_run_labs=True)
            self.assertEqual(result["status"], "awaiting_human_review")
            self.assertTrue(pending.exists())
            self.assertFalse(list((root / "state" / "lab_runs").glob("*.json")))

    def test_scheduled_proposal_runs_in_dc_lab_and_is_archived_as_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            memory = root / "memory.json"
            memory.write_text(json.dumps({
                "schema_version": 1, "project": "test", "updated_at": "2026-11-20",
                "known_constraints": [],
                "next_tasks": [{"id": "lab-task", "title": "DC lab",
                    "acceptance": "Run a validated DC divider experiment", "status": "pending"}],
            }), encoding="utf-8")
            pending = root / "pending.json"
            app = BridgeApplication("123456", "local-test-model",
                memory_path=memory, proposal_path=pending, state_dir=root / "state")
            record = {
                "schema_version": 1, "created_at_utc": "2026-11-20T20:00:00+00:00",
                "task": {"id": "lab-task", "title": "DC lab"},
                "model": "local-test-model",
                "proposal": {
                    "task_id": "lab-task", "summary_ar": "Run a 10V divider",
                    "steps": [{"kind": "simulate_circuit", "target": "dc_resistive_network",
                        "circuit": {"ground": "0",
                            "resistors": [{"a": "in", "b": "mid", "ohms": 1000},
                                          {"a": "mid", "b": "0", "ohms": 1000}],
                            "voltage_sources": [{"positive": "in", "negative": "0", "volts": 10}]}}],
                    "needs_human_approval": True, "claims_to_verify": [],
                },
                "awaiting_human_approval": True, "executed": False,
            }
            def fake_proposal(_memory_path, proposal_path):
                Path(proposal_path).write_text(json.dumps(record), encoding="utf-8")
                return {"status": "proposal_saved"}
            with patch("bridge_server.LocalAgentOrchestrator.run_once", side_effect=fake_proposal):
                result = app.create_proposal(auto_run_labs=True)
            self.assertEqual(result["status"], "lab_experiment_verified")
            self.assertTrue(result["lab_run"]["verified_numerically"])
            self.assertFalse(pending.exists())
            report = json.loads(Path(result["lab_run"]["report_path"]).read_text(encoding="utf-8"))
            self.assertAlmostEqual(report["results"][0]["result"]["node_voltages_v"]["mid"], 5.0)


if __name__ == "__main__":
    unittest.main()
