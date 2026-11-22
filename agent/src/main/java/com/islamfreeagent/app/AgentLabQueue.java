package com.islamfreeagent.app;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.List;
import java.util.UUID;

/** Durable, bounded queue for local, non-actuating DC lab calculations. */
final class AgentLabQueue {
    private static final String PREFS = "islam_free_agent_lab";
    private static final String KEY_QUEUE = "dc_queue";
    private static final int MAX_JOBS = 100;

    private AgentLabQueue() {}

    static synchronized String enqueue(Context context, double volts,
                                       List<AgentDcLab.Resistor> resistors) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        JSONArray jobs = read(prefs);
        while (jobs.length() >= MAX_JOBS) {
            JSONArray compact = new JSONArray();
            boolean removedTerminal = false;
            for (int i = 0; i < jobs.length(); i++) {
                JSONObject old = jobs.optJSONObject(i);
                String status = old.optString("status", "");
                if (!removedTerminal && ("completed".equals(status) || "failed".equals(status))) {
                    removedTerminal = true;
                    continue;
                }
                compact.put(old);
            }
            if (!removedTerminal) {
                throw new IllegalStateException("قائمة المختبر ممتلئة بتجارب لم تنتهِ؛ لن نحذف أي تجربة معلقة");
            }
            jobs = compact;
        }
        JSONObject job = new JSONObject();
        String id = UUID.randomUUID().toString();
        try {
            job.put("id", id);
            job.put("volts", volts);
            job.put("status", "pending");
            JSONArray rs = new JSONArray();
            for (AgentDcLab.Resistor resistor : resistors) {
                JSONObject item = new JSONObject();
                item.put("a", resistor.a);
                item.put("b", resistor.b);
                item.put("ohms", resistor.ohms);
                rs.put(item);
            }
            job.put("resistors", rs);
            validateJob(job);
            jobs.put(job);
        } catch (JSONException impossible) {
            throw new IllegalStateException(impossible);
        }
        save(prefs, jobs);
        return id;
    }

    /** Re-apply the exact on-device runner limits to queued and persisted jobs. */
    static void validateJob(JSONObject job) {
        if (job == null) throw new IllegalArgumentException("تجربة المختبر فارغة");
        try {
            JSONObject plan = new JSONObject()
                    .put("action", "simulate_lab")
                    .put("lab_id", AgentLabRunner.DC_LAB_ID)
                    .put("ground", "0")
                    .put("source_node", "vcc")
                    .put("source_voltage_v", job.getDouble("volts"))
                    .put("resistors", job.getJSONArray("resistors"));
            AgentLabRunner.validate(plan);
        } catch (IllegalArgumentException error) {
            throw error;
        } catch (Exception error) {
            throw new IllegalArgumentException("بيانات تجربة المختبر غير صالحة", error);
        }
    }

    static synchronized JSONObject nextPending(Context context) {
        JSONArray jobs = read(context.getSharedPreferences(PREFS, Context.MODE_PRIVATE));
        for (int i = 0; i < jobs.length(); i++) {
            JSONObject job = jobs.optJSONObject(i);
            if ("pending".equals(job.optString("status"))) return job;
        }
        return null;
    }

    static synchronized void finish(Context context, String id, JSONObject result, String error) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        JSONArray jobs = read(prefs);
        for (int i = 0; i < jobs.length(); i++) {
            JSONObject job = jobs.optJSONObject(i);
            if (!id.equals(job.optString("id"))) continue;
            try {
                if (error == null) {
                    job.put("status", "completed");
                    job.put("result", result == null ? new JSONObject() : result);
                } else {
                    job.put("status", "failed");
                    job.put("error", error.substring(0, Math.min(300, error.length())));
                }
            } catch (JSONException impossible) {
                throw new IllegalStateException(impossible);
            }
            save(prefs, jobs);
            return;
        }
        throw new IllegalStateException("تعذر العثور على تجربة المختبر لتحديث حالتها");
    }

    static synchronized String summary(Context context) {
        final JSONArray jobs;
        try {
            jobs = read(context.getSharedPreferences(PREFS, Context.MODE_PRIVATE));
        } catch (IllegalStateException corrupt) {
            return "تحذير: تعذرت قراءة قائمة المختبر؛ أوقفنا التعديل لحماية البيانات";
        }
        int pending = 0, completed = 0, failed = 0;
        for (int i = 0; i < jobs.length(); i++) {
            JSONObject job = jobs.optJSONObject(i);
            switch (job.optString("status")) {
                case "pending": pending++; break;
                case "completed": completed++; break;
                case "failed": failed++; break;
                default: break;
            }
        }
        return "تجارب المختبر: " + jobs.length() + " • انتظار: " + pending
                + " • مكتملة: " + completed + " • فاشلة: " + failed;
    }

    private static JSONArray read(SharedPreferences prefs) {
        String raw = prefs.getString(KEY_QUEUE, null);
        if (raw == null) return new JSONArray();
        try {
            JSONArray jobs = new JSONArray(raw);
            for (int i = 0; i < jobs.length(); i++) {
                JSONObject job = jobs.optJSONObject(i);
                if (job == null || job.optString("id", "").trim().isEmpty()) {
                    throw new IllegalStateException("عنصر غير صالح داخل قائمة المختبر؛ لم نغيّر البيانات");
                }
                String status = job.optString("status", "");
                if (!"pending".equals(status) && !"completed".equals(status) && !"failed".equals(status)) {
                    throw new IllegalStateException("حالة تجربة غير معروفة؛ لم نغيّر بيانات القائمة");
                }
            }
            return jobs;
        } catch (JSONException error) {
            throw new IllegalStateException("بيانات قائمة المختبر تالفة؛ أوقفنا التعديل لحماية التجارب المحفوظة", error);
        }
    }

    private static void save(SharedPreferences prefs, JSONArray jobs) {
        if (!prefs.edit().putString(KEY_QUEUE, jobs.toString()).commit()) {
            throw new IllegalStateException("تعذر حفظ قائمة المختبر");
        }
    }
}
