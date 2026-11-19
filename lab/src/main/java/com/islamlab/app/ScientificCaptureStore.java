package com.islamlab.app;

import android.content.ContentValues;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Locale;
import java.util.zip.CRC32;

/**
 * Append-only API for raw captures and human review history.
 * It deliberately exposes no update/delete operations.
 */
public final class ScientificCaptureStore {
    private final ExperimentStore owner;

    public ScientificCaptureStore(ExperimentStore owner) {
        if (owner == null) throw new IllegalArgumentException("ExperimentStore مطلوب");
        this.owner = owner;
    }

    public static final class CaptureInput {
        public final String captureId, sessionId, sourceType, capturedAtUtc, deviceId;
        public final String stm32Firmware, esp32Firmware, coilProfileId, acquisitionConfigId;
        public final String payloadFormat, transportStatus;
        public final long sequence, createdEpochMs;
        public final Long monotonicStartTick, tickFrequencyHz;
        public final int sampleCount;
        public final byte[] payload;

        public CaptureInput(String captureId, String sessionId, long sequence, String sourceType,
                            String payloadFormat, byte[] payload, int sampleCount,
                            String transportStatus, long createdEpochMs) {
            this(captureId, sessionId, sequence, sourceType, null, null, null, null,
                    null, null, null, null, payloadFormat, payload, sampleCount, transportStatus, createdEpochMs);
        }

        public CaptureInput(String captureId, String sessionId, long sequence, String sourceType,
                            String capturedAtUtc, Long monotonicStartTick, Long tickFrequencyHz,
                            String deviceId, String stm32Firmware, String esp32Firmware,
                            String coilProfileId, String acquisitionConfigId, String payloadFormat,
                            byte[] payload, int sampleCount, String transportStatus, long createdEpochMs) {
            this.captureId=captureId; this.sessionId=sessionId; this.sequence=sequence;
            this.sourceType=sourceType; this.capturedAtUtc=capturedAtUtc;
            this.monotonicStartTick=monotonicStartTick; this.tickFrequencyHz=tickFrequencyHz;
            this.deviceId=deviceId; this.stm32Firmware=stm32Firmware; this.esp32Firmware=esp32Firmware;
            this.coilProfileId=coilProfileId; this.acquisitionConfigId=acquisitionConfigId;
            this.payloadFormat=payloadFormat; this.payload=payload;
            this.sampleCount=sampleCount; this.transportStatus=transportStatus;
            this.createdEpochMs=createdEpochMs;
        }
    }

    public static final class CaptureRecord {
        public final String captureId, sessionId, sourceType, payloadFormat, payloadSha256, payloadCrc32;
        public final long sequence, createdEpochMs;
        public final int sampleCount;
        public final byte[] payload;
        CaptureRecord(Cursor c) {
            captureId=c.getString(0); sessionId=c.getString(1); sequence=c.getLong(2);
            sourceType=c.getString(3); payloadFormat=c.getString(4);
            payload=c.getBlob(5); payloadSha256=c.getString(6); payloadCrc32=c.getString(7);
            sampleCount=c.getInt(8); createdEpochMs=c.getLong(9);
        }
    }

    /** Reads the original bytes and verifies their stored length, CRC32 and SHA-256. */
    public CaptureRecord getCapture(String captureId) {
        if (isBlank(captureId)) throw new IllegalArgumentException("معرف الالتقاط مطلوب");
        try (Cursor c = owner.scientificReadableDatabase().rawQuery(
                "SELECT capture_id,session_id,sequence,source_type,payload_format,payload_blob,"
                + "payload_sha256,payload_crc32,sample_count,created_epoch_ms,payload_length_bytes "
                + "FROM captures WHERE capture_id=?", new String[]{captureId})) {
            if (!c.moveToFirst()) return null;
            CaptureRecord record = new CaptureRecord(c);
            if (record.payload == null || record.payload.length != c.getInt(10)
                    || !record.payloadSha256.equals(sha256(record.payload))
                    || !record.payloadCrc32.equals(crc32(record.payload)))
                throw new IllegalStateException("فشل التحقق من سلامة الالتقاط المخزن");
            return record;
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("تعذر التحقق من بصمة الالتقاط", ex);
        }
    }

    public static final class ReviewInput {
        public final String eventId, captureId, reviewerId;
        public final String expectedLifecycle, newLifecycle, expectedGroundTruth, newGroundTruth;
        public final String reasonCode, note, evidenceType, evidenceRef;
        public final long eventTimeEpochMs;

        public ReviewInput(String eventId, String captureId, String reviewerId,
                           String expectedLifecycle, String newLifecycle,
                           String expectedGroundTruth, String newGroundTruth,
                           String reasonCode, String note, String evidenceType,
                           String evidenceRef, long eventTimeEpochMs) {
            this.eventId=eventId; this.captureId=captureId; this.reviewerId=reviewerId;
            this.expectedLifecycle=expectedLifecycle; this.newLifecycle=newLifecycle;
            this.expectedGroundTruth=expectedGroundTruth; this.newGroundTruth=newGroundTruth;
            this.reasonCode=reasonCode; this.note=note; this.evidenceType=evidenceType;
            this.evidenceRef=evidenceRef; this.eventTimeEpochMs=eventTimeEpochMs;
        }
    }

    /** Inserts a capture exactly once. SHA-256 is computed here; no weak fallback is allowed. */
    public String insertCapture(CaptureInput input) {
        validateCapture(input);
        final String sha256;
        final String crc32;
        try {
            sha256 = sha256(input.payload);
            crc32 = crc32(input.payload);
        } catch (Exception ex) {
            throw new IllegalStateException("تعذر حساب بصمة الحمولة؛ أُلغي الحفظ", ex);
        }

        ContentValues v = new ContentValues();
        v.put("capture_id", input.captureId); v.put("session_id", input.sessionId);
        v.put("sequence", input.sequence); v.put("source_type", input.sourceType);
        v.put("captured_at_utc", input.capturedAtUtc);
        if (input.monotonicStartTick != null) v.put("monotonic_start_tick", input.monotonicStartTick);
        if (input.tickFrequencyHz != null) v.put("tick_frequency_hz", input.tickFrequencyHz);
        v.put("device_id", input.deviceId); v.put("stm32_firmware", input.stm32Firmware);
        v.put("esp32_firmware", input.esp32Firmware); v.put("coil_profile_id", input.coilProfileId);
        v.put("acquisition_config_id", input.acquisitionConfigId);
        v.put("payload_format", input.payloadFormat); v.put("payload_blob", input.payload);
        v.put("payload_length_bytes", input.payload.length); v.put("payload_crc32", crc32);
        v.put("payload_sha256", sha256); v.put("sample_count", input.sampleCount);
        v.put("transport_status", input.transportStatus); v.put("created_epoch_ms", input.createdEpochMs);

        SQLiteDatabase db = owner.scientificWritableDatabase();
        db.beginTransaction();
        try {
            db.insertOrThrow("captures", null, v); // ABORT on conflict; never REPLACE.
            db.setTransactionSuccessful();
        } finally {
            db.endTransaction();
        }
        return sha256;
    }

    /** Appends a review event only if its stated previous state matches the latest event. */
    public void appendReviewEvent(ReviewInput input) {
        validateReview(input);
        SQLiteDatabase db = owner.scientificWritableDatabase();
        db.beginTransaction();
        try {
            String sourceType;
            try (Cursor c = db.rawQuery("SELECT source_type FROM captures WHERE capture_id=?",
                    new String[]{input.captureId})) {
                if (!c.moveToFirst()) throw new IllegalArgumentException("الالتقاط غير موجود");
                sourceType = c.getString(0);
            }

            String latestEventId = null;
            String lifecycle = "CAPTURED";
            String groundTruth = "UNKNOWN";
            try (Cursor c = db.rawQuery("SELECT event_id,new_lifecycle_status,new_ground_truth_status "
                    + "FROM review_events WHERE capture_id=? ORDER BY rowid DESC LIMIT 1",
                    new String[]{input.captureId})) {
                if (c.moveToFirst()) {
                    latestEventId = c.getString(0);
                    lifecycle = c.getString(1);
                    groundTruth = c.getString(2);
                }
            }
            if (!equalsNullable(lifecycle, input.expectedLifecycle)
                    || !equalsNullable(groundTruth, input.expectedGroundTruth)) {
                throw new IllegalStateException("تغيرت حالة المراجعة؛ أعد تحميل آخر حالة قبل التصحيح");
            }
            if ("CONFIRMED".equals(input.newGroundTruth)) {
                if ("synthetic".equals(sourceType))
                    throw new IllegalArgumentException("لا يمكن تأكيد الحقيقة الأرضية لبيانات اصطناعية");
                if (isBlank(input.evidenceType) || isBlank(input.evidenceRef))
                    throw new IllegalArgumentException("تأكيد الحقيقة الأرضية يتطلب نوع دليل ومرجعه");
            }

            ContentValues v = new ContentValues();
            v.put("event_id", input.eventId); v.put("capture_id", input.captureId);
            v.put("event_time_epoch_ms", input.eventTimeEpochMs); v.put("reviewer_id", input.reviewerId);
            putNullable(v, "previous_lifecycle_status", lifecycle);
            v.put("new_lifecycle_status", input.newLifecycle);
            putNullable(v, "previous_ground_truth_status", groundTruth);
            v.put("new_ground_truth_status", input.newGroundTruth);
            v.put("reason_code", input.reasonCode); putNullable(v, "review_note", input.note);
            putNullable(v, "evidence_type", input.evidenceType); putNullable(v, "evidence_ref", input.evidenceRef);
            putNullable(v, "previous_event_id", latestEventId);
            db.insertOrThrow("review_events", null, v);
            db.setTransactionSuccessful();
        } finally {
            db.endTransaction();
        }
    }


    public static final class AnalysisInput {
        public final String runId, captureId, payloadSha256, algorithmId, algorithmVersion, modelSha256;
        public final String parametersJson, resultJson, runStatus;
        public final long startedEpochMs;
        public final Long completedEpochMs;
        public AnalysisInput(String runId, String captureId, String payloadSha256,
                String algorithmId, String algorithmVersion, String modelSha256,
                String parametersJson, String resultJson, long startedEpochMs,
                Long completedEpochMs, String runStatus) {
            this.runId=runId; this.captureId=captureId; this.payloadSha256=payloadSha256;
            this.algorithmId=algorithmId; this.algorithmVersion=algorithmVersion;
            this.modelSha256=modelSha256; this.parametersJson=parametersJson;
            this.resultJson=resultJson; this.startedEpochMs=startedEpochMs;
            this.completedEpochMs=completedEpochMs; this.runStatus=runStatus;
        }
    }

    public static final class EvaluationItemInput {
        public final String itemId, captureId, split, groupKey, expectedJson, actualJson;
        public EvaluationItemInput(String itemId, String captureId, String split, String groupKey,
                                   String expectedJson, String actualJson) {
            this.itemId=itemId; this.captureId=captureId; this.split=split; this.groupKey=groupKey;
            this.expectedJson=expectedJson; this.actualJson=actualJson;
        }
    }

    public static final class EvaluationInput {
        public final String evaluationId, manifestJson, championId, championVersion;
        public final String candidateId, candidateVersion, metricsJson, decision;
        public final long createdEpochMs;
        public final java.util.List<EvaluationItemInput> items;
        public EvaluationInput(String evaluationId, String manifestJson, String championId,
                String championVersion, String candidateId, String candidateVersion,
                String metricsJson, String decision, long createdEpochMs,
                java.util.List<EvaluationItemInput> items) {
            this.evaluationId=evaluationId; this.manifestJson=manifestJson;
            this.championId=championId; this.championVersion=championVersion;
            this.candidateId=candidateId; this.candidateVersion=candidateVersion;
            this.metricsJson=metricsJson; this.decision=decision;
            this.createdEpochMs=createdEpochMs; this.items=items;
        }
    }

    public static final class DeploymentInput {
        public final String eventId, previousAlgorithmId, previousAlgorithmVersion;
        public final String newAlgorithmId, newAlgorithmVersion, modelSha256;
        public final String action, reason, actorId, evaluationRunId;
        public final long eventTimeEpochMs;
        public DeploymentInput(String eventId, String previousAlgorithmId,
                String previousAlgorithmVersion, String newAlgorithmId, String newAlgorithmVersion,
                String modelSha256, String action, String reason, String actorId,
                long eventTimeEpochMs, String evaluationRunId) {
            this.eventId=eventId; this.previousAlgorithmId=previousAlgorithmId;
            this.previousAlgorithmVersion=previousAlgorithmVersion;
            this.newAlgorithmId=newAlgorithmId; this.newAlgorithmVersion=newAlgorithmVersion;
            this.modelSha256=modelSha256; this.action=action; this.reason=reason;
            this.actorId=actorId; this.eventTimeEpochMs=eventTimeEpochMs;
            this.evaluationRunId=evaluationRunId;
        }
    }

    /** Persists an analysis only when it names the exact immutable capture digest. */
    public void appendAnalysisRun(AnalysisInput input) {
        if (input == null || isBlank(input.runId) || isBlank(input.captureId)
                || !isSha256(input.payloadSha256) || isBlank(input.algorithmId)
                || isBlank(input.algorithmVersion) || !isJsonObject(input.parametersJson)
                || (input.resultJson != null && !isJsonObject(input.resultJson))
                || input.startedEpochMs < 0 || !oneOf(input.runStatus, "complete", "failed", "cancelled"))
            throw new IllegalArgumentException("بيانات تشغيل التحليل غير صالحة");
        if (input.modelSha256 != null && !isSha256(input.modelSha256))
            throw new IllegalArgumentException("بصمة النموذج غير صالحة");
        if ("complete".equals(input.runStatus) && input.completedEpochMs == null)
            throw new IllegalArgumentException("التحليل المكتمل يحتاج وقت انتهاء");
        if (input.completedEpochMs != null && input.completedEpochMs < input.startedEpochMs)
            throw new IllegalArgumentException("وقت انتهاء التحليل يسبق بدايته");

        SQLiteDatabase db = owner.scientificWritableDatabase();
        db.beginTransaction();
        try {
            try (Cursor c = db.rawQuery("SELECT payload_sha256 FROM captures WHERE capture_id=?",
                    new String[]{input.captureId})) {
                if (!c.moveToFirst()) throw new IllegalArgumentException("الالتقاط غير موجود");
                if (!input.payloadSha256.equals(c.getString(0)))
                    throw new IllegalArgumentException("بصمة التحليل لا تطابق بصمة الالتقاط الخام");
            }
            ContentValues v = new ContentValues();
            v.put("analysis_run_id", input.runId); v.put("capture_id", input.captureId);
            v.put("input_payload_sha256", input.payloadSha256);
            v.put("algorithm_id", input.algorithmId); v.put("algorithm_version", input.algorithmVersion);
            putNullable(v, "model_sha256", input.modelSha256);
            v.put("parameters_json", input.parametersJson); putNullable(v, "result_json", input.resultJson);
            v.put("started_epoch_ms", input.startedEpochMs);
            if (input.completedEpochMs != null) v.put("completed_epoch_ms", input.completedEpochMs);
            v.put("run_status", input.runStatus);
            db.insertOrThrow("analysis_runs", null, v);
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }

    /** Stores an evaluation and all its split assignments atomically. */
    public String appendEvaluation(EvaluationInput input) {
        if (input == null || isBlank(input.evaluationId) || !isJsonObject(input.manifestJson)
                || isBlank(input.candidateId) || isBlank(input.candidateVersion)
                || !isJsonObject(input.metricsJson) || isBlank(input.decision)
                || input.createdEpochMs < 0 || input.items == null || input.items.isEmpty())
            throw new IllegalArgumentException("بيانات التقييم غير صالحة");
        final String manifestHash;
        try { manifestHash = sha256(input.manifestJson.getBytes(java.nio.charset.StandardCharsets.UTF_8)); }
        catch (Exception ex) { throw new IllegalStateException("تعذر حساب بصمة بيان مجموعة البيانات", ex); }

        java.util.HashMap<String, String> groupSplits = new java.util.HashMap<>();
        java.util.HashSet<String> captureIds = new java.util.HashSet<>();
        for (EvaluationItemInput item : input.items) {
            if (item == null || isBlank(item.itemId) || isBlank(item.captureId) || isBlank(item.groupKey)
                    || !oneOf(item.split, "train", "validation", "test", "shadow")
                    || (item.expectedJson != null && !isJsonObject(item.expectedJson))
                    || (item.actualJson != null && !isJsonObject(item.actualJson)))
                throw new IllegalArgumentException("عنصر تقييم غير صالح");
            if (!captureIds.add(item.captureId))
                throw new IllegalArgumentException("لا يجوز تكرار الالتقاط داخل التقييم نفسه");
            String oldSplit = groupSplits.putIfAbsent(item.groupKey, item.split);
            if (oldSplit != null && !oldSplit.equals(item.split))
                throw new IllegalArgumentException("تسرب مجموعة مترابطة بين تقسيمات التقييم");
        }

        SQLiteDatabase db = owner.scientificWritableDatabase();
        db.beginTransaction();
        try {
            if ("PROMOTE".equals(input.decision)) {
                for (EvaluationItemInput item : input.items) {
                    try (Cursor c = db.rawQuery("SELECT source_type FROM captures WHERE capture_id=?",
                            new String[]{item.captureId})) {
                        if (!c.moveToFirst()) throw new IllegalArgumentException("التقاط التقييم غير موجود");
                        if ("synthetic".equals(c.getString(0)))
                            throw new IllegalArgumentException("لا يجوز ترقية خوارزمية اعتماداً على بيانات اصطناعية");
                    }
                    try (Cursor c = db.rawQuery("SELECT new_lifecycle_status,new_ground_truth_status "
                            + "FROM review_events WHERE capture_id=? ORDER BY rowid DESC LIMIT 1",
                            new String[]{item.captureId})) {
                        if (!c.moveToFirst()
                                || !"ELIGIBLE_FOR_TRAINING".equals(c.getString(0))
                                || !"CONFIRMED".equals(c.getString(1)))
                            throw new IllegalArgumentException("ترقية الخوارزمية تتطلب بيانات مستقلة مؤكدة ومؤهلة");
                    }
                }
            }
            ContentValues run = new ContentValues();
            run.put("evaluation_run_id", input.evaluationId); run.put("dataset_manifest_json", input.manifestJson);
            run.put("dataset_manifest_sha256", manifestHash);
            putNullable(run, "champion_algorithm_id", input.championId);
            putNullable(run, "champion_algorithm_version", input.championVersion);
            run.put("candidate_algorithm_id", input.candidateId);
            run.put("candidate_algorithm_version", input.candidateVersion);
            run.put("metrics_json", input.metricsJson); run.put("decision", input.decision);
            run.put("created_epoch_ms", input.createdEpochMs);
            db.insertOrThrow("evaluation_runs", null, run);

            for (EvaluationItemInput item : input.items) {
                ContentValues row = new ContentValues();
                row.put("evaluation_item_id", item.itemId); row.put("evaluation_run_id", input.evaluationId);
                row.put("capture_id", item.captureId); row.put("split", item.split);
                row.put("group_key", item.groupKey);
                putNullable(row, "expected_result_json", item.expectedJson);
                putNullable(row, "actual_result_json", item.actualJson);
                db.insertOrThrow("evaluation_items", null, row);
            }
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
        return manifestHash;
    }

    /** Activation is permitted only when a recorded evaluation explicitly says PROMOTE. */
    public void appendDeploymentEvent(DeploymentInput input) {
        if (input == null || isBlank(input.eventId) || isBlank(input.newAlgorithmId)
                || isBlank(input.newAlgorithmVersion) || !oneOf(input.action, "activate", "rollback", "reject")
                || isBlank(input.reason) || isBlank(input.actorId) || input.eventTimeEpochMs < 0)
            throw new IllegalArgumentException("بيانات حدث النشر غير صالحة");
        if (input.modelSha256 != null && !isSha256(input.modelSha256))
            throw new IllegalArgumentException("بصمة النموذج غير صالحة");
        if ("activate".equals(input.action) && isBlank(input.evaluationRunId))
            throw new IllegalArgumentException("التفعيل يحتاج مرجع تقييم");
        SQLiteDatabase db = owner.scientificWritableDatabase();
        db.beginTransaction();
        try {
            if (input.evaluationRunId != null) {
                try (Cursor c = db.rawQuery("SELECT candidate_algorithm_id,candidate_algorithm_version,decision "
                        + "FROM evaluation_runs WHERE evaluation_run_id=?",
                        new String[]{input.evaluationRunId})) {
                    if (!c.moveToFirst()) throw new IllegalArgumentException("التقييم المرجعي غير موجود");
                    if ("activate".equals(input.action)) {
                        if (!input.newAlgorithmId.equals(c.getString(0))
                                || !input.newAlgorithmVersion.equals(c.getString(1))
                                || !"PROMOTE".equals(c.getString(2)))
                            throw new IllegalArgumentException("التقييم لا يجيز تفعيل هذه النسخة");
                    }
                }
            }
            ContentValues v = new ContentValues();
            v.put("deployment_event_id", input.eventId);
            putNullable(v, "previous_algorithm_id", input.previousAlgorithmId);
            putNullable(v, "previous_algorithm_version", input.previousAlgorithmVersion);
            v.put("new_algorithm_id", input.newAlgorithmId);
            v.put("new_algorithm_version", input.newAlgorithmVersion);
            putNullable(v, "model_sha256", input.modelSha256);
            v.put("action", input.action); v.put("reason", input.reason);
            v.put("actor_id", input.actorId); v.put("event_time_epoch_ms", input.eventTimeEpochMs);
            putNullable(v, "evaluation_run_id", input.evaluationRunId);
            db.insertOrThrow("deployment_events", null, v);
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }

    private static boolean isSha256(String value) {
        return value != null && value.matches("(?i)[0-9a-f]{64}");
    }

    private static boolean isJsonObject(String value) {
        if (isBlank(value)) return false;
        try { new org.json.JSONObject(value); return true; }
        catch (org.json.JSONException ex) { return false; }
    }

    private static void validateCapture(CaptureInput x) {
        if (x == null || isBlank(x.captureId) || isBlank(x.sessionId) || x.sequence < 0
                || isBlank(x.payloadFormat) || x.payload == null || x.payload.length == 0
                || x.sampleCount < 0 || x.createdEpochMs < 0)
            throw new IllegalArgumentException("بيانات الالتقاط ناقصة أو غير صالحة");
        if (!oneOf(x.sourceType, "synthetic", "user_provided", "instrument", "islam_detector"))
            throw new IllegalArgumentException("مصدر الالتقاط غير معتمد");
        if (!oneOf(x.transportStatus, "complete", "incomplete", "corrupted"))
            throw new IllegalArgumentException("حالة النقل غير معتمدة");
        if ("complete".equals(x.transportStatus) && x.sampleCount < 1)
            throw new IllegalArgumentException("الالتقاط المكتمل يحتاج عينة واحدة على الأقل");
        if (x.monotonicStartTick != null && x.monotonicStartTick < 0)
            throw new IllegalArgumentException("قيمة الساعة الرتيبة غير صالحة");
        if (x.tickFrequencyHz != null && x.tickFrequencyHz <= 0)
            throw new IllegalArgumentException("تردد الساعة يجب أن يكون موجباً");
    }

    private static void validateReview(ReviewInput x) {
        if (x == null || isBlank(x.eventId) || isBlank(x.captureId) || isBlank(x.reviewerId)
                || isBlank(x.reasonCode) || x.eventTimeEpochMs < 0
                || !oneOf(x.newLifecycle, "CAPTURED", "NEEDS_REVIEW", "REVIEWED",
                "ELIGIBLE_FOR_TRAINING", "REJECTED", "INCONCLUSIVE")
                || !oneOf(x.newGroundTruth, "UNKNOWN", "CONFIRMED", "REJECTED", "INCONCLUSIVE"))
            throw new IllegalArgumentException("بيانات حدث المراجعة غير صالحة");
        if (!oneOf(x.expectedLifecycle, "CAPTURED", "NEEDS_REVIEW", "REVIEWED",
                "ELIGIBLE_FOR_TRAINING", "REJECTED", "INCONCLUSIVE")
                || !oneOf(x.expectedGroundTruth, "UNKNOWN", "CONFIRMED", "REJECTED", "INCONCLUSIVE"))
            throw new IllegalArgumentException("الحالة السابقة غير صالحة");
    }

    private static String sha256(byte[] bytes) throws NoSuchAlgorithmException {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(bytes);
        StringBuilder out = new StringBuilder(64);
        for (byte b : digest) out.append(String.format(Locale.US, "%02x", b & 0xff));
        return out.toString();
    }

    private static String crc32(byte[] bytes) {
        CRC32 crc = new CRC32(); crc.update(bytes);
        return String.format(Locale.US, "%08x", crc.getValue());
    }

    private static boolean oneOf(String value, String... values) {
        if (value == null) return false;
        for (String v : values) if (v.equals(value)) return true;
        return false;
    }

    private static boolean equalsNullable(String a, String b) {
        return a == null ? b == null : a.equals(b);
    }

    private static void putNullable(ContentValues v, String key, String value) {
        if (value == null) v.putNull(key); else v.put(key, value);
    }

    private static boolean isBlank(String value) { return value == null || value.trim().isEmpty(); }
}
