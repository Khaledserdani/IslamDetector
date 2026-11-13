package com.islamlab.app;

import org.json.JSONException;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
public class FilamentGeometryInputTest {
    private static final String VALID = "{"
            + "\"paths_m\":{"
            + "\"TX\":[[0.1,0,0],[0,0.1,0],[-0.1,0,0],[0,-0.1,0],[0.1,0,0]],"
            + "\"RX\":[[0.08,0,0.01],[0,0.08,0.01],[-0.08,0,0.01],[0,-0.08,0.01],[0.08,0,0.01]]},"
            + "\"turns\":{\"TX\":20,\"RX\":30},"
            + "\"tx_current_a\":1.5,"
            + "\"observation_points_m\":[[0,0,0.2],[0.02,0,0.2]],"
            + "\"wire_lengths_m\":{\"TX\":25,\"RX\":35}"
            + "}";

    @Test public void parsesCompleteGeometryAndWireBudgets() throws Exception {
        FilamentGeometryInput g=FilamentGeometryInput.parse(VALID);
        assertEquals(20,g.txTurns);
        assertEquals(30,g.rxTurns);
        assertEquals(1.5,g.txCurrentAmps,0.0);
        assertEquals(25.0,g.txWireLengthMetres,0.0);
        assertEquals(35.0,g.rxWireLengthMetres,0.0);
        assertEquals(2,g.observationPoints.length);
    }

    @Test(expected=IllegalArgumentException.class)
    public void rejectsNonPositiveTurnCount() throws Exception {
        FilamentGeometryInput.parse(VALID.replace("\"TX\":20","\"TX\":0"));
    }

    @Test(expected=JSONException.class)
    public void rejectsMissingReceiverPath() throws Exception {
        FilamentGeometryInput.parse(VALID.replace(",\"RX\":[[0.08,0,0.01],[0,0.08,0.01],[-0.08,0,0.01],[0,-0.08,0.01],[0.08,0,0.01]]",""));
    }

    @Test(expected=IllegalArgumentException.class)
    public void rejectsMalformedCoordinateDimension() throws Exception {
        FilamentGeometryInput.parse(VALID.replace("[0.1,0,0]","[0.1,0]"));
    }
}
