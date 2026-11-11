package com.islamlab.app;

import org.junit.Test;
import static org.junit.Assert.*;

public class ExperimentDataTest {
    @Test public void parsesCommaAndNewlineSeparatedMeasurements() {
        assertArrayEquals(new double[]{12.5, 11.0, -2.25}, ExperimentData.parse("12.5, 11.0\\n-2.25"), 1e-9);
    }
    @Test public void skipsCsvHeaderAndKeepsNumericColumn() {
        assertArrayEquals(new double[]{10.0, 8.5, 7.0}, ExperimentData.parse("index,value\\n1,10.0\\n2,8.5\\n3,7.0"), 1e-9);
    }
    @Test public void exportsUnitAndSummaryInCsv() {
        String csv = ExperimentData.toCsv(new double[]{1, 2, 3});
        assertTrue(csv.contains("unit,mV"));
        assertTrue(csv.contains("mean,2.00000000"));
    }
    @Test(expected = IllegalArgumentException.class)
    public void rejectsOneMeasurement() { ExperimentData.parse("4.2"); }
}