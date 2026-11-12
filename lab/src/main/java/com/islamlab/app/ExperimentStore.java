package com.islamlab.app;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

import java.util.ArrayList;
import java.util.List;

/** Durable local experiment store. Raw CSV is preserved alongside searchable metadata. */
public final class ExperimentStore extends SQLiteOpenHelper {
    private static final String DB_NAME = "islam_lab_experiments.db";
    private static final int DB_VERSION = 2;
    private static final String TABLE = "experiments";
    private static final String[] RECORD_COLUMNS = {
            "id", "name", "csv", "source_type", "acquisition_origin", "measurement_status",
            "created_epoch_ms", "schema_version", "verification_status", "measurement_unit",
            "measurement_quantity", "sample_count", "device_id", "firmware_version", "soil_type"
    };

    public static final class Record {
        public final String id, name, csv, sourceType, acquisitionOrigin, measurementStatus;
        public final String schemaVersion, verificationStatus, measurementUnit, measurementQuantity;
        public final String deviceId, firmwareVersion, soilType;
        public final int sampleCount;
        public final long createdEpochMs;

        Record(Cursor c) {
            id=c.getString(0); name=c.getString(1); csv=c.getString(2);
            sourceType=c.getString(3); acquisitionOrigin=c.getString(4);
            measurementStatus=c.getString(5); createdEpochMs=c.getLong(6);
            schemaVersion=c.getString(7); verificationStatus=c.getString(8);
            measurementUnit=c.getString(9); measurementQuantity=c.getString(10);
            sampleCount=c.getInt(11); deviceId=c.getString(12);
            firmwareVersion=c.getString(13); soilType=c.getString(14);
        }
    }

    public ExperimentStore(Context context) { super(context, DB_NAME, null, DB_VERSION); }

    @Override public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE " + TABLE + " (id TEXT PRIMARY KEY NOT NULL, name TEXT NOT NULL, csv TEXT NOT NULL, source_type TEXT NOT NULL, acquisition_origin TEXT NOT NULL, measurement_status TEXT NOT NULL, created_epoch_ms INTEGER NOT NULL, updated_epoch_ms INTEGER NOT NULL, schema_version TEXT NOT NULL DEFAULT 'legacy_unknown', verification_status TEXT NOT NULL DEFAULT 'legacy_unverified', measurement_unit TEXT NOT NULL DEFAULT 'unknown', measurement_quantity TEXT NOT NULL DEFAULT 'unknown', sample_count INTEGER NOT NULL DEFAULT 0, device_id TEXT NOT NULL DEFAULT '', firmware_version TEXT NOT NULL DEFAULT '', soil_type TEXT NOT NULL DEFAULT '')");
        db.execSQL("CREATE INDEX idx_experiments_created ON " + TABLE + "(created_epoch_ms DESC)");
        db.execSQL("CREATE INDEX idx_experiments_source ON " + TABLE + "(source_type)");
        db.execSQL("CREATE INDEX idx_experiments_verification ON " + TABLE + "(verification_status)");
    }

    @Override public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        if (oldVersion < 2) {
            db.execSQL("ALTER TABLE " + TABLE + " ADD COLUMN schema_version TEXT NOT NULL DEFAULT 'legacy_unknown'");
            db.execSQL("ALTER TABLE " + TABLE + " ADD COLUMN verification_status TEXT NOT NULL DEFAULT 'legacy_unverified'");
            db.execSQL("ALTER TABLE " + TABLE + " ADD COLUMN measurement_unit TEXT NOT NULL DEFAULT 'unknown'");
            db.execSQL("ALTER TABLE " + TABLE + " ADD COLUMN measurement_quantity TEXT NOT NULL DEFAULT 'unknown'");
            db.execSQL("ALTER TABLE " + TABLE + " ADD COLUMN sample_count INTEGER NOT NULL DEFAULT 0");
            db.execSQL("ALTER TABLE " + TABLE + " ADD COLUMN device_id TEXT NOT NULL DEFAULT ''");
            db.execSQL("ALTER TABLE " + TABLE + " ADD COLUMN firmware_version TEXT NOT NULL DEFAULT ''");
            db.execSQL("ALTER TABLE " + TABLE + " ADD COLUMN soil_type TEXT NOT NULL DEFAULT ''");
            backfillMetadata(db);
            db.execSQL("CREATE INDEX IF NOT EXISTS idx_experiments_source ON " + TABLE + "(source_type)");
            db.execSQL("CREATE INDEX IF NOT EXISTS idx_experiments_verification ON " + TABLE + "(verification_status)");
        }
    }

    private static void backfillMetadata(SQLiteDatabase db) {
        List<String[]> rows = new ArrayList<>();
        try (Cursor c = db.query(TABLE, new String[]{"id", "csv"}, null, null, null, null, null)) {
            while (c.moveToNext()) rows.add(new String[]{c.getString(0), c.getString(1)});
        }
        for (String[] row : rows) {
            String csv = row[1];
            ContentValues v = new ContentValues();
            v.put("schema_version", metadata(csv, "schema_version", "legacy_unknown"));
            v.put("verification_status", metadata(csv, "verification.status",
                    metadata(csv, "measurement_status", "legacy_unverified")));
            v.put("measurement_unit", metadata(csv, "measurement.unit", metadata(csv, "unit", "unknown")));
            v.put("measurement_quantity", metadata(csv, "measurement.quantity", "unknown"));
            v.put("device_id", metadata(csv, "source.device_id", ""));
            v.put("firmware_version", metadata(csv, "source.firmware_version", ""));
            v.put("soil_type", metadata(csv, "soil.type", ""));
            ExperimentCsvValidator.Report report = ExperimentCsvValidator.validate(csv);
            v.put("sample_count", report.valid ? report.sampleCount : 0);
            db.update(TABLE, v, "id=?", new String[]{row[0]});
        }
    }

    public boolean save(String id, String name, String csv, long createdAt) {
        if (id == null || id.trim().isEmpty() || name == null || name.trim().isEmpty()
                || csv == null || csv.trim().isEmpty()) return false;
        ExperimentCsvValidator.Report report = ExperimentCsvValidator.validate(csv);
        String schema = metadata(csv, "schema_version", "legacy_unknown");
        if ("1.0.0".equals(schema) && !report.valid) return false;
        String source = metadata(csv, "source.type", metadata(csv, "source_type", "unknown"));
        String origin = metadata(csv, "source.origin", metadata(csv, "acquisition_origin", "unknown"));
        String verification = metadata(csv, "verification.status",
                metadata(csv, "measurement_status", "legacy_unverified"));
        ContentValues values = new ContentValues();
        values.put("id", id); values.put("name", name); values.put("csv", csv);
        values.put("source_type", source); values.put("acquisition_origin", origin);
        values.put("measurement_status", verification);
        values.put("created_epoch_ms", createdAt); values.put("updated_epoch_ms", System.currentTimeMillis());
        values.put("schema_version", metadata(csv, "schema_version", "legacy_unknown"));
        values.put("verification_status", verification);
        values.put("measurement_unit", metadata(csv, "measurement.unit", metadata(csv, "unit", "unknown")));
        values.put("measurement_quantity", metadata(csv, "measurement.quantity", "unknown"));
        values.put("sample_count", report.valid ? report.sampleCount : 0);
        values.put("device_id", metadata(csv, "source.device_id", ""));
        values.put("firmware_version", metadata(csv, "source.firmware_version", ""));
        values.put("soil_type", metadata(csv, "soil.type", ""));
        return getWritableDatabase().insertWithOnConflict(TABLE, null, values, SQLiteDatabase.CONFLICT_REPLACE) != -1;
    }

    public List<Record> list() {
        List<Record> records = new ArrayList<>();
        try (Cursor c = getReadableDatabase().query(TABLE, RECORD_COLUMNS,
                null,null,null,null,"created_epoch_ms DESC")) {
            while (c.moveToNext()) records.add(new Record(c));
        }
        return records;
    }

    public List<Record> listBySource(String sourceType) {
        List<Record> records = new ArrayList<>();
        try (Cursor c = getReadableDatabase().query(TABLE, RECORD_COLUMNS,
                "source_type=?",new String[]{sourceType},null,null,"created_epoch_ms DESC")) {
            while (c.moveToNext()) records.add(new Record(c));
        }
        return records;
    }

    public List<Record> listByVerification(String status) {
        List<Record> records = new ArrayList<>();
        try (Cursor c = getReadableDatabase().query(TABLE, RECORD_COLUMNS,
                "verification_status=?",new String[]{status},null,null,"created_epoch_ms DESC")) {
            while (c.moveToNext()) records.add(new Record(c));
        }
        return records;
    }

    public Record get(String id) {
        try (Cursor c = getReadableDatabase().query(TABLE, RECORD_COLUMNS,
                "id=?",new String[]{id},null,null,null)) {
            return c.moveToFirst() ? new Record(c) : null;
        }
    }

    public boolean rename(String id, String name) {
        if (id == null || id.trim().isEmpty() || name == null || name.trim().isEmpty()) return false;
        ContentValues v = new ContentValues(); v.put("name", name.trim()); v.put("updated_epoch_ms", System.currentTimeMillis());
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
        if (legacy == null || legacy.isEmpty()) return 0;
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
                v.put("schema_version", metadata(csv,"schema_version","legacy_unknown"));
                v.put("verification_status", metadata(csv,"verification.status",metadata(csv,"measurement_status","legacy_unverified")));
                v.put("measurement_unit", metadata(csv,"measurement.unit",metadata(csv,"unit","unknown")));
                v.put("measurement_quantity", metadata(csv,"measurement.quantity","unknown"));
                v.put("sample_count", ExperimentCsvValidator.validate(csv).sampleCount);
                v.put("device_id", metadata(csv,"source.device_id",""));
                v.put("firmware_version", metadata(csv,"source.firmware_version",""));
                v.put("soil_type", metadata(csv,"soil.type",""));
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
