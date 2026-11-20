package com.islamfreeagent.app;

import org.junit.Test;
import java.time.LocalTime;
import static org.junit.Assert.*;

public class AgentWorkWindowTest {
    @Test public void defaultNightWindowCrossesMidnight() {
        assertFalse(AgentWorkWindow.isOpen(LocalTime.of(19, 59), "20:00", "06:00"));
        assertTrue(AgentWorkWindow.isOpen(LocalTime.of(20, 0), "20:00", "06:00"));
        assertTrue(AgentWorkWindow.isOpen(LocalTime.of(23, 59), "20:00", "06:00"));
        assertTrue(AgentWorkWindow.isOpen(LocalTime.MIDNIGHT, "20:00", "06:00"));
        assertTrue(AgentWorkWindow.isOpen(LocalTime.of(5, 59), "20:00", "06:00"));
        assertFalse(AgentWorkWindow.isOpen(LocalTime.of(6, 0), "20:00", "06:00"));
    }

    @Test public void daytimeWindowUsesStartInclusiveEndExclusive() {
        assertFalse(AgentWorkWindow.isOpen(LocalTime.of(5, 59), "06:00", "14:00"));
        assertTrue(AgentWorkWindow.isOpen(LocalTime.of(6, 0), "06:00", "14:00"));
        assertTrue(AgentWorkWindow.isOpen(LocalTime.of(13, 59), "06:00", "14:00"));
        assertFalse(AgentWorkWindow.isOpen(LocalTime.of(14, 0), "06:00", "14:00"));
    }

    @Test public void rejectsEqualOrInvalidWindow() {
        try {
            AgentWorkWindow.isOpen(LocalTime.NOON, "20:00", "20:00");
            fail("equal times must be rejected");
        } catch (IllegalArgumentException expected) { }
        try {
            AgentWorkWindow.isOpen(LocalTime.NOON, "bad", "06:00");
            fail("invalid times must be rejected");
        } catch (IllegalArgumentException expected) { }
    }
}
