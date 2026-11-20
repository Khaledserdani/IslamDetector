import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from work_schedule import is_within_work_window, ScheduledWorker


class WorkScheduleTests(unittest.TestCase):
    def test_algiers_window_is_start_inclusive_end_exclusive(self):
        zone = ZoneInfo("Africa/Algiers")
        self.assertTrue(is_within_work_window(datetime(2026, 11, 20, 6, 0, tzinfo=zone)))
        self.assertTrue(is_within_work_window(datetime(2026, 11, 20, 13, 59, tzinfo=zone)))
        self.assertFalse(is_within_work_window(datetime(2026, 11, 20, 14, 0, tzinfo=zone)))
        self.assertFalse(is_within_work_window(datetime(2026, 11, 20, 5, 59, tzinfo=zone)))

    def test_scheduler_starts_and_stops_only_on_transitions(self):
        zone = ZoneInfo("Africa/Algiers")
        now = [datetime(2026, 11, 20, 5, 0, tzinfo=zone)]
        events = []
        scheduler = ScheduledWorker(lambda interval: events.append(("start", interval)),
                                    lambda: events.append(("stop", None)),
                                    clock=lambda: now[0])
        self.assertFalse(scheduler.tick())
        now[0] = datetime(2026, 11, 20, 6, 0, tzinfo=zone)
        self.assertTrue(scheduler.tick())
        scheduler.tick()
        now[0] = datetime(2026, 11, 20, 14, 0, tzinfo=zone)
        self.assertFalse(scheduler.tick())
        self.assertEqual(events, [("stop", None), ("start", 300), ("stop", None)])


if __name__ == "__main__":
    unittest.main()
