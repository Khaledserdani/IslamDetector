package com.islamlab.app;

import android.database.sqlite.SQLiteDatabase;

/** Additive schema for immutable scientific captures and append-only audit records. */
final class ScientificStorageSchema {
    private ScientificStorageSchema() {}

    static void create(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE IF NOT EXISTS captures ("
                + "capture_id TEXT PRIMARY KEY NOT NULL,"
                + "session_id TEXT NOT NULL,"
                + "sequence INTEGER NOT NULL CHECK(sequence >= 0),"
                + "source_type TEXT NOT NULL CHECK(source_type IN ('synthetic','user_provided','instrument','islam_detector')),"
                + "captured_at_utc TEXT,"
                + "monotonic_start_tick INTEGER,"
                + "tick_frequency_hz INTEGER CHECK(tick_frequency_hz IS NULL OR tick_frequency_hz > 0),"
                + "device_id TEXT, stm32_firmware TEXT, esp32_firmware TEXT,"
                + "coil_profile_id TEXT, acquisition_config_id TEXT,"
                + "payload_format TEXT NOT NULL,"
                + "payload_blob BLOB NOT NULL,"
                + "payload_length_bytes INTEGER NOT NULL CHECK(payload_length_bytes >= 0),"
                + "payload_crc32 TEXT NOT NULL,"
                + "payload_sha256 TEXT NOT NULL CHECK(length(payload_sha256)=64),"
                + "sample_count INTEGER NOT NULL CHECK(sample_count >= 0),"
                + "transport_status TEXT NOT NULL CHECK(transport_status IN ('complete','incomplete','corrupted')),"
                + "created_epoch_ms INTEGER NOT NULL,"
                + "UNIQUE(session_id, sequence))");
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_captures_session_sequence ON captures(session_id, sequence)");
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_captures_source_created ON captures(source_type, created_epoch_ms DESC)");

        db.execSQL("CREATE TABLE IF NOT EXISTS review_events ("
                + "event_id TEXT PRIMARY KEY NOT NULL,"
                + "capture_id TEXT NOT NULL REFERENCES captures(capture_id) ON DELETE RESTRICT,"
                + "event_time_epoch_ms INTEGER NOT NULL,"
                + "reviewer_id TEXT NOT NULL,"
                + "previous_lifecycle_status TEXT,"
                + "new_lifecycle_status TEXT NOT NULL CHECK(new_lifecycle_status IN "
                + "('CAPTURED','NEEDS_REVIEW','REVIEWED','ELIGIBLE_FOR_TRAINING','REJECTED','INCONCLUSIVE')),"
                + "previous_ground_truth_status TEXT,"
                + "new_ground_truth_status TEXT NOT NULL CHECK(new_ground_truth_status IN "
                + "('UNKNOWN','CONFIRMED','REJECTED','INCONCLUSIVE')),"
                + "reason_code TEXT NOT NULL, review_note TEXT, evidence_type TEXT, evidence_ref TEXT,"
                + "previous_event_id TEXT REFERENCES review_events(event_id) ON DELETE RESTRICT)");
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_review_events_capture_time ON review_events(capture_id, event_time_epoch_ms)");

        db.execSQL("CREATE TABLE IF NOT EXISTS analysis_runs ("
                + "analysis_run_id TEXT PRIMARY KEY NOT NULL,"
                + "capture_id TEXT NOT NULL REFERENCES captures(capture_id) ON DELETE RESTRICT,"
                + "input_payload_sha256 TEXT NOT NULL CHECK(length(input_payload_sha256)=64),"
                + "algorithm_id TEXT NOT NULL, algorithm_version TEXT NOT NULL, model_sha256 TEXT,"
                + "parameters_json TEXT NOT NULL, result_json TEXT,"
                + "started_epoch_ms INTEGER NOT NULL, completed_epoch_ms INTEGER,"
                + "run_status TEXT NOT NULL CHECK(run_status IN ('complete','failed','cancelled')))");
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_analysis_capture ON analysis_runs(capture_id, started_epoch_ms)");

        db.execSQL("CREATE TABLE IF NOT EXISTS evaluation_runs ("
                + "evaluation_run_id TEXT PRIMARY KEY NOT NULL,"
                + "dataset_manifest_json TEXT NOT NULL,"
                + "dataset_manifest_sha256 TEXT NOT NULL CHECK(length(dataset_manifest_sha256)=64),"
                + "champion_algorithm_id TEXT, champion_algorithm_version TEXT,"
                + "candidate_algorithm_id TEXT NOT NULL, candidate_algorithm_version TEXT NOT NULL,"
                + "metrics_json TEXT NOT NULL, decision TEXT NOT NULL,"
                + "created_epoch_ms INTEGER NOT NULL)");
        db.execSQL("CREATE TABLE IF NOT EXISTS evaluation_items ("
                + "evaluation_item_id TEXT PRIMARY KEY NOT NULL,"
                + "evaluation_run_id TEXT NOT NULL REFERENCES evaluation_runs(evaluation_run_id) ON DELETE RESTRICT,"
                + "capture_id TEXT NOT NULL REFERENCES captures(capture_id) ON DELETE RESTRICT,"
                + "split TEXT NOT NULL CHECK(split IN ('train','validation','test','shadow')),"
                + "group_key TEXT NOT NULL, expected_result_json TEXT, actual_result_json TEXT,"
                + "UNIQUE(evaluation_run_id, capture_id))");
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_evaluation_items_group ON evaluation_items(evaluation_run_id, group_key)");

        db.execSQL("CREATE TABLE IF NOT EXISTS deployment_events ("
                + "deployment_event_id TEXT PRIMARY KEY NOT NULL,"
                + "previous_algorithm_id TEXT, previous_algorithm_version TEXT,"
                + "new_algorithm_id TEXT NOT NULL, new_algorithm_version TEXT NOT NULL,"
                + "model_sha256 TEXT,"
                + "action TEXT NOT NULL CHECK(action IN ('activate','rollback','reject')),"
                + "reason TEXT NOT NULL, actor_id TEXT NOT NULL, event_time_epoch_ms INTEGER NOT NULL,"
                + "evaluation_run_id TEXT REFERENCES evaluation_runs(evaluation_run_id) ON DELETE RESTRICT)");

        createAppendOnlyTriggers(db, "captures");
        createAppendOnlyTriggers(db, "review_events");
        createAppendOnlyTriggers(db, "analysis_runs");
        createAppendOnlyTriggers(db, "evaluation_runs");
        createAppendOnlyTriggers(db, "evaluation_items");
        createAppendOnlyTriggers(db, "deployment_events");

        // A capture group must never leak across dataset splits in the same evaluation.
        db.execSQL("CREATE TRIGGER IF NOT EXISTS trg_evaluation_group_split_guard "
                + "BEFORE INSERT ON evaluation_items "
                + "WHEN EXISTS (SELECT 1 FROM evaluation_items old "
                + "WHERE old.evaluation_run_id=NEW.evaluation_run_id "
                + "AND old.group_key=NEW.group_key AND old.split<>NEW.split) "
                + "BEGIN SELECT RAISE(ABORT, 'evaluation group split conflict'); END");
    }

    private static void createAppendOnlyTriggers(SQLiteDatabase db, String table) {
        db.execSQL("CREATE TRIGGER IF NOT EXISTS trg_" + table + "_no_update "
                + "BEFORE UPDATE ON " + table + " BEGIN "
                + "SELECT RAISE(ABORT, '" + table + " is append-only'); END");
        db.execSQL("CREATE TRIGGER IF NOT EXISTS trg_" + table + "_no_delete "
                + "BEFORE DELETE ON " + table + " BEGIN "
                + "SELECT RAISE(ABORT, '" + table + " is append-only'); END");
    }
}
