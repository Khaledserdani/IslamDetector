package com.islamlab.app;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
public class PiPulseInputTest {
    private static final String VALID =
        "{\"paths_m\":{" +
        "\"TX\":[[0.12,0,0],[0,0.12,0],[-0.12,0,0],[0,-0.12,0],[0.12,0,0]]," +
        "\"RX\":[[0.10,0,0.015],[0,0.10,0.015],[-0.10,0,0.015],[0,-0.10,0.015],[0.10,0,0.015]]," +
        "\"target_loop\":[[0.04,0,-0.06],[0,0.04,-0.06],[-0.04,0,-0.06],[0,-0.04,-0.06],[0.04,0,-0.06]]}," +
        "\"turns\":{\"TX\":20,\"RX\":30,\"target_loop\":1}," +
        "\"electrical\":{\"tx_resistance_ohm\":1.52,\"tx_inductance_h\":0.00035,\"rx_inductance_h\":0.00075}," +
        "\"target\":{\"resistance_ohm\":0.08,\"inductance_h\":0.00002}," +
        "\"pulse\":{\"bus_voltage_v\":5,\"pulse_width_s\":0.0001,\"clamp_voltage_v\":20,\"time_step_s\":0.00000025,\"stop_time_s\":0.0006}}";

    @Test public void parsesCompletePulseConfiguration() throws Exception {
        PiPulseInput p=PiPulseInput.parse(VALID);
        assertEquals(20,p.txTurns);
        assertEquals(30,p.rxTurns);
        assertEquals(1,p.targetTurns);
        assertEquals(1.52,p.txResistance,0.0);
        assertEquals(20.0,p.clampVoltage,0.0);
    }

    @Test(expected=IllegalArgumentException.class)
    public void rejectsTimeGridAboveResourceLimit() throws Exception {
        PiPulseInput.parse(VALID.replace("\"time_step_s\":0.00000025","\"time_step_s\":0.000000001"));
    }

    @Test(expected=IllegalArgumentException.class)
    public void rejectsNegativeClampVoltage() throws Exception {
        PiPulseInput.parse(VALID.replace("\"clamp_voltage_v\":20","\"clamp_voltage_v\":-20"));
    }

    @Test(expected=IllegalArgumentException.class)
    public void rejectsZeroTurnCount() throws Exception {
        PiPulseInput.parse(VALID.replace("\"TX\":20","\"TX\":0"));
    }
}
