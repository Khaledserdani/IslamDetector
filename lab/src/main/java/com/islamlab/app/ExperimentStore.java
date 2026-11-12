package com.islamlab.app;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

import java.util.ArrayList;
import java.util.List;

/** Durable local experiment store. Raw CSV and source provenance are preserved verbatim. */
public final class ExperimentStore extends SQLiteOpenHelper {
    private static final String DB_NAME = "islam_lab_experiments.db";
    private static final int DB_VERSION = 1;
    private static final String TABLE = "experiments";

    public static final class Record {
        public final String id, name, csv, sourceType, acquisitionOrigin, measurementStatus;
        public final long createdEpochMs;
        Record(String id, String name, String csv, String sourceType, String acquisitionOrigin,
               String measurementStatus, long createdEpochMs) {
            this.id=id; this.name=name; this.csv=csv; this.sourceType=sourceType;
            this.acquisitionOrigin=acquisitionOrigin; this.measurementStatus=measurementStatus;
            this.createdEpochMs=createdEpochMs;
        }
    }

    public ExperimentStore(Context context) { super(context, DB_NAME, null, DB_VERSION); }

    @Override public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE " + TABLE + " (id TEXT PRIMARY KEY NOT NULL, name TEXT NOT NULL, csv TEXT NOT NULL, source_type TEXT NOT NULL, acquisition_origin TEXT NOT NULL, measurement_status TEXT NOT NULL, created_epoch_ms INTEGER NOT NULL, updated_epoch_ms INTEGER NOT NULL)");
        db.execSQL("CREATE INDEX idx_experiments_created ON " + TABLE + "(created_epoch_ms DESC)");
    }

    @Override public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        // Future schema migrations must preserve existing experiment rows.
    }

    public boolean save(String id, String name, String csv, long createdAt) {
        if (id == null || id.trim().isEmpty() || name == null || name.trim().isEmpty()
                || csv == null || csv.trim().isEmpty()) return false;
        ContentValues values = new ContentValues();
        values.put("id", id); values.put("name", name); values.put("csv", csv);
        values.put("source_type", metadata(csv, "source_type", "unknown"));
        values.put("acquisition_origin", metadata(csv, "acquisition_origin", "unknown"));
        values.put("measurement_status", metadata(csv, "measurement_status", "unknown"));
        values.put("created_epoch_ms", createdAt); values.put("updated_epoch_ms", System.currentTimeMillis());
        return getWritableDatabase().insertWithOnConflict(TABLE, null, values, SQLiteDatabase.CONFLICT_REPLACE) != -1;
    }

    public List<Record> list() {
        List<Record> records = new ArrayList<>();
        try (Cursor c = getReadableDatabase().query(TABLE,
                new String[]{"id","name","csv","source_type","acquisition_origin","measurement_status","created_epoch_ms"},
                null,null,null,null,"created_epoch_ms DESC")) {
            while (c.moveToNext()) records.add(new Record(c.getString(0),c.getString(1),c.getString(2),
                    c.getString(3),c.getString(4),c.getString(5),c.getLong(6)));
        }
        return records;
    }

    public Record get(String id) {
        try (Cursor c = getReadableDatabase().query(TABLE,
                new String[]{"id","name","csv","source_type","acquisition_origin","measurement_status","created_epoch_ms"},
                "id=?",new String[]{id},null,null,null)) {
            if (!c.moveToFirst()) return null;
            return new Record(c.getString(0),c.getString(1),c.getString(2),c.getString(3),
                    c.getString(4),c.getString(5),c.getLong(6));
        }
    }

    public boolean rename(String id, String name) {
        ContentValues v = new ContentValues(); v.put("name", name); v.put("updated_epoch_ms", System.currentTimeMillis());
        return getWritableDatabase().update(TABLE,v,"id=?",new String[]{id}) == 1;
    }

    public boolean delete(String id) {
        return getWritableDatabase().delete(TABLE,"id=?",new String[]{id}) == 1;
    }

    public int count() {
        try (Cursor c = getReadableDatabase().rawQuery("SELECT COUNT(*) FROM " + TABLE, null)) {
            return c.moveToFirst() ? c.getInt(0) : 0;
        }
    }

    /** One-time, idempotent migration from the previous SharedPreferences history. */
    public int migrateLegacy(java.util.Map<String, ?> legacy) {
        int migrated = 0;
        SQLiteDatabase db = getWritableDatabase();
        db.beginTransaction();
        try {
            for (String key : legacy.keySet()) {
                if (!key.startsWith("experiment_")) continue;
                Object raw = legacy.get(key);
                if (!(raw instanceof String)) continue;
                String csv = (String) raw;
                String nameValue = legacy.get("name_" + key) instanceof String
                        ? (String) legacy.get("name_" + key) : "تجربة " + key.substring("experiment_".length());
                long created = parseLong(key.substring("experiment_".length()), System.currentTimeMillis());
                ContentValues v = new ContentValues();
                v.put("id", key); v.put("name", nameValue); v.put("csv", csv);
                v.put("source_type", metadata(csv,"source_type","legacy_unknown"));
                v.put("acquisition_origin", metadata(csv,"acquisition_origin","legacy_storage"));
                v.put("measurement_status", metadata(csv,"measurement_status","legacy_unverified"));
                v.put("created_epoch_ms",created); v.put("updated_epoch_ms",System.currentTimeMillis());
                if (db.insertWithOnConflict(TABLE,null,v,SQLiteDatabase.CONFLICT_IGNORE) != -1) migrated++;
            }
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
        return migrated;
    }

    private static String metadata(String csv, String key, String fallback) {
        if (csv == null) return fallback;
        String prefix = key + ",";
        for (String line : csv.split("\\r?\\n")) {
            if (line.startsWith(prefix)) return line.substring(prefix.length()).trim();
        }
        return fallback;
    }

    private static long parseLong(String value, long fallback) {
        try { return Long.parseLong(value.replaceAll("[^0-9].*$","")); }
        catch (Exception ignored) { return fallback; }
    }
}
