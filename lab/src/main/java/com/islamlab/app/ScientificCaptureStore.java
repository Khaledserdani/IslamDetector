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
                    null, null, payloadFormat, payload, sampleCount, transportStatus, createdEpochMs);
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
