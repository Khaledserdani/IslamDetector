package com.islamfreeagent.app;

import java.time.LocalTime;

/** Local wall-clock window helper; the Android scheduler remains best-effort. */
final class AgentWorkWindow {
    static final String DEFAULT_START = "20:00";
    static final String DEFAULT_END = "06:00";

    private AgentWorkWindow() {}

    static boolean isOpen(LocalTime now, String startText, String endText) {
        if (now == null) throw new IllegalArgumentException("current time is required");
        final LocalTime start;
        final LocalTime end;
        try {
            start = LocalTime.parse(startText);
            end = LocalTime.parse(endText);
        } catch (RuntimeException error) {
            throw new IllegalArgumentException("work window must use HH:mm", error);
        }
        if (start.equals(end)) throw new IllegalArgumentException("work window cannot be 24 hours");
        if (start.isBefore(end)) return !now.isBefore(start) && now.isBefore(end);
        return !now.isBefore(start) || now.isBefore(end);
    }
}
