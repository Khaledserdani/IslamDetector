package com.islamdetector.aipro;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/** Local experiment store. Raw readings are retained before any model training. */
public final class ExperimentStore extends SQLiteOpenHelper {
    private static final String DB_NAME = "islam_detector_experiments.db";
    private static final int DB_VERSION = 1;

    public ExperimentStore(Context context) {
        super(context, DB_NAME, null, DB_VERSION);
    }

    @Override
    public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE samples (" +
                "_id INTEGER PRIMARY KEY AUTOINCREMENT," +
                "captured_at INTEGER NOT NULL," +
                "raw_json TEXT NOT NULL," +
                "raw_hash TEXT NOT NULL UNIQUE," +
                "window_count INTEGER NOT NULL DEFAULT 0," +
                "depth_cm REAL," +
                "calibrated INTEGER NOT NULL DEFAULT 0," +
                "feedback TEXT)");
        db.execSQL("CREATE INDEX samples_captured_at_idx ON samples(captured_at)");
    }

    @Override
    public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        // Schema migrations must preserve field data; never drop experiment history.
    }

    public synchronized long saveSampleIfNew(String rawJson, int windowCount,
                                             Double depthCm, boolean calibrated) {
        String hash = sha256(rawJson);
        SQLiteDatabase db = getWritableDatabase();
        Cursor existing = db.rawQuery("SELECT _id FROM samples WHERE raw_hash=?",
                new String[]{hash});
        try {
            if (existing.moveToFirst()) return existing.getLong(0);
        } finally {
            existing.close();
        }

        ContentValues values = new ContentValues();
        values.put("captured_at", System.currentTimeMillis());
        values.put("raw_json", rawJson);
        values.put("raw_hash", hash);
        values.put("window_count", windowCount);
        if (depthCm != null) values.put("depth_cm", depthCm);
        values.put("calibrated", calibrated ? 1 : 0);
        return db.insertOrThrow("samples", null, values);
    }

    public synchronized void saveFeedback(long sampleId, String feedback) {
        if (sampleId <= 0) return;
        ContentValues values = new ContentValues();
        values.put("feedback", feedback);
        getWritableDatabase().update("samples", values, "_id=?",
                new String[]{String.valueOf(sampleId)});
    }

    public synchronized int countSamples() {
        Cursor c = getReadableDatabase().rawQuery("SELECT COUNT(*) FROM samples", null);
        try {
            return c.moveToFirst() ? c.getInt(0) : 0;
        } finally {
            c.close();
        }
    }

    private String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder out = new StringBuilder();
            for (byte b : digest) out.append(String.format("%02x", b));
            return out.toString();
        } catch (Exception e) {
            return Integer.toHexString(value.hashCode());
        }
    }
}
