package com.islamlab.app;

import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.zip.CRC32;

/**
 * Loads only independently recorded TEST observations from the immutable local store.
 * Ground truth comes from the latest confirmed review event; detector outputs come from
 * the versioned evaluation item. This loader never reads TRAIN/VALIDATION as test evidence.
 */
public final class EvaluationObservationLoader {
    private EvaluationObservationLoader() {}

    public static List<EvaluationPolicyEvaluator.Observation> loadHeldOutTest(
            ExperimentStore owner, String evaluationId) {
        if (owner == null || blank(evaluationId))
            throw new IllegalArgumentException("مرجع التقييم مطلوب");
        SQLiteDatabase db = owner.scientificReadableDatabase();
        String manifestJson, manifestHash, championId, championVersion, candidateId, candidateVersion, decision;
        try (Cursor run = db.rawQuery("SELECT dataset_manifest_json,dataset_manifest_sha256,"
                + "champion_algorithm_id,champion_algorithm_version,candidate_algorithm_id,"
                + "candidate_algorithm_version,decision FROM evaluation_runs WHERE evaluation_run_id=?",
                new String[]{evaluationId})) {
            if (!run.moveToFirst()) throw new IllegalArgumentException("التقييم غير موجود");
            manifestJson=run.getString(0); manifestHash=run.getString(1);
            championId=run.getString(2); championVersion=run.getString(3);
            candidateId=run.getString(4); candidateVersion=run.getString(5);
            decision=run.getString(6);
        }
        if (!"FIELD_CANDIDATE".equals(decision) || blank(championId) || blank(championVersion)
                || blank(candidateId) || blank(candidateVersion))
            throw new IllegalArgumentException("هذا السجل ليس مقارنة ميدانية صالحة بين Champion وCandidate");
        if (!manifestHash.equals(sha256(manifestJson.getBytes(java.nio.charset.StandardCharsets.UTF_8))))
            throw new IllegalStateException("بصمة بيان الاختبار لا تطابق محتواه");

        final Map<String, JSONObject> manifestItems = new HashMap<>();
        try {
            JSONObject root = new JSONObject(manifestJson);
            if (!"islam-dataset-manifest-v1".equals(root.optString("manifest_schema"))
                    || !evaluationId.equals(root.optString("manifest_id")))
                throw new IllegalArgumentException("نوع أو معرف بيان الاختبار غير صحيح");
            JSONArray entries = root.getJSONArray("items");
            for (int i=0;i<entries.length();i++) {
                JSONObject entry=entries.getJSONObject(i);
                String id=entry.optString("capture_id", "");
                if (blank(id) || manifestItems.put(id, entry) != null)
                    throw new IllegalArgumentException("معرف عينة مكرر في البيان");
            }
        } catch (JSONException ex) {
            throw new IllegalArgumentException("بيان الاختبار غير قابل للقراءة", ex);
        }

        List<EvaluationPolicyEvaluator.Observation> observations = new ArrayList<>();
        Set<String> groups = new HashSet<>();
        int testManifestCount=0;
        for (JSONObject entry : manifestItems.values()) {
            if ("test".equals(entry.optString("split"))) testManifestCount++;
        }

        try (Cursor rows = db.rawQuery("SELECT i.capture_id,i.group_key,c.source_type,c.transport_status,c.payload_blob,c.payload_sha256,c.payload_crc32,"
                + "c.payload_length_bytes,rv.new_lifecycle_status,rv.new_ground_truth_status,"
                + "rv.target_class,rv.soil_class,rv.ground_truth_positive "
                + "FROM evaluation_items i JOIN captures c ON c.capture_id=i.capture_id "
                + "LEFT JOIN review_events rv ON rv.event_id=(SELECT event_id FROM review_events "
                + "WHERE capture_id=i.capture_id ORDER BY rowid DESC LIMIT 1) "
                + "WHERE i.evaluation_run_id=? AND i.split='test' ORDER BY i.capture_id",
                new String[]{evaluationId})) {
            while (rows.moveToNext()) {
                String captureId=rows.getString(0), groupKey=rows.getString(1);
                JSONObject entry=manifestItems.get(captureId);
                if (entry == null || !"test".equals(entry.optString("split"))
                        || !groupKey.equals(entry.optString("group_key")))
                    throw new IllegalStateException("عناصر TEST لا تطابق بيان مجموعة البيانات");
                byte[] payload=rows.getBlob(4);
                if (!"instrument".equals(rows.getString(2)) && !"islam_detector".equals(rows.getString(2)))
                    throw new IllegalArgumentException("بيانات TEST ليست التقاطاً من جهاز قياس موثق");
                if (!"complete".equals(rows.getString(3)) || payload == null
                        || payload.length != rows.getInt(7)
                        || !rows.getString(5).equals(sha256(payload))
                        || !rows.getString(6).equals(crc32(payload)))
                    throw new IllegalStateException("حمولة TEST ناقصة أو لا تطابق بصمتها");
                if (!rows.getString(5).equals(entry.optString("payload_sha256"))
                        || !rows.getString(2).equals(entry.optString("source_type"))
                        || !rows.getString(3).equals(entry.optString("transport_status")))
                    throw new IllegalStateException("بيان TEST لا يطابق الالتقاط الأصلي");
                if (!"ELIGIBLE_FOR_TRAINING".equals(rows.getString(8))
                        || !"CONFIRMED".equals(rows.getString(9))
                        || blank(rows.getString(10)) || blank(rows.getString(11))
                        || rows.isNull(12))
                    throw new IllegalArgumentException("الحقيقة الأرضية أو فئة الهدف/التربة غير مؤكدة");
                if (!rows.getString(10).equals(entry.optString("target_class"))
                        || !rows.getString(11).equals(entry.optString("soil_class"))
                        || entry.isNull("ground_truth_positive")
                        || entry.getBoolean("ground_truth_positive") != (rows.getInt(12)==1))
                    throw new IllegalStateException("بيان الحقيقة الأرضية لا يطابق آخر مراجعة");

                try (Cursor usage = db.rawQuery("SELECT COUNT(*) FROM dataset_usage_events "
                        + "WHERE capture_id=? AND dataset_manifest_id=? AND dataset_manifest_sha256=? "
                        + "AND usage_role='TEST' AND consumer_id=? AND consumer_version=? AND run_id=?",
                        new String[]{captureId,evaluationId,manifestHash,candidateId,candidateVersion,evaluationId})) {
                    if (!usage.moveToFirst() || usage.getInt(0) != 1)
                        throw new IllegalStateException("سجل استخدام TEST غير موجود أو غير فريد");
                }

                boolean championDetected = ScientificCaptureStore.requireCompletedDetectionRun(
                        db, captureId, championId, championVersion, rows.getString(5));
                boolean candidateDetected = ScientificCaptureStore.requireCompletedDetectionRun(
                        db, captureId, candidateId, candidateVersion, rows.getString(5));
                if (!groups.add(groupKey))
                    throw new IllegalArgumentException("تكررت المجموعة المستقلة في TEST");
                observations.add(new EvaluationPolicyEvaluator.Observation(
                        "test", groupKey, rows.getString(10), rows.getString(11),
                        rows.getInt(12)==1, championDetected, candidateDetected));
            }
        } catch (JSONException ex) {
            throw new IllegalStateException("تعذر التحقق من بيانات الحقيقة الأرضية", ex);
        }
        if (observations.size() != testManifestCount)
            throw new IllegalStateException("عدد حالات TEST لا يطابق البيان المختوم");
        return Collections.unmodifiableList(observations);
    }

    private static String sha256(byte[] bytes) {
        try {
            byte[] digest=MessageDigest.getInstance("SHA-256").digest(bytes);
            StringBuilder out=new StringBuilder(64);
            for (byte b:digest) out.append(String.format(Locale.US,"%02x",b & 0xff));
            return out.toString();
        } catch (Exception ex) { throw new IllegalStateException("تعذر حساب SHA-256",ex); }
    }

    private static String crc32(byte[] bytes) {
        CRC32 crc=new CRC32(); crc.update(bytes);
        return String.format(Locale.US,"%08x",crc.getValue());
    }

    private static boolean blank(String value) { return value==null || value.trim().isEmpty(); }
}
