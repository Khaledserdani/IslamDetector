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
                "evaluation_runs", "evaluation_items", "deployment_events"};
        for (String table : tables) {
            try (Cursor c = db.rawQuery("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
                    new String[]{table})) {
                assertTrue(c.moveToFirst());
                assertEquals("missing table " + table, 1, c.getInt(0));
            }
        }
    }
}
