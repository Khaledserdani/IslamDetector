package com.islamlab.app;

import org.junit.Test;
import static org.junit.Assert.*;

public class LabMathTest {
    @Test public void computesSampleStatistics() {
        double[] stats = LabMath.summarize(new double[]{1, 2, 3});
        assertEquals(1.0, stats[0], 1e-9);
        assertEquals(3.0, stats[1], 1e-9);
        assertEquals(2.0, stats[2], 1e-9);
        assertEquals(2.0, stats[3], 1e-9);
        assertEquals(Math.sqrt(2.0 / 3.0), stats[4], 1e-9);
        assertEquals(3.0, stats[5], 1e-9);
    }
    @Test public void parsesCommaAndSpaceSeparatedValues() {
        assertArrayEquals(new double[]{1, 2.5, -3}, LabMath.parseSamples("1, 2.5 -3"), 1e-9);
    }
    @Test(expected = IllegalArgumentException.class)
    public void rejectsEmptySampleSet() { LabMath.summarize(new double[0]); }
    @Test public void computesPiMeasurementWindow() {
        assertEquals(450L, LabMath.totalWindowMicros(100, 150, 8, 25));
    }
}
