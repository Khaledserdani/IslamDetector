import json
import tempfile
import unittest
from pathlib import Path

from checkpoint import (
    CheckpointError,
    exclusive_run_lock,
    load_checkpoint,
    new_checkpoint,
    record_step,
    save_checkpoint,
    set_checkpoint_state,
)


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.path = self.root / "state" / "checkpoint.json"
        self.lock = self.root / "state" / "run.lock"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_atomic_save_and_resume_preserves_progress(self):
        state = new_checkpoint("agent-003", "run-001")
        state = record_step(state, "inspect-design", {"status": "completed"})
        state = set_checkpoint_state(state, "paused")
        save_checkpoint(self.path, state)
        resumed = load_checkpoint(self.path, expected_task_id="agent-003")
        self.assertEqual(resumed["state"], "paused")
        self.assertEqual(resumed["completed_steps"], ["inspect-design"])
        resumed = set_checkpoint_state(resumed, "running")
        resumed = record_step(resumed, "validate-policy")
        save_checkpoint(self.path, resumed)
        final = load_checkpoint(self.path, expected_task_id="agent-003")
        self.assertEqual(final["completed_steps"], ["inspect-design", "validate-policy"])

    def test_refuses_resume_for_different_task(self):
        save_checkpoint(self.path, new_checkpoint("agent-003", "run-001"))
        with self.assertRaisesRegex(CheckpointError, "does not match"):
            load_checkpoint(self.path, expected_task_id="agent-004")

    def test_refuses_missing_or_corrupt_checkpoint(self):
        with self.assertRaisesRegex(CheckpointError, "does not exist"):
            load_checkpoint(self.path)
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{broken", encoding="utf-8")
        with self.assertRaisesRegex(CheckpointError, "invalid JSON"):
            load_checkpoint(self.path)

    def test_rejects_duplicate_completed_step(self):
        state = new_checkpoint("agent-003", "run-001")
        state = record_step(state, "one")
        with self.assertRaisesRegex(CheckpointError, "already recorded"):
            record_step(state, "one")

    def test_rejects_non_string_state_without_crashing(self):
        state = new_checkpoint("agent-003", "run-001")
        state["state"] = []
        with self.assertRaisesRegex(CheckpointError, "checkpoint state"):
            save_checkpoint(self.path, state)

    def test_rejects_invalid_state_transition(self):
        state = new_checkpoint("agent-003", "run-001")
        state = set_checkpoint_state(state, "completed")
        with self.assertRaisesRegex(CheckpointError, "transition"):
            set_checkpoint_state(state, "running")

    def test_exclusive_lock_blocks_second_run(self):
        with exclusive_run_lock(self.lock, "run-001"):
            self.assertTrue(self.lock.exists())
            with self.assertRaisesRegex(CheckpointError, "another run owns"):
                with exclusive_run_lock(self.lock, "run-002"):
                    self.fail("second lock acquisition must not happen")
        self.assertFalse(self.lock.exists())

    def test_lock_is_released_after_exception(self):
        with self.assertRaisesRegex(RuntimeError, "test failure"):
            with exclusive_run_lock(self.lock, "run-001"):
                raise RuntimeError("test failure")
        self.assertFalse(self.lock.exists())

    def test_rejects_unsupported_last_result_fields(self):
        state = new_checkpoint("agent-003", "run-001")
        state["last_result"] = {"shell": "must not be stored"}
        with self.assertRaisesRegex(CheckpointError, "last_result"):
            save_checkpoint(self.path, state)

    def test_rejects_oversized_checkpoint_file(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(" " * 256001, encoding="utf-8")
        with self.assertRaisesRegex(CheckpointError, "size limit"):
            load_checkpoint(self.path)

    def test_rejects_checkpoint_extra_fields(self):
        state = new_checkpoint("agent-003", "run-001")
        state["command"] = "arbitrary"
        with self.assertRaisesRegex(CheckpointError, "exact schema"):
            save_checkpoint(self.path, state)


if __name__ == "__main__":
    unittest.main()
