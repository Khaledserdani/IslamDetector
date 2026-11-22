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
        if (jobs.length() >= MAX_JOBS) throw new IllegalStateException("قائمة المختبر ممتلئة (100 تجربة)");
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
    static void validateJob(JSONObject job) throws Exception {
        if (job == null) throw new IllegalArgumentException("تجربة المختبر فارغة");
        JSONObject plan = new JSONObject()
                .put("action", "simulate_lab")
                .put("lab_id", AgentLabRunner.DC_LAB_ID)
                .put("ground", "0")
                .put("source_node", "vcc")
                .put("source_voltage_v", job.getDouble("volts"))
                .put("resistors", job.getJSONArray("resistors"));
        AgentLabRunner.validate(plan);
    }

    static synchronized JSONObject nextPending(Context context) {
        JSONArray jobs = read(context.getSharedPreferences(PREFS, Context.MODE_PRIVATE));
        for (int i = 0; i < jobs.length(); i++) {
            JSONObject job = jobs.optJSONObject(i);
            if (job != null && "pending".equals(job.optString("status"))) return job;
        }
        return null;
    }

    static synchronized void finish(Context context, String id, JSONObject result, String error) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        JSONArray jobs = read(prefs);
        for (int i = 0; i < jobs.length(); i++) {
            JSONObject job = jobs.optJSONObject(i);
            if (job == null || !id.equals(job.optString("id"))) continue;
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
    }

    static synchronized String summary(Context context) {
        JSONArray jobs = read(context.getSharedPreferences(PREFS, Context.MODE_PRIVATE));
        int pending = 0, completed = 0, failed = 0;
        for (int i = 0; i < jobs.length(); i++) {
            JSONObject job = jobs.optJSONObject(i);
            if (job == null) continue;
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
        try {
            return new JSONArray(prefs.getString(KEY_QUEUE, "[]"));
        } catch (JSONException error) {
            return new JSONArray();
        }
    }

    private static void save(SharedPreferences prefs, JSONArray jobs) {
        if (!prefs.edit().putString(KEY_QUEUE, jobs.toString()).commit()) {
            throw new IllegalStateException("تعذر حفظ قائمة المختبر");
        }
    }
}
