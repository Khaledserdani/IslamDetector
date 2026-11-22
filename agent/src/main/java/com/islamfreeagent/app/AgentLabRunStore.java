package com.islamfreeagent.app;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.UUID;

/** Bounded, append-only local provenance ledger for verified laboratory runs. */
final class AgentLabRunStore {
    private static final String PREFS = "islam_free_agent_lab_history";
    private static final String KEY_RUNS = "runs_json";
    private static final int MAX_RUNS = 200;

    private AgentLabRunStore() {}

    static synchronized String record(Context context, String labId, String engineVersion,
                                      String source, JSONObject inputs, JSONObject outputs,
                                      boolean verified, String verification) {
        return record(context, labId, engineVersion, source, inputs, outputs,
                verified, verification, null);
    }

    /** sourceRef makes scheduled-worker recording idempotent across a queue retry. */
    static synchronized String record(Context context, String labId, String engineVersion,
                                      String source, JSONObject inputs, JSONObject outputs,
                                      boolean verified, String verification, String sourceRef) {
        if (context == null) throw new IllegalArgumentException("سياق حفظ سجل المختبر غير متوفر");
        if (labId == null || labId.trim().isEmpty()) throw new IllegalArgumentException("معرّف المختبر فارغ");
        SharedPreferences prefs = context.getApplicationContext()
                .getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        JSONArray runs = read(prefs);
        if (sourceRef != null && !sourceRef.trim().isEmpty()) {
            for (int i = 0; i < runs.length(); i++) {
                JSONObject old = runs.optJSONObject(i);
                if (sourceRef.equals(old.optString("source_ref", ""))) {
                    return old.optString("run_id");
                }
            }
        }
        String id = UUID.randomUUID().toString();
        JSONObject item = new JSONObject();
        try {
            item.put("run_id", id);
            item.put("lab_id", labId);
            item.put("engine_version", engineVersion);
            item.put("source", source);
            if (sourceRef != null && !sourceRef.trim().isEmpty()) item.put("source_ref", sourceRef);
            item.put("created_at_epoch_ms", System.currentTimeMillis());
            item.put("inputs", inputs == null ? new JSONObject() : new JSONObject(inputs.toString()));
            item.put("outputs", outputs == null ? new JSONObject() : new JSONObject(outputs.toString()));
            item.put("verified", verified);
            item.put("verification", verification == null ? "" : verification);
            JSONArray next = new JSONArray().put(item);
            for (int i = 0; i < runs.length() && i < MAX_RUNS - 1; i++) {
                JSONObject old = runs.optJSONObject(i);
                if (old != null) next.put(old);
            }
            if (!prefs.edit().putString(KEY_RUNS, next.toString()).commit()) {
                throw new IllegalStateException("تعذر حفظ سجل تجربة المختبر");
            }
        } catch (JSONException error) {
            throw new IllegalStateException("تعذر إنشاء سجل تجربة المختبر", error);
        }
        return id;
    }

    static synchronized JSONArray recent(Context context, int limit) {
        if (context == null) return new JSONArray();
        final JSONArray source;
        try {
            source = read(context.getApplicationContext()
                    .getSharedPreferences(PREFS, Context.MODE_PRIVATE));
        } catch (IllegalStateException corrupt) {
            return new JSONArray();
        }
        JSONArray result = new JSONArray();
        for (int i = 0; i < source.length() && i < Math.max(0, Math.min(limit, 50)); i++) {
            JSONObject item = source.optJSONObject(i);
            if (item != null) result.put(item);
        }
        return result;
    }

    static synchronized String summary(Context context) {
        final JSONArray runs;
        try {
            runs = read(context.getApplicationContext()
                    .getSharedPreferences(PREFS, Context.MODE_PRIVATE));
        } catch (IllegalStateException corrupt) {
            return "تحذير: تعذرت قراءة سجل المختبر؛ أوقفنا الحفظ لحماية السجلات";
        }
        int verified = 0, unverified = 0;
        for (int i = 0; i < runs.length(); i++) {
            JSONObject item = runs.optJSONObject(i);
            if (item == null) continue;
            if (item.optBoolean("verified", false)) verified++; else unverified++;
        }
        return "سجل المختبر: " + runs.length() + " تجربة • متحققة عددياً: " + verified
                + " • تحتاج مراجعة: " + unverified;
    }

    private static JSONArray read(SharedPreferences prefs) {
        String raw = prefs.getString(KEY_RUNS, null);
        if (raw == null) return new JSONArray();
        try {
            JSONArray runs = new JSONArray(raw);
            for (int i = 0; i < runs.length(); i++) {
                if (runs.optJSONObject(i) == null) {
                    throw new IllegalStateException("عنصر غير صالح في سجل المختبر؛ لم نغيّر البيانات");
                }
            }
            return runs;
        } catch (JSONException error) {
            throw new IllegalStateException("سجل المختبر تالف؛ أوقفنا الحفظ لحماية السجلات", error);
        }
    }
}
