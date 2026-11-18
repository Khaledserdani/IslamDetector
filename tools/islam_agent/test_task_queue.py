import json
import tempfile
import unittest
from pathlib import Path

from task_queue import load_memory, transition, write_memory_atomic


class TaskQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "memory.json"
        self.memory = {
            "schema_version": 1,
            "project": "test",
            "updated_at": "2026-11-18",
            "known_constraints": [],
            "next_tasks": [
                {"id": "t1", "title": "Test task", "status": "pending", "acceptance": "works"}
            ],
        }
        self.path.write_text(json.dumps(self.memory), encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_and_valid_transition(self):
        memory = load_memory(self.path)
        task = transition(memory, "t1", "in_progress", "started")
        self.assertEqual(task["status"], "in_progress")
        self.assertEqual(task["last_note"], "started")
        self.assertEqual(memory["task_events"][-1]["from"], "pending")

    def test_invalid_transition_is_rejected(self):
        memory = load_memory(self.path)
        with self.assertRaises(ValueError):
            transition(memory, "t1", "completed")

    def test_unknown_task_is_rejected(self):
        memory = load_memory(self.path)
        with self.assertRaises(ValueError):
            transition(memory, "missing", "in_progress")

    def test_duplicate_ids_are_rejected(self):
        duplicate = dict(self.memory)
        duplicate["next_tasks"] = self.memory["next_tasks"] * 2
        self.path.write_text(json.dumps(duplicate), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_memory(self.path)

    def test_atomic_write_round_trip(self):
        memory = load_memory(self.path)
        transition(memory, "t1", "in_progress")
        write_memory_atomic(self.path, memory)
        reread = load_memory(self.path)
        self.assertEqual(reread["next_tasks"][0]["status"], "in_progress")


if __name__ == "__main__":
    unittest.main()