package com.islamfreeagent.app;

import org.junit.Test;
import static org.junit.Assert.*;

public class AgentWorkWindowTest {
    @Test public void defaultNightWindowCrossesMidnight() {
        assertFalse(AgentWorkWindow.isOpen(19 * 60 + 59, "20:00", "06:00"));
        assertTrue(AgentWorkWindow.isOpen(20 * 60, "20:00", "06:00"));
        assertTrue(AgentWorkWindow.isOpen(23 * 60 + 59, "20:00", "06:00"));
        assertTrue(AgentWorkWindow.isOpen(0, "20:00", "06:00"));
        assertTrue(AgentWorkWindow.isOpen(5 * 60 + 59, "20:00", "06:00"));
        assertFalse(AgentWorkWindow.isOpen(6 * 60, "20:00", "06:00"));
    }

    @Test public void daytimeWindowUsesStartInclusiveEndExclusive() {
        assertFalse(AgentWorkWindow.isOpen(5 * 60 + 59, "06:00", "14:00"));
        assertTrue(AgentWorkWindow.isOpen(6 * 60, "06:00", "14:00"));
        assertTrue(AgentWorkWindow.isOpen(13 * 60 + 59, "06:00", "14:00"));
        assertFalse(AgentWorkWindow.isOpen(14 * 60, "06:00", "14:00"));
    }

    @Test public void rejectsEqualOrInvalidWindow() {
        try {
            AgentWorkWindow.isOpen(12 * 60, "20:00", "20:00");
            fail("equal times must be rejected");
        } catch (IllegalArgumentException expected) { }
        try {
            AgentWorkWindow.isOpen(12 * 60, "bad", "06:00");
            fail("invalid times must be rejected");
        } catch (IllegalArgumentException expected) { }
    }
}
