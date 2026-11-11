package com.islamlab.app;

import org.junit.Test;
import static org.junit.Assert.*;

public class ExperimentDataTest {
    @Test public void parsesCommaAndNewlineSeparatedMeasurements() {
        assertArrayEquals(new double[]{12.5, 11.0, -2.25}, ExperimentData.parse("12.5, 11.0\n-2.25"), 1e-9);
    }

    @Test public void skipsMetadataAndReadsExplicitCsvValueColumn() {
        String csv = "source_type,user_measurement\nunit,mV\nindex,value\n1,10.0\n2,8.5\n3,7.0\n";
        assertArrayEquals(new double[]{10.0, 8.5, 7.0}, ExperimentData.parse(csv), 1e-9);
    }

    @Test public void exportedCsvCanBeParsedAgainWithoutLosingSamples() {
        double[] original = new double[]{1.25, 2.5, -3.75};
        assertArrayEquals(original, ExperimentData.parse(ExperimentData.toCsv(original)), 1e-9);
    }

    @Test public void exportsUnitAndSummaryInCsv() {
        String csv = ExperimentData.toCsv(new double[]{1, 2, 3});
        assertTrue(csv.contains("unit,mV"));
        assertTrue(csv.contains("mean,2.00000000"));
        assertTrue(csv.contains("index,value\n1,1.00000000"));
    }

    @Test(expected = IllegalArgumentException.class)
    public void rejectsOneMeasurement() { ExperimentData.parse("4.2"); }

    @Test(expected = IllegalArgumentException.class)
    public void rejectsMalformedRowsInsteadOfSilentlyDroppingThem() {
        ExperimentData.parse("index,value\n1,10.0\n2,not-a-number\n3,8.0");
    }

    @Test(expected = IllegalArgumentException.class)
    public void rejectsNonFiniteMeasurements() { ExperimentData.parse("1,NaN,3"); }
}
