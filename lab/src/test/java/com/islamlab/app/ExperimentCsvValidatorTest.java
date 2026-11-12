package com.islamlab.app;

import org.junit.Test;
import static org.junit.Assert.*;

public class ExperimentCsvValidatorTest {
    private static String strict(String source, String status, String samples) {
        return "schema_version,1.0.0\nexperiment_id,exp-001\ntitle,Test\ncreated_at_utc,2026-11-12T10:00:00Z\n"
                + "source.type," + source + "\nsource.origin,test_fixture\n"
                + "verification.status," + status + "\nmeasurement.quantity,voltage\nmeasurement.unit,mV\nmeasurement.sample_origin,test_fixture\n"
                + "sample_index,time_us,value\n" + samples;
    }

    @Test public void acceptsValidStrictRecordAndCountsSamples() {
        ExperimentCsvValidator.Report r = ExperimentCsvValidator.validate(
                strict("instrument", "unverified", "0,8,12.5\n1,12,11.0\n"));
        assertTrue(r.message, r.valid);
        assertEquals(2, r.sampleCount);
        assertEquals("instrument", r.sourceType);
    }

    @Test public void rejectsMissingRequiredMetadata() {
        String csv = "schema_version,1.0.0\ntitle,T\nsample_index,time_us,value\n0,1,2\n1,2,3\n";
        assertFalse(ExperimentCsvValidator.validate(csv).valid);
    }

    @Test public void rejectsSyntheticGroundTruthClaim() {
        assertFalse(ExperimentCsvValidator.validate(
                strict("synthetic", "ground_truth_confirmed", "0,8,1\n1,12,2\n")).valid);
    }

    @Test public void rejectsNonIncreasingTime() {
        assertFalse(ExperimentCsvValidator.validate(
                strict("instrument", "unverified", "0,8,1\n1,8,2\n")).valid);
    }

    @Test public void rejectsNonNumericAndIncompleteRows() {
        assertFalse(ExperimentCsvValidator.validate(
                strict("instrument", "unverified", "0,8,nope\n1,12,2\n")).valid);
        assertFalse(ExperimentCsvValidator.validate(
                strict("instrument", "unverified", "0,8,1\n1,\n")).valid);
    }

    @Test public void rejectsDeviceSourceWithoutIdentityAndFirmware() {
        assertFalse(ExperimentCsvValidator.validate(
                strict("islam_detector", "unverified", "0,8,1\n1,12,2\n")).valid);
    }

    @Test public void acceptsLegacyV11ExportsWithoutReclassifyingSource() {
        String csv = "schema_version,1.1\nsource_type,synthetic\nmeasurement_status,not_a_hardware_measurement\n"
                + "index,value\n1,10\n2,8\n";
        ExperimentCsvValidator.Report r = ExperimentCsvValidator.validate(csv);
        assertTrue(r.message, r.valid);
        assertEquals("synthetic", r.sourceType);
    }

    @Test public void rejectsEmptyAndOversizedRecords() {
        assertFalse(ExperimentCsvValidator.validate("").valid);
        assertFalse(ExperimentCsvValidator.validate(new String(new char[2_000_001]).replace('\0','x')).valid);
    }

    @Test public void acceptsLegacySummaryAfterBlankSeparator() {
        String csv = "schema_version,1.1\nsource_type,synthetic\nmeasurement_status,not_a_hardware_measurement\n"
                + "index,value\n1,10\n2,8\n\ncount,2\nmean,9\n";
        assertTrue(ExperimentCsvValidator.validate(csv).valid);
    }

    @Test public void rejectsRepeatedSampleIndex() {
        assertFalse(ExperimentCsvValidator.validate(
                strict("instrument", "unverified", "0,8,1\n0,12,2\n")).valid);
    }

}
