package com.islamlab.app;

import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteConstraintException;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteException;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;

import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
public class ScientificCaptureStoreTest {
    private Context context;
    private ExperimentStore owner;
    private ScientificCaptureStore store;

    @Before public void setUp() {
        context = RuntimeEnvironment.getApplication();
        context.deleteDatabase("islam_lab_experiments.db");
        owner = new ExperimentStore(context);
        store = new ScientificCaptureStore(owner);
    }

    @After public void tearDown() {
        owner.close();
        context.deleteDatabase("islam_lab_experiments.db");
    }

    private ScientificCaptureStore.CaptureInput capture(String id, long sequence, String source, byte[] bytes) {
        return new ScientificCaptureStore.CaptureInput(id, "session-A", sequence, source,
                "u8-test-v1", bytes, 2, "complete", 1000L + sequence);
    }

    private ScientificCaptureStore.ReviewInput review(String eventId, String captureId,
            String oldLife, String newLife, String oldTruth, String newTruth,
            String evidenceType, String evidenceRef) {
        return new ScientificCaptureStore.ReviewInput(eventId, captureId, "reviewer-test",
                oldLife, newLife, oldTruth, newTruth, "test_reason", "test note",
                evidenceType, evidenceRef, 2000L);
    }

    @Test public void identicalPayloadsWithDifferentCaptureIdentityRemainSeparate() {
        byte[] payload = new byte[]{1, 2, 3, 4};
        String hash1 = store.insertCapture(capture("capture-1", 1, "instrument", payload));
        String hash2 = store.insertCapture(capture("capture-2", 2, "instrument", payload));
        assertEquals(hash1, hash2);
        try (Cursor c = owner.scientificReadableDatabase().rawQuery(
                "SELECT COUNT(*) FROM captures WHERE payload_sha256=?", new String[]{hash1})) {
            assertTrue(c.moveToFirst());
            assertEquals(2, c.getInt(0));
        }
    }

    @Test(expected = SQLiteConstraintException.class)
    public void duplicateCaptureIdNeverReplacesExistingRawData() {
        store.insertCapture(capture("same-id", 1, "instrument", new byte[]{1, 2}));
        store.insertCapture(capture("same-id", 2, "instrument", new byte[]{9, 9}));
    }

    @Test public void reviewCorrectionsAppendHistoryWithoutChangingRawPayload() {
        byte[] payload = new byte[]{5, 4, 3, 2, 1};
        String hash = store.insertCapture(capture("reviewed-capture", 7, "instrument", payload));
        store.appendReviewEvent(review("event-1", "reviewed-capture",
                "CAPTURED", "NEEDS_REVIEW", "UNKNOWN", "UNKNOWN", null, null));
        store.appendReviewEvent(review("event-2", "reviewed-capture",
                "NEEDS_REVIEW", "REVIEWED", "UNKNOWN", "UNKNOWN", null, null));

        SQLiteDatabase db = owner.scientificReadableDatabase();
        try (Cursor c = db.rawQuery("SELECT COUNT(*) FROM review_events WHERE capture_id=?",
                new String[]{"reviewed-capture"})) {
            assertTrue(c.moveToFirst());
            assertEquals(2, c.getInt(0));
        }
        try (Cursor c = db.rawQuery("SELECT previous_lifecycle_status,previous_event_id "
                + "FROM review_events WHERE event_id='event-2'", null)) {
            assertTrue(c.moveToFirst());
            assertEquals("NEEDS_REVIEW", c.getString(0));
            assertEquals("event-1", c.getString(1));
        }
        try (Cursor c = db.rawQuery("SELECT payload_sha256,payload_blob FROM captures "
                + "WHERE capture_id='reviewed-capture'", null)) {
            assertTrue(c.moveToFirst());
            assertEquals(hash, c.getString(0));
            assertArrayEquals(payload, c.getBlob(1));
        }
    }

    @Test(expected = IllegalArgumentException.class)
    public void syntheticCaptureCannotBeConfirmedAsGroundTruth() {
        store.insertCapture(capture("synthetic-capture", 3, "synthetic", new byte[]{1, 2}));
        store.appendReviewEvent(review("synthetic-review", "synthetic-capture",
                "CAPTURED", "REVIEWED", "UNKNOWN", "CONFIRMED", "excavation", "field-note-1"));
    }

    @Test(expected = IllegalArgumentException.class)
    public void groundTruthConfirmationRequiresEvidenceReference() {
        store.insertCapture(capture("instrument-capture", 4, "instrument", new byte[]{1, 2}));
        store.appendReviewEvent(review("no-evidence", "instrument-capture",
                "CAPTURED", "REVIEWED", "UNKNOWN", "CONFIRMED", null, null));
    }

    @Test(expected = SQLiteException.class)
    public void databaseTriggerBlocksDirectCaptureUpdate() {
        store.insertCapture(capture("immutable-capture", 5, "instrument", new byte[]{1, 2}));
        owner.scientificWritableDatabase().execSQL(
                "UPDATE captures SET payload_length_bytes=99 WHERE capture_id='immutable-capture'");
    }

    @Test public void v3SchemaIsCreatedAlongsideLegacyExperimentsTable() {
        SQLiteDatabase db = owner.scientificReadableDatabase();
        String[] tables = {"experiments", "captures", "review_events", "analysis_runs",
                "evaluation_runs", "evaluation_items", "evaluation_decisions", "deployment_events"};
        for (String table : tables) {
            try (Cursor c = db.rawQuery("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
                    new String[]{table})) {
                assertTrue(c.moveToFirst());
                assertEquals("missing table " + table, 1, c.getInt(0));
            }
        }
    }

    @Test public void upgradesVersionTwoDatabaseWithoutChangingLegacyCsv() {
        owner.close();
        java.io.File dbFile = context.getDatabasePath("islam_lab_experiments.db");
        SQLiteDatabase oldDb = SQLiteDatabase.openOrCreateDatabase(dbFile, null);
        oldDb.execSQL("CREATE TABLE experiments (id TEXT PRIMARY KEY NOT NULL, name TEXT NOT NULL, "
                + "csv TEXT NOT NULL, source_type TEXT NOT NULL, acquisition_origin TEXT NOT NULL, "
                + "measurement_status TEXT NOT NULL, created_epoch_ms INTEGER NOT NULL, "
                + "updated_epoch_ms INTEGER NOT NULL, schema_version TEXT NOT NULL DEFAULT 'legacy_unknown', "
                + "verification_status TEXT NOT NULL DEFAULT 'legacy_unverified', "
                + "measurement_unit TEXT NOT NULL DEFAULT 'unknown', "
                + "measurement_quantity TEXT NOT NULL DEFAULT 'unknown', sample_count INTEGER NOT NULL DEFAULT 0, "
                + "device_id TEXT NOT NULL DEFAULT '', firmware_version TEXT NOT NULL DEFAULT '', "
                + "soil_type TEXT NOT NULL DEFAULT '')");
        String csv = "schema_version,1.1\nsource_type,user_provided\nindex,value\n1,2\n2,3\n";
        android.content.ContentValues row = new android.content.ContentValues();
        row.put("id", "v2-row"); row.put("name", "سجل إصدار 2"); row.put("csv", csv);
        row.put("source_type", "user_provided"); row.put("acquisition_origin", "legacy_import");
        row.put("measurement_status", "legacy_unverified"); row.put("created_epoch_ms", 44L);
        row.put("updated_epoch_ms", 55L); row.put("schema_version", "1.1");
        row.put("verification_status", "legacy_unverified"); row.put("measurement_unit", "mV");
        row.put("measurement_quantity", "unknown"); row.put("sample_count", 2);
        row.put("device_id", ""); row.put("firmware_version", ""); row.put("soil_type", "");
        oldDb.insertOrThrow("experiments", null, row);
        oldDb.setVersion(2);
        oldDb.close();

        owner = new ExperimentStore(context);
        ExperimentStore.Record restored = owner.get("v2-row");
        assertNotNull(restored);
        assertEquals(csv, restored.csv);
        assertEquals("سجل إصدار 2", restored.name);
        assertEquals(44L, restored.createdEpochMs);
        for (String table : new String[]{"captures", "review_events", "analysis_runs",
                "evaluation_runs", "evaluation_items", "evaluation_decisions", "deployment_events"}) {
            try (Cursor cursor = owner.scientificReadableDatabase().rawQuery(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
                    new String[]{table})) {
                assertTrue(cursor.moveToFirst());
                assertEquals("missing migrated table " + table, 1, cursor.getInt(0));
            }
        }
    }


    @Test public void analysisRequiresExactRawCaptureDigest() {
        String hash = store.insertCapture(capture("analysis-capture", 8, "instrument", new byte[]{8, 7, 6}));
        try {
            store.appendAnalysisRun(new ScientificCaptureStore.AnalysisInput(
                    "analysis-bad", "analysis-capture", "0000000000000000000000000000000000000000000000000000000000000000", "pi-decay", "0.1",
                    null, "{}", "{}", 3000L, 3100L, "complete"));
            fail("Expected digest mismatch");
        } catch (IllegalArgumentException expected) { }
        store.appendAnalysisRun(new ScientificCaptureStore.AnalysisInput(
                "analysis-good", "analysis-capture", hash, "pi-decay", "0.1",
                null, "{\"window\":8}", "{\"score\":0.72}", 3000L, 3100L, "complete"));
        try (Cursor c = owner.scientificReadableDatabase().rawQuery(
                "SELECT COUNT(*) FROM analysis_runs WHERE capture_id='analysis-capture'", null)) {
            assertTrue(c.moveToFirst());
            assertEquals(1, c.getInt(0));
        }
    }

    @Test public void evaluationRejectsRelatedGroupAcrossTrainAndTest() {
        store.insertCapture(capture("eval-a", 11, "instrument", new byte[]{1}));
        store.insertCapture(capture("eval-b", 12, "instrument", new byte[]{2}));
        java.util.List<ScientificCaptureStore.EvaluationItemInput> items = new java.util.ArrayList<>();
        items.add(new ScientificCaptureStore.EvaluationItemInput(
                "item-a", "eval-a", "train", "same-target-session", null, null));
        items.add(new ScientificCaptureStore.EvaluationItemInput(
                "item-b", "eval-b", "test", "same-target-session", null, null));
        try {
            store.appendEvaluation(new ScientificCaptureStore.EvaluationInput(
                    "eval-leak", "{}", null, null, "candidate", "1.0",
                    "{\"accuracy\":0.9}", "FIELD_CANDIDATE", 4000L, items));
            fail("Expected group split rejection");
        } catch (IllegalArgumentException expected) { }
    }

    @Test public void activationRequiresPromotingEvaluationForSameCandidate() {
        store.insertCapture(capture("eval-capture", 13, "instrument", new byte[]{3}));
        store.appendReviewEvent(review("eval-review", "eval-capture",
                "CAPTURED", "ELIGIBLE_FOR_TRAINING", "UNKNOWN", "CONFIRMED",
                "excavation_record", "field-case-13"));
        java.util.List<ScientificCaptureStore.EvaluationItemInput> items = new java.util.ArrayList<>();
        items.add(new ScientificCaptureStore.EvaluationItemInput(
                "eval-item", "eval-capture", "test", "target-13", null, "{\"score\":0.8}"));
        store.appendEvaluation(new ScientificCaptureStore.EvaluationInput(
                "eval-approved", "{\"dataset\":\"sealed-v1\"}", "champion", "1.0",
                "candidate", "2.0", "{\"accuracy\":0.95}", "FIELD_CANDIDATE", 5000L, items));
        store.appendEvaluationDecision("approval-1", "eval-approved", "PROMOTE",
                "ISLAM-RELEASE-GATE", "1.0", "reviewer-1",
                "independent held-out field test passed", "review-report-13", 5500L);
        store.appendDeploymentEvent(new ScientificCaptureStore.DeploymentInput(
                "deploy-1", "champion", "1.0", "candidate", "2.0", null,
                "activate", "independent evaluation passed", "operator", 6000L, "eval-approved"));
        try (Cursor c = owner.scientificReadableDatabase().rawQuery(
                "SELECT COUNT(*) FROM deployment_events WHERE action='activate'", null)) {
            assertTrue(c.moveToFirst());
            assertEquals(1, c.getInt(0));
        }
    }


    @Test public void promotionEvaluationRejectsUnconfirmedCapture() {
        store.insertCapture(capture("unconfirmed-eval", 14, "instrument", new byte[]{4}));
        java.util.List<ScientificCaptureStore.EvaluationItemInput> items = new java.util.ArrayList<>();
        items.add(new ScientificCaptureStore.EvaluationItemInput(
                "unconfirmed-item", "unconfirmed-eval", "test", "field-case-14", null, null));
        try {
            store.appendEvaluation(new ScientificCaptureStore.EvaluationInput(
                    "unconfirmed-run", "{}", null, null, "candidate", "3.0",
                    "{\"accuracy\":0.99}", "FIELD_CANDIDATE", 7000L, items));
            fail("Expected unconfirmed capture rejection");
        } catch (IllegalArgumentException expected) { }
    }

    @Test public void captureReadVerifiesOriginalBytesAndDigests() {
        byte[] payload = new byte[]{10, 20, 30, 40};
        store.insertCapture(capture("read-capture", 15, "instrument", payload));
        ScientificCaptureStore.CaptureRecord record = store.getCapture("read-capture");
        assertNotNull(record);
        assertArrayEquals(payload, record.payload);
        assertEquals(payload.length, record.payload.length);
    }


    @Test public void deploymentCannotActivateBeforeExplicitApprovalEvent() {
        store.insertCapture(capture("pending-capture", 16, "instrument", new byte[]{6}));
        store.appendReviewEvent(review("pending-review", "pending-capture",
                "CAPTURED", "ELIGIBLE_FOR_TRAINING", "UNKNOWN", "CONFIRMED",
                "excavation_record", "field-case-16"));
        java.util.List<ScientificCaptureStore.EvaluationItemInput> items = new java.util.ArrayList<>();
        items.add(new ScientificCaptureStore.EvaluationItemInput(
                "pending-item", "pending-capture", "test", "field-case-16", null, null));
        store.appendEvaluation(new ScientificCaptureStore.EvaluationInput(
                "pending-run", "{}", null, null, "candidate", "4.0",
                "{\"accuracy\":0.97}", "FIELD_CANDIDATE", 8000L, items));
        try {
            store.appendDeploymentEvent(new ScientificCaptureStore.DeploymentInput(
                    "pending-deploy", null, null, "candidate", "4.0", null,
                    "activate", "attempt without approval", "operator", 9000L, "pending-run"));
            fail("Expected approval gate");
        } catch (IllegalArgumentException expected) { }
    }


    @Test public void promotionEvaluationRejectsIncompleteCapturePayload() {
        store.insertCapture(new ScientificCaptureStore.CaptureInput(
                "partial-capture", "session-A", 17, "instrument",
                "u8-test-v1", new byte[]{7, 8}, 0, "incomplete", 1017L));
        store.appendReviewEvent(review("partial-review", "partial-capture",
                "CAPTURED", "ELIGIBLE_FOR_TRAINING", "UNKNOWN", "CONFIRMED",
                "field_record", "partial-case"));
        java.util.List<ScientificCaptureStore.EvaluationItemInput> items = new java.util.ArrayList<>();
        items.add(new ScientificCaptureStore.EvaluationItemInput(
                "partial-item", "partial-capture", "test", "partial-case", null, null));
        try {
            store.appendEvaluation(new ScientificCaptureStore.EvaluationInput(
                    "partial-run", "{}", null, null, "candidate", "5.0",
                    "{\"accuracy\":0.99}", "FIELD_CANDIDATE", 10000L, items));
            fail("Expected incomplete payload rejection");
        } catch (IllegalArgumentException expected) { }
    }

    @Test public void captureReadReturnsFullAcquisitionMetadata() {
        store.insertCapture(new ScientificCaptureStore.CaptureInput(
                "metadata-capture", "session-meta", 21, "instrument",
                "2026-11-19T10:00:00Z", 12345L, 1000000L,
                "device-7", "stm32-fw-2", "esp-fw-3", "mono-spiral-35",
                "acq-config-9", "u16-le-v1", new byte[]{11, 12, 13}, 3,
                "complete", 21000L));
        ScientificCaptureStore.CaptureRecord record = store.getCapture("metadata-capture");
        assertNotNull(record);
        assertEquals("2026-11-19T10:00:00Z", record.capturedAtUtc);
        assertEquals(Long.valueOf(12345L), record.monotonicStartTick);
        assertEquals(Long.valueOf(1000000L), record.tickFrequencyHz);
        assertEquals("device-7", record.deviceId);
        assertEquals("stm32-fw-2", record.stm32Firmware);
        assertEquals("esp-fw-3", record.esp32Firmware);
        assertEquals("mono-spiral-35", record.coilProfileId);
        assertEquals("acq-config-9", record.acquisitionConfigId);
        assertEquals("complete", record.transportStatus);
        assertEquals("u16-le-v1", record.payloadFormat);
        assertEquals(3, record.sampleCount);
    }

    @Test public void captureCannotMoveBetweenTrainAndTestAcrossEvaluationRuns() {
        store.insertCapture(capture("reused-capture", 22, "instrument", new byte[]{22, 23}));
        java.util.List<ScientificCaptureStore.EvaluationItemInput> first =
                new java.util.ArrayList<>();
        first.add(new ScientificCaptureStore.EvaluationItemInput(
                "first-test-item", "reused-capture", "test", "case-22", null, null));
        store.appendEvaluation(new ScientificCaptureStore.EvaluationInput(
                "first-run", "{}", null, null, "candidate-a", "1",
                "{}", "SIMULATION_ONLY", 11000L, first));

        java.util.List<ScientificCaptureStore.EvaluationItemInput> second =
                new java.util.ArrayList<>();
        second.add(new ScientificCaptureStore.EvaluationItemInput(
                "second-train-item", "reused-capture", "train", "case-22", null, null));
        try {
            store.appendEvaluation(new ScientificCaptureStore.EvaluationInput(
                    "second-run", "{}", null, null, "candidate-b", "1",
                    "{}", "SIMULATION_ONLY", 12000L, second));
            fail("Expected cross-run train/test reuse guard");
        } catch (SQLiteException expected) { }
    }

}
