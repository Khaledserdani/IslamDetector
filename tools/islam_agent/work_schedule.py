"""Local-time work-window scheduler for the ISLAM agent."""
from __future__ import annotations

import threading
from datetime import datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

ALGIERS = ZoneInfo("Africa/Algiers")


def is_within_work_window(now: Optional[datetime] = None, start: str = "06:00", end: str = "14:00") -> bool:
    """Return True inside [start, end), using Africa/Algiers by default."""
    current = now or datetime.now(ALGIERS)
    if current.tzinfo is None:
        current = current.replace(tzinfo=ALGIERS)
    else:
        current = current.astimezone(ALGIERS)
    start_time, end_time = time.fromisoformat(start), time.fromisoformat(end)
    if start_time == end_time:
        raise ValueError("work window start and end cannot be equal")
    local_time = current.timetz().replace(tzinfo=None)
    if start_time < end_time:
        return start_time <= local_time < end_time
    # Overnight window, e.g. 20:00–06:00.
    return local_time >= start_time or local_time < end_time


class ScheduledWorker:
    """Starts/stops an existing worker as the configured local-time window opens/closes."""

    def __init__(self, start_worker, stop_worker, interval_seconds=300,
                 start="06:00", end="14:00", check_seconds=30, clock=None):
        if not 300 <= interval_seconds <= 86400:
            raise ValueError("interval_seconds must be between 300 and 86400")
        if check_seconds < 1:
            raise ValueError("check_seconds must be positive")
        self.start_worker = start_worker
        self.stop_worker = stop_worker
        self.interval_seconds = interval_seconds
        self.start = start
        self.end = end
        self.check_seconds = check_seconds
        self.clock = clock or (lambda: datetime.now(ALGIERS))
        self._active = None
        self._stop = threading.Event()
        self._thread = None

    def tick(self) -> bool:
        desired = is_within_work_window(self.clock(), self.start, self.end)
        if desired != self._active:
            if desired:
                self.start_worker(self.interval_seconds)
            else:
                self.stop_worker()
            self._active = desired
        return desired

    def run(self):
        while not self._stop.is_set():
            self.tick()
            self._stop.wait(self.check_seconds)

    def start_schedule(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self.run, name="islam-work-schedule", daemon=True)
        self._thread.start()

    def stop_schedule(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=max(1, self.check_seconds + 1))
        if self._active:
            self.stop_worker()
        self._active = False
