package com.islamfreeagent.app;

/** Local wall-clock window helper compatible with the app's minSdk 23. */
final class AgentWorkWindow {
    static final String DEFAULT_START = "20:00";
    static final String DEFAULT_END = "06:00";

    private AgentWorkWindow() {}

    static boolean isOpen(int minuteOfDay, String startText, String endText) {
        if (minuteOfDay < 0 || minuteOfDay >= 1440) {
            throw new IllegalArgumentException("minuteOfDay must be in [0, 1439]");
        }
        int start = parseMinute(startText);
        int end = parseMinute(endText);
        if (start == end) throw new IllegalArgumentException("work window cannot be 24 hours");
        if (start < end) return minuteOfDay >= start && minuteOfDay < end;
        return minuteOfDay >= start || minuteOfDay < end;
    }

    private static int parseMinute(String value) {
        if (value == null || !value.matches("(?:[01]?[0-9]|2[0-3]):[0-5][0-9]")) {
            throw new IllegalArgumentException("work window must use HH:mm");
        }
        String[] parts = value.split(":");
        return Integer.parseInt(parts[0]) * 60 + Integer.parseInt(parts[1]);
    }
}
