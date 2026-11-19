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
        public final String captureId, sessionId, sourceType, capturedAtUtc, deviceId;
        public final String stm32Firmware, esp32Firmware, coilProfileId, acquisitionConfigId;
        public final String payloadFormat, payloadSha256, payloadCrc32, transportStatus;
        public final long sequence, createdEpochMs;
        public final Long monotonicStartTick, tickFrequencyHz;
        public final int sampleCount;
        public final byte[] payload;
        CaptureRecord(Cursor c) {
            captureId=c.getString(0); sessionId=c.getString(1); sequence=c.getLong(2);
            sourceType=c.getString(3); capturedAtUtc=c.getString(4);
            monotonicStartTick=c.isNull(5) ? null : c.getLong(5);
            tickFrequencyHz=c.isNull(6) ? null : c.getLong(6);
            deviceId=c.getString(7); stm32Firmware=c.getString(8); esp32Firmware=c.getString(9);
            coilProfileId=c.getString(10); acquisitionConfigId=c.getString(11);
            payloadFormat=c.getString(12); payload=c.getBlob(13);
            payloadSha256=c.getString(14); payloadCrc32=c.getString(15);
            sampleCount=c.getInt(16); transportStatus=c.getString(17);
            createdEpochMs=c.getLong(18);
        }
    }

    /** Reads the original bytes and full acquisition metadata; verifies length, CRC32 and SHA-256. */
    public CaptureRecord getCapture(String captureId) {
        if (isBlank(captureId)) throw new IllegalArgumentException("معرف الالتقاط مطلوب");
        try (Cursor c = owner.scientificReadableDatabase().rawQuery(
                "SELECT capture_id,session_id,sequence,source_type,captured_at_utc,"
                + "monotonic_start_tick,tick_frequency_hz,device_id,stm32_firmware,esp32_firmware,"
                + "coil_profile_id,acquisition_config_id,payload_format,payload_blob,payload_sha256,"
                + "payload_crc32,sample_count,transport_status,created_epoch_ms,payload_length_bytes "
                + "FROM captures WHERE capture_id=?", new String[]{captureId})) {
            if (!c.moveToFirst()) return null;
            CaptureRecord record = new CaptureRecord(c);
            if (record.payload == null || record.payload.length != c.getInt(19)
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
        public final String targetClass, soilClass;
        public final Boolean groundTruthPositive;
        public final long eventTimeEpochMs;

        public ReviewInput(String eventId, String captureId, String reviewerId,
                           String expectedLifecycle, String newLifecycle,
                           String expectedGroundTruth, String newGroundTruth,
                           String reasonCode, String note, String evidenceType,
                           String evidenceRef, long eventTimeEpochMs) {
            this(eventId, captureId, reviewerId, expectedLifecycle, newLifecycle,
                    expectedGroundTruth, newGroundTruth, reasonCode, note, evidenceType,
                    evidenceRef, eventTimeEpochMs, null, null, null);
        }

        public ReviewInput(String eventId, String captureId, String reviewerId,
                           String expectedLifecycle, String newLifecycle,
                           String expectedGroundTruth, String newGroundTruth,
                           String reasonCode, String note, String evidenceType,
                           String evidenceRef, long eventTimeEpochMs,
                           String targetClass, String soilClass, Boolean groundTruthPositive) {
            this.eventId=eventId; this.captureId=captureId; this.reviewerId=reviewerId;
            this.expectedLifecycle=expectedLifecycle; this.newLifecycle=newLifecycle;
            this.expectedGroundTruth=expectedGroundTruth; this.newGroundTruth=newGroundTruth;
            this.reasonCode=reasonCode; this.note=note; this.evidenceType=evidenceType;
            this.evidenceRef=evidenceRef; this.eventTimeEpochMs=eventTimeEpochMs;
            this.targetClass=targetClass; this.soilClass=soilClass;
            this.groundTruthPositive=groundTruthPositive;
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
            String latestTargetClass = null, latestSoilClass = null;
            Boolean latestGroundTruthPositive = null;
            try (Cursor c = db.rawQuery("SELECT event_id,new_lifecycle_status,new_ground_truth_status,"
                    + "target_class,soil_class,ground_truth_positive FROM review_events "
                    + "WHERE capture_id=? ORDER BY rowid DESC LIMIT 1",
                    new String[]{input.captureId})) {
                if (c.moveToFirst()) {
                    latestEventId = c.getString(0);
                    lifecycle = c.getString(1);
                    groundTruth = c.getString(2);
                    latestTargetClass = c.getString(3);
                    latestSoilClass = c.getString(4);
                    if (!c.isNull(5)) latestGroundTruthPositive = c.getInt(5) == 1;
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

            if ((input.targetClass != null && isBlank(input.targetClass))
                    || (input.soilClass != null && isBlank(input.soilClass)))
                throw new IllegalArgumentException("فئة الهدف أو التربة لا يجوز أن تكون فارغة");
            if (input.groundTruthPositive != null && !"CONFIRMED".equals(input.newGroundTruth))
                throw new IllegalArgumentException("تحديد وجود الهدف يتطلب حقيقة أرضية مؤكدة");
            String effectiveTargetClass = input.targetClass != null ? input.targetClass : latestTargetClass;
            String effectiveSoilClass = input.soilClass != null ? input.soilClass : latestSoilClass;
            Boolean effectiveGroundTruthPositive = input.groundTruthPositive != null
                    ? input.groundTruthPositive
                    : ("CONFIRMED".equals(input.newGroundTruth) ? latestGroundTruthPositive : null);

            ContentValues v = new ContentValues();
            v.put("event_id", input.eventId); v.put("capture_id", input.captureId);
            v.put("event_time_epoch_ms", input.eventTimeEpochMs); v.put("reviewer_id", input.reviewerId);
            putNullable(v, "previous_lifecycle_status", lifecycle);
            v.put("new_lifecycle_status", input.newLifecycle);
            putNullable(v, "previous_ground_truth_status", groundTruth);
            v.put("new_ground_truth_status", input.newGroundTruth);
            v.put("reason_code", input.reasonCode); putNullable(v, "review_note", input.note);
            putNullable(v, "evidence_type", input.evidenceType); putNullable(v, "evidence_ref", input.evidenceRef);
            putNullable(v, "target_class", effectiveTargetClass); putNullable(v, "soil_class", effectiveSoilClass);
            if (effectiveGroundTruthPositive != null)
                v.put("ground_truth_positive", effectiveGroundTruthPositive ? 1 : 0);
            else v.putNull("ground_truth_positive");
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



    /** Split assignment supplied by the experiment protocol; group keys must be stable identifiers. */
    public static final class ManifestAssignment {
        public final String captureId, split, groupKey;
        public ManifestAssignment(String captureId, String split, String groupKey) {
            this.captureId=captureId; this.split=split; this.groupKey=groupKey;
        }
    }

    /** A manifest is generated from stored captures and the latest review event, never from caller labels. */
    public static final class DatasetManifest {
        public final String manifestId, json, sha256;
        public final int itemCount;
        DatasetManifest(String manifestId, String json, String sha256, int itemCount) {
            this.manifestId=manifestId; this.json=json; this.sha256=sha256; this.itemCount=itemCount;
        }
    }

    /**
     * Builds a deterministic manifest from authoritative local records.
     * Target class and soil class are intentionally absent: they are not canonical capture fields.
     */
    public DatasetManifest buildDatasetManifest(String manifestId, long createdEpochMs,
            java.util.List<ManifestAssignment> assignments) {
        if (isBlank(manifestId) || createdEpochMs < 0 || assignments == null || assignments.isEmpty())
            throw new IllegalArgumentException("بيانات بيان مجموعة البيانات غير صالحة");
        java.util.ArrayList<ManifestAssignment> ordered = new java.util.ArrayList<>(assignments);
        java.util.Collections.sort(ordered, new java.util.Comparator<ManifestAssignment>() {
            @Override public int compare(ManifestAssignment a, ManifestAssignment b) {
                String left = a == null || a.captureId == null ? "" : a.captureId;
                String right = b == null || b.captureId == null ? "" : b.captureId;
                return left.compareTo(right);
            }
        });
        java.util.HashSet<String> ids = new java.util.HashSet<>();
        java.util.HashMap<String,String> groupSplits = new java.util.HashMap<>();
        org.json.JSONArray entries = new org.json.JSONArray();
        SQLiteDatabase db = owner.scientificReadableDatabase();
        for (ManifestAssignment assignment : ordered) {
            if (assignment == null || isBlank(assignment.captureId) || isBlank(assignment.groupKey)
                    || !oneOf(assignment.split, "train", "validation", "test", "shadow")
                    || !ids.add(assignment.captureId))
                throw new IllegalArgumentException("توزيع العينات في البيان غير صالح أو مكرر");
            String prior = groupSplits.get(assignment.groupKey);
            if (prior != null && !prior.equals(assignment.split))
                throw new IllegalArgumentException("المجموعة المترابطة موزعة بين تقسيمات مختلفة");
            groupSplits.put(assignment.groupKey, assignment.split);

            try (Cursor capture = db.rawQuery("SELECT source_type,transport_status,payload_blob,"
                    + "payload_sha256,payload_crc32,payload_length_bytes,sample_count,payload_format,"
                    + "session_id,sequence,device_id,stm32_firmware,esp32_firmware,coil_profile_id,"
                    + "acquisition_config_id,captured_at_utc,monotonic_start_tick,tick_frequency_hz "
                    + "FROM captures WHERE capture_id=?", new String[]{assignment.captureId})) {
                if (!capture.moveToFirst()) throw new IllegalArgumentException("عينة غير موجودة: " + assignment.captureId);
                byte[] raw = capture.getBlob(2);
                if (raw == null || raw.length != capture.getInt(5)
                        || !capture.getString(3).equals(sha256(raw))
                        || !capture.getString(4).equals(crc32(raw)))
                    throw new IllegalStateException("سلامة الحمولة غير مثبتة للعينة: " + assignment.captureId);
                org.json.JSONObject entry = new org.json.JSONObject();
                try {
                    entry.put("capture_id", assignment.captureId);
                    entry.put("split", assignment.split);
                    entry.put("group_key", assignment.groupKey);
                    entry.put("payload_sha256", capture.getString(3));
                    entry.put("payload_length_bytes", raw.length);
                    entry.put("sample_count", capture.getInt(6));
                    entry.put("payload_format", capture.getString(7));
                    entry.put("source_type", capture.getString(0));
                    entry.put("transport_status", capture.getString(1));
                    entry.put("session_id", capture.getString(8));
                    entry.put("sequence", capture.getLong(9));
                    putJsonNullable(entry, "device_id", capture.getString(10));
                    putJsonNullable(entry, "stm32_firmware", capture.getString(11));
                    putJsonNullable(entry, "esp32_firmware", capture.getString(12));
                    putJsonNullable(entry, "coil_profile_id", capture.getString(13));
                    putJsonNullable(entry, "acquisition_config_id", capture.getString(14));
                    putJsonNullable(entry, "captured_at_utc", capture.getString(15));
                    if (!capture.isNull(16)) entry.put("monotonic_start_tick", capture.getLong(16));
                    if (!capture.isNull(17)) entry.put("tick_frequency_hz", capture.getLong(17));
                    try (Cursor review = db.rawQuery("SELECT reviewer_id,new_lifecycle_status,"
                            + "new_ground_truth_status,evidence_type,evidence_ref,event_time_epoch_ms,"
                            + "target_class,soil_class,ground_truth_positive "
                            + "FROM review_events WHERE capture_id=? ORDER BY rowid DESC LIMIT 1",
                            new String[]{assignment.captureId})) {
                        if (review.moveToFirst()) {
                            entry.put("reviewer_id", review.getString(0));
                            entry.put("review_lifecycle", review.getString(1));
                            entry.put("ground_truth_status", review.getString(2));
                            putJsonNullable(entry, "evidence_type", review.getString(3));
                            putJsonNullable(entry, "evidence_ref", review.getString(4));
                            entry.put("reviewed_epoch_ms", review.getLong(5));
                            putJsonNullable(entry, "target_class", review.getString(6));
                            putJsonNullable(entry, "soil_class", review.getString(7));
                            if (!review.isNull(8))
                                entry.put("ground_truth_positive", review.getInt(8) == 1);
                            else entry.put("ground_truth_positive", org.json.JSONObject.NULL);
                        } else {
                            entry.put("review_lifecycle", "CAPTURED");
                            entry.put("ground_truth_status", "UNKNOWN");
                        }
                    }
                    entries.put(entry);
                } catch (org.json.JSONException ex) {
                    throw new IllegalStateException("تعذر إنشاء بيان مجموعة البيانات", ex);
                }
            }
        }
        try {
            org.json.JSONObject root = new org.json.JSONObject();
            root.put("manifest_schema", "islam-dataset-manifest-v1");
            root.put("manifest_id", manifestId);
            root.put("created_epoch_ms", createdEpochMs);
            root.put("item_count", entries.length());
            root.put("items", entries);
            String json = root.toString();
            return new DatasetManifest(manifestId, json,
                    sha256(json.getBytes(java.nio.charset.StandardCharsets.UTF_8)), entries.length());
        } catch (org.json.JSONException | NoSuchAlgorithmException ex) {
            throw new IllegalStateException("تعذر ختم بيان مجموعة البيانات", ex);
        }
    }



    /** Requires a complete detector result bound to the exact raw capture digest. */
    static boolean requireCompletedDetectionRun(SQLiteDatabase db, String captureId,
            String algorithmId, String algorithmVersion, String captureDigest) {
        try (Cursor c = db.rawQuery("SELECT input_payload_sha256,result_json,model_sha256 FROM analysis_runs "
                + "WHERE capture_id=? AND algorithm_id=? AND algorithm_version=? AND run_status='complete' "
                + "ORDER BY started_epoch_ms DESC,rowid DESC LIMIT 1",
                new String[]{captureId, algorithmId, algorithmVersion})) {
            if (!c.moveToFirst() || !captureDigest.equals(c.getString(0)) || c.isNull(1)
                    || !isSha256(c.getString(2)))
                throw new IllegalArgumentException("نتيجة التحليل المكتملة أو بصمة النموذج غير موجودة أو لا تطابق الالتقاط");
            try {
                org.json.JSONObject result = new org.json.JSONObject(c.getString(1));
                if (!(result.opt("detected") instanceof Boolean))
                    throw new IllegalArgumentException("خرج كاشف المعادن يجب أن يحتوي detected منطقية");
                return result.getBoolean("detected");
            } catch (org.json.JSONException ex) {
                throw new IllegalArgumentException("خرج التحليل غير صالح", ex);
            }
        }
    }

    /** A field-candidate evaluation must consume the exact sealed manifest it records. */
    private static void validateEvaluationManifest(SQLiteDatabase db, EvaluationInput input,
            String expectedManifestHash) {
        try {
            org.json.JSONObject root = new org.json.JSONObject(input.manifestJson);
            if (!"islam-dataset-manifest-v1".equals(root.optString("manifest_schema"))
                    || !input.evaluationId.equals(root.optString("manifest_id"))
                    || root.optInt("item_count", -1) != input.items.size())
                throw new IllegalArgumentException("تقييم ميداني يحتاج بيان بيانات موثوقاً مطابقاً");
            org.json.JSONArray entries = root.optJSONArray("items");
            if (entries == null || entries.length() != input.items.size())
                throw new IllegalArgumentException("عدد عينات البيان لا يطابق التقييم");
            java.util.HashMap<String,org.json.JSONObject> byCapture = new java.util.HashMap<>();
            for (int i=0;i<entries.length();i++) {
                org.json.JSONObject entry = entries.getJSONObject(i);
                String id = entry.optString("capture_id", "");
                if (isBlank(id) || byCapture.put(id, entry) != null)
                    throw new IllegalArgumentException("البيان يحتوي معرف التقاط مفقوداً أو مكرراً");
            }
            for (EvaluationItemInput item : input.items) {
                org.json.JSONObject entry = byCapture.remove(item.captureId);
                if (entry == null || !item.split.equals(entry.optString("split"))
                        || !item.groupKey.equals(entry.optString("group_key")))
                    throw new IllegalArgumentException("توزيع العينة في البيان لا يطابق عناصر التقييم");
                try (Cursor capture = db.rawQuery("SELECT payload_sha256,source_type,transport_status "
                        + "FROM captures WHERE capture_id=?", new String[]{item.captureId})) {
                    if (!capture.moveToFirst()
                            || !capture.getString(0).equals(entry.optString("payload_sha256"))
                            || !capture.getString(1).equals(entry.optString("source_type"))
                            || !capture.getString(2).equals(entry.optString("transport_status")))
                        throw new IllegalArgumentException("بيان العينة لا يطابق سجل الالتقاط الأصلي");
                }
                if (!"CONFIRMED".equals(entry.optString("ground_truth_status"))
                        || !"ELIGIBLE_FOR_TRAINING".equals(entry.optString("review_lifecycle"))
                        || !entry.has("target_class") || entry.isNull("target_class")
                        || isBlank(entry.optString("target_class"))
                        || !entry.has("soil_class") || entry.isNull("soil_class")
                        || isBlank(entry.optString("soil_class"))
                        || !entry.has("ground_truth_positive") || entry.isNull("ground_truth_positive"))
                    throw new IllegalArgumentException("بيان التقييم يفتقد حقيقة أرضية مؤكدة أو فئة الهدف/التربة");
            }
            if (!byCapture.isEmpty())
                throw new IllegalArgumentException("البيان يحتوي عينات غير موجودة في التقييم");
            if (!expectedManifestHash.equals(sha256(input.manifestJson.getBytes(
                    java.nio.charset.StandardCharsets.UTF_8))))
                throw new IllegalArgumentException("بصمة بيان مجموعة البيانات غير متطابقة");
        } catch (org.json.JSONException | NoSuchAlgorithmException ex) {
            throw new IllegalArgumentException("تعذر التحقق من بيان مجموعة البيانات", ex);
        }
    }

    private static void putJsonNullable(org.json.JSONObject object, String key, String value)
            throws org.json.JSONException {
        if (value == null) object.put(key, org.json.JSONObject.NULL);
        else object.put(key, value);
    }

    /** Immutable record of a capture's declared role in a versioned dataset/run. */
    public static final class DatasetUsageInput {
        public final String eventId, captureId, manifestId, manifestSha256, role;
        public final String consumerId, consumerVersion, runId, actorId, evidenceRef;
        public final long recordedEpochMs;
        public DatasetUsageInput(String eventId, String captureId, String manifestId,
                String manifestSha256, String role, String consumerId, String consumerVersion,
                String runId, long recordedEpochMs, String actorId, String evidenceRef) {
            this.eventId=eventId; this.captureId=captureId; this.manifestId=manifestId;
            this.manifestSha256=manifestSha256; this.role=role; this.consumerId=consumerId;
            this.consumerVersion=consumerVersion; this.runId=runId;
            this.recordedEpochMs=recordedEpochMs; this.actorId=actorId; this.evidenceRef=evidenceRef;
        }
    }

    /**
     * Appends dataset usage evidence. Repeating an identical event_id is idempotent;
     * reusing it with different content is rejected.
     */
    public void appendDatasetUsageEvent(DatasetUsageInput input) {
        if (input == null || isBlank(input.eventId) || isBlank(input.captureId)
                || isBlank(input.manifestId) || !isSha256(input.manifestSha256)
                || !oneOf(input.role, "TRAIN", "VALIDATION", "TEST", "SHADOW")
                || isBlank(input.consumerId) || isBlank(input.consumerVersion)
                || isBlank(input.runId) || input.recordedEpochMs < 0
                || isBlank(input.actorId) || isBlank(input.evidenceRef))
            throw new IllegalArgumentException("بيانات سجل استخدام العينة غير صالحة");
        SQLiteDatabase db = owner.scientificWritableDatabase();
        db.beginTransaction();
        try {
            try (Cursor c = db.rawQuery("SELECT capture_id,dataset_manifest_id,dataset_manifest_sha256,"
                    + "usage_role,consumer_id,consumer_version,run_id,recorded_epoch_ms,actor_id,evidence_ref "
                    + "FROM dataset_usage_events WHERE event_id=?", new String[]{input.eventId})) {
                if (c.moveToFirst()) {
                    boolean same = input.captureId.equals(c.getString(0))
                            && input.manifestId.equals(c.getString(1))
                            && input.manifestSha256.equals(c.getString(2))
                            && input.role.equals(c.getString(3))
                            && input.consumerId.equals(c.getString(4))
                            && input.consumerVersion.equals(c.getString(5))
                            && input.runId.equals(c.getString(6))
                            && input.recordedEpochMs == c.getLong(7)
                            && input.actorId.equals(c.getString(8))
                            && input.evidenceRef.equals(c.getString(9));
                    if (!same) throw new IllegalArgumentException("معرف الحدث مستخدم بمحتوى مختلف");
                    db.setTransactionSuccessful();
                    return;
                }
            }
            ContentValues v = new ContentValues();
            v.put("event_id", input.eventId); v.put("capture_id", input.captureId);
            v.put("dataset_manifest_id", input.manifestId);
            v.put("dataset_manifest_sha256", input.manifestSha256);
            v.put("usage_role", input.role); v.put("consumer_id", input.consumerId);
            v.put("consumer_version", input.consumerVersion); v.put("run_id", input.runId);
            v.put("recorded_epoch_ms", input.recordedEpochMs); v.put("actor_id", input.actorId);
            v.put("evidence_ref", input.evidenceRef);
            db.insertOrThrow("dataset_usage_events", null, v);
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
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
                || ("FIELD_CANDIDATE".equals(input.decision)
                    && (isBlank(input.championId) || isBlank(input.championVersion)))
                || !isJsonObject(input.metricsJson) || !oneOf(input.decision, "FIELD_CANDIDATE", "SIMULATION_ONLY", "SHADOW_ONLY")
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
            String oldSplit = groupSplits.get(item.groupKey);
            if (oldSplit != null && !oldSplit.equals(item.split))
                throw new IllegalArgumentException("تسرب مجموعة مترابطة بين تقسيمات التقييم");
            groupSplits.put(item.groupKey, item.split);
        }

        SQLiteDatabase db = owner.scientificWritableDatabase();
        db.beginTransaction();
        try {
            if ("FIELD_CANDIDATE".equals(input.decision)) {
                for (EvaluationItemInput item : input.items) {
                    String captureDigest;
                    try (Cursor c = db.rawQuery("SELECT source_type,transport_status,payload_blob,"
                            + "payload_sha256,payload_crc32,payload_length_bytes FROM captures WHERE capture_id=?",
                            new String[]{item.captureId})) {
                        if (!c.moveToFirst()) throw new IllegalArgumentException("التقاط التقييم غير موجود");
                        if (!oneOf(c.getString(0), "instrument", "islam_detector"))
                            throw new IllegalArgumentException("التقييم الميداني يقبل التقاطاً مباشراً من الجهاز فقط");
                        byte[] raw = c.getBlob(2);
                        captureDigest = c.getString(3);
                        if (!"complete".equals(c.getString(1)) || raw == null
                                || raw.length != c.getInt(5)
                                || !captureDigest.equals(sha256(raw))
                                || !c.getString(4).equals(crc32(raw)))
                            throw new IllegalArgumentException("بيانات التقييم لا تقبل حمولة ناقصة أو تالفة");
                    }
                    try (Cursor c = db.rawQuery("SELECT new_lifecycle_status,new_ground_truth_status "
                            + "FROM review_events WHERE capture_id=? ORDER BY rowid DESC LIMIT 1",
                            new String[]{item.captureId})) {
                        if (!c.moveToFirst()
                                || !"ELIGIBLE_FOR_TRAINING".equals(c.getString(0))
                                || !"CONFIRMED".equals(c.getString(1)))
                            throw new IllegalArgumentException("ترقية الخوارزمية تتطلب بيانات مستقلة مؤكدة ومؤهلة");
                    }
                    if ("test".equals(item.split)) {
                        requireCompletedDetectionRun(db, item.captureId, input.championId,
                                input.championVersion, captureDigest);
                        requireCompletedDetectionRun(db, item.captureId, input.candidateId,
                                input.candidateVersion, captureDigest);
                    }
                }
            }
            if ("FIELD_CANDIDATE".equals(input.decision)) {
                validateEvaluationManifest(db, input, manifestHash);
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

                ContentValues usage = new ContentValues();
                usage.put("event_id", input.evaluationId + ":" + item.captureId);
                usage.put("capture_id", item.captureId);
                usage.put("dataset_manifest_id", input.evaluationId);
                usage.put("dataset_manifest_sha256", manifestHash);
                usage.put("usage_role", item.split.toUpperCase(Locale.ROOT));
                usage.put("consumer_id", input.candidateId);
                usage.put("consumer_version", input.candidateVersion);
                usage.put("run_id", input.evaluationId);
                usage.put("recorded_epoch_ms", input.createdEpochMs);
                usage.put("actor_id", "evaluation_pipeline");
                usage.put("evidence_ref", "evaluation_items:" + item.itemId);
                db.insertOrThrow("dataset_usage_events", null, usage);
            }
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
        return manifestHash;
    }




    /** Registers one immutable, explicitly approved policy version. */
    public void registerEvaluationPolicy(String policyId, String policyVersion,
            EvaluationPolicyEvaluator.Policy policy, String approvedBy,
            String approvalEvidenceRef, long approvedEpochMs) {
        if (isBlank(policyId) || isBlank(policyVersion) || policy == null
                || isBlank(approvedBy) || isBlank(approvalEvidenceRef) || approvedEpochMs < 0)
            throw new IllegalArgumentException("بيانات اعتماد سياسة التقييم غير مكتملة");
        String json = serializePolicy(policy);
        String hash;
        try { hash = sha256(json.getBytes(java.nio.charset.StandardCharsets.UTF_8)); }
        catch (Exception ex) { throw new IllegalStateException("تعذر ختم سياسة التقييم", ex); }
        ContentValues row = new ContentValues();
        row.put("policy_id", policyId); row.put("policy_version", policyVersion);
        row.put("policy_json", json); row.put("policy_sha256", hash);
        row.put("approved_by", approvedBy); row.put("approval_evidence_ref", approvalEvidenceRef);
        row.put("approved_epoch_ms", approvedEpochMs);
        owner.scientificWritableDatabase().insertOrThrow("evaluation_policies", null, row);
    }

    private static String serializePolicy(EvaluationPolicyEvaluator.Policy policy) {
        try {
            org.json.JSONObject p = new org.json.JSONObject();
            p.put("min_test_cases", policy.minTestCases);
            p.put("min_positive_cases", policy.minPositiveCases);
            p.put("min_negative_cases", policy.minNegativeCases);
            p.put("max_accuracy_drop", policy.maxAccuracyDrop);
            p.put("max_recall_drop", policy.maxRecallDrop);
            p.put("max_false_positive_rate_increase", policy.maxFalsePositiveRateIncrease);
            p.put("min_candidate_recall", policy.minCandidateRecall);
            p.put("max_candidate_false_positive_rate", policy.maxCandidateFalsePositiveRate);
            org.json.JSONArray required = new org.json.JSONArray();
            java.util.ArrayList<String> sorted = new java.util.ArrayList<>(policy.requiredStrata);
            java.util.Collections.sort(sorted);
            for (String key : sorted) required.put(key);
            p.put("required_strata", required);
            return p.toString();
        } catch (org.json.JSONException ex) {
            throw new IllegalStateException("تعذر ترميز سياسة التقييم", ex);
        }
    }

    /**
     * Loads verified held-out TEST records, computes the release gate locally, and appends
     * the immutable result. Caller-supplied metrics_json is never used as the gate result.
     */
    public EvaluationPolicyEvaluator.Result evaluateAndRecordGate(String gateResultId,
            String evaluationId, String policyId, String policyVersion,
            EvaluationPolicyEvaluator.Policy policy, long createdEpochMs) {
        if (isBlank(gateResultId) || isBlank(evaluationId) || isBlank(policyId)
                || isBlank(policyVersion) || policy == null || createdEpochMs < 0)
            throw new IllegalArgumentException("مدخلات بوابة التقييم غير صالحة");
        java.util.List<EvaluationPolicyEvaluator.Observation> observations =
                EvaluationObservationLoader.loadHeldOutTest(owner, evaluationId);
        EvaluationPolicyEvaluator.Result result =
                EvaluationPolicyEvaluator.evaluate(observations, policy);
        final String policyJson = serializePolicy(policy);
        final String metricsJson;
        try {
            String policyHash = sha256(policyJson.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            try (Cursor registered = owner.scientificReadableDatabase().rawQuery(
                    "SELECT policy_json,policy_sha256 FROM evaluation_policies "
                            + "WHERE policy_id=? AND policy_version=?",
                    new String[]{policyId, policyVersion})) {
                if (!registered.moveToFirst() || !policyJson.equals(registered.getString(0))
                        || !policyHash.equals(registered.getString(1)))
                    throw new IllegalArgumentException("سياسة التقييم غير مسجلة أو تختلف عن النسخة المعتمدة");
            }
            org.json.JSONObject m = new org.json.JSONObject();
            m.put("status", result.status); m.put("reason", result.reason);
            if (result.champion != null) m.put("champion", metricsJson(result.champion));
            if (result.candidate != null) m.put("candidate", metricsJson(result.candidate));
            org.json.JSONArray strata = new org.json.JSONArray();
            for (EvaluationPolicyEvaluator.StratumResult stratum : result.strata.values()) {
                org.json.JSONObject s = new org.json.JSONObject();
                s.put("target_class", stratum.targetClass); s.put("soil_class", stratum.soilClass);
                s.put("champion", metricsJson(stratum.champion));
                s.put("candidate", metricsJson(stratum.candidate));
                strata.put(s);
            }
            m.put("strata", strata);
            metricsJson = m.toString();
        } catch (org.json.JSONException | NoSuchAlgorithmException ex) {
            throw new IllegalStateException("تعذر توثيق نتيجة بوابة التقييم", ex);
        }

        SQLiteDatabase db = owner.scientificWritableDatabase();
        db.beginTransaction();
        try {
            try (Cursor run = db.rawQuery("SELECT decision FROM evaluation_runs WHERE evaluation_run_id=?",
                    new String[]{evaluationId})) {
                if (!run.moveToFirst() || !"FIELD_CANDIDATE".equals(run.getString(0)))
                    throw new IllegalArgumentException("بوابة النشر تتطلب تقييماً ميدانياً");
            }
            ContentValues v = new ContentValues();
            v.put("gate_result_id", gateResultId); v.put("evaluation_run_id", evaluationId);
            v.put("policy_id", policyId); v.put("policy_version", policyVersion);
            v.put("policy_json", policyJson); v.put("status", result.status);
            v.put("reason", result.reason); v.put("metrics_json", metricsJson);
            v.put("created_epoch_ms", createdEpochMs);
            db.insertOrThrow("evaluation_gate_results", null, v);
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
        return result;
    }

    private static org.json.JSONObject metricsJson(EvaluationPolicyEvaluator.Metrics metrics)
            throws org.json.JSONException {
        org.json.JSONObject out = new org.json.JSONObject();
        out.put("cases", metrics.cases); out.put("positives", metrics.positives);
        out.put("negatives", metrics.negatives); out.put("tp", metrics.truePositive);
        out.put("fp", metrics.falsePositive); out.put("tn", metrics.trueNegative);
        out.put("fn", metrics.falseNegative); out.put("accuracy", metrics.accuracy);
        out.put("recall", metrics.recall); out.put("false_positive_rate", metrics.falsePositiveRate);
        return out;
    }

    /** Appends an explicit human/policy decision after a field-candidate evaluation. */
    public void appendEvaluationDecision(String decisionId, String evaluationId, String decision,
            String policyId, String policyVersion, String reviewerId, String rationale,
            String evidenceRef, long decidedEpochMs) {
        if (isBlank(decisionId) || isBlank(evaluationId)
                || !oneOf(decision, "PROMOTE", "REJECT", "SHADOW_ONLY")
                || isBlank(policyId) || isBlank(policyVersion) || isBlank(reviewerId)
                || isBlank(rationale) || isBlank(evidenceRef) || decidedEpochMs < 0)
            throw new IllegalArgumentException("قرار اعتماد التقييم ناقص أو غير صالح");
        SQLiteDatabase db = owner.scientificWritableDatabase();
        db.beginTransaction();
        try {
            try (Cursor c = db.rawQuery("SELECT decision FROM evaluation_runs WHERE evaluation_run_id=?",
                    new String[]{evaluationId})) {
                if (!c.moveToFirst()) throw new IllegalArgumentException("التقييم غير موجود");
                if ("PROMOTE".equals(decision) && !"FIELD_CANDIDATE".equals(c.getString(0)))
                    throw new IllegalArgumentException("لا يمكن ترقية تقييم محاكاة أو ظل");
            }
            if ("PROMOTE".equals(decision)) {
                try (Cursor c = db.rawQuery("SELECT status,policy_id,policy_version "
                        + "FROM evaluation_gate_results WHERE evaluation_run_id=? "
                        + "ORDER BY rowid DESC LIMIT 1", new String[]{evaluationId})) {
                    if (!c.moveToFirst() || !"ELIGIBLE_FOR_REVIEW".equals(c.getString(0))
                            || !policyId.equals(c.getString(1))
                            || !policyVersion.equals(c.getString(2)))
                        throw new IllegalArgumentException("PROMOTE يتطلب بوابة رقمية ناجحة بنفس السياسة والإصدار");
                }
                try (Cursor c = db.rawQuery("SELECT COUNT(*) FROM evaluation_items "
                        + "WHERE evaluation_run_id=? AND split='test'", new String[]{evaluationId})) {
                    if (!c.moveToFirst() || c.getInt(0) < 1)
                        throw new IllegalArgumentException("الترقية تتطلب مجموعة اختبار مستقلة");
                }
            }
            ContentValues v = new ContentValues();
            v.put("decision_id", decisionId); v.put("evaluation_run_id", evaluationId);
            v.put("decision", decision); v.put("policy_id", policyId);
            v.put("policy_version", policyVersion); v.put("reviewer_id", reviewerId);
            v.put("rationale", rationale); v.put("evidence_ref", evidenceRef);
            v.put("decided_epoch_ms", decidedEpochMs);
            db.insertOrThrow("evaluation_decisions", null, v);
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
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
                try (Cursor c = db.rawQuery("SELECT r.candidate_algorithm_id,r.candidate_algorithm_version,"
                        + "r.decision,(SELECT d.decision FROM evaluation_decisions d "
                        + "WHERE d.evaluation_run_id=r.evaluation_run_id ORDER BY d.rowid DESC LIMIT 1),"
                        + "(SELECT d.policy_id FROM evaluation_decisions d "
                        + "WHERE d.evaluation_run_id=r.evaluation_run_id ORDER BY d.rowid DESC LIMIT 1),"
                        + "(SELECT d.policy_version FROM evaluation_decisions d "
                        + "WHERE d.evaluation_run_id=r.evaluation_run_id ORDER BY d.rowid DESC LIMIT 1),"
                        + "(SELECT g.status FROM evaluation_gate_results g "
                        + "WHERE g.evaluation_run_id=r.evaluation_run_id ORDER BY g.rowid DESC LIMIT 1),"
                        + "(SELECT g.policy_id FROM evaluation_gate_results g "
                        + "WHERE g.evaluation_run_id=r.evaluation_run_id ORDER BY g.rowid DESC LIMIT 1),"
                        + "(SELECT g.policy_version FROM evaluation_gate_results g "
                        + "WHERE g.evaluation_run_id=r.evaluation_run_id ORDER BY g.rowid DESC LIMIT 1) "
                        + "FROM evaluation_runs r WHERE r.evaluation_run_id=?",
                        new String[]{input.evaluationRunId})) {
                    if (!c.moveToFirst()) throw new IllegalArgumentException("التقييم المرجعي غير موجود");
                    if ("activate".equals(input.action)) {
                        if (!input.newAlgorithmId.equals(c.getString(0))
                                || !input.newAlgorithmVersion.equals(c.getString(1))
                                || !"FIELD_CANDIDATE".equals(c.getString(2))
                                || !"PROMOTE".equals(c.getString(3))
                                || !"ELIGIBLE_FOR_REVIEW".equals(c.getString(6))
                                || !equalsNullable(c.getString(4), c.getString(7))
                                || !equalsNullable(c.getString(5), c.getString(8)))
                            throw new IllegalArgumentException("الاعتماد أو أحدث بوابة رقمية لا يطابق النسخة المطلوب تفعيلها");
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
