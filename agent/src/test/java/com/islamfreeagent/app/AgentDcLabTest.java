package com.islamfreeagent.app;

import org.junit.Test;
import java.util.Arrays;
import static org.junit.Assert.*;

public class AgentDcLabTest {
    @Test public void solvesTwoEqualResistorsAsFiveVoltDivider() {
        AgentDcLab.Result result = AgentDcLab.solve("0", "vcc", 10.0, Arrays.asList(
                new AgentDcLab.Resistor("vcc", "mid", 1000.0),
                new AgentDcLab.Resistor("mid", "0", 1000.0)));
        assertEquals(5.0, result.nodeVoltages.get("mid"), 1e-9);
        assertEquals(0.005, result.sourceCurrentAmps, 1e-9);
        assertTrue(result.maximumKclResidualAmps < 1e-10);
    }

    @Test public void solvesParallelBranches() {
        AgentDcLab.Result result = AgentDcLab.solve("0", "vcc", 12.0, Arrays.asList(
                new AgentDcLab.Resistor("vcc", "0", 1000.0),
                new AgentDcLab.Resistor("vcc", "0", 2000.0)));
        assertEquals(0.018, result.sourceCurrentAmps, 1e-9);
        assertEquals(0.0, result.maximumKclResidualAmps, 1e-10);
    }

    @Test public void rejectsFloatingNetwork() {
        try {
            AgentDcLab.solve("0", "vcc", 5.0, Arrays.asList(
                    new AgentDcLab.Resistor("vcc", "a", 1000.0),
                    new AgentDcLab.Resistor("b", "0", 1000.0),
                    new AgentDcLab.Resistor("c", "d", 1000.0)));
            fail("floating network must fail");
        } catch (IllegalArgumentException expected) {
            assertTrue(expected.getMessage().contains("singular"));
        }
    }

    @Test public void rejectsInvalidResistance() {
        try {
            AgentDcLab.solve("0", "vcc", 5.0, Arrays.asList(
                    new AgentDcLab.Resistor("vcc", "0", 0.0)));
            fail("zero resistance must fail");
        } catch (IllegalArgumentException expected) {
            assertTrue(expected.getMessage().contains("resistance"));
        }
    }
}
