package com.islamfreeagent.app;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

final class AgentTaskStore {
    private static final String PREFS = "islam_free_agent";
    private static final String KEY_TASKS = "tasks_json";
    private final SharedPreferences preferences;

    AgentTaskStore(Context context) {
        preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    synchronized List<Task> all() {
        ArrayList<Task> tasks = new ArrayList<>();
        String raw = preferences.getString(KEY_TASKS, "[]");
        try {
            JSONArray array = new JSONArray(raw);
            for (int i = 0; i < array.length(); i++) {
                JSONObject item = array.optJSONObject(i);
                if (item == null) continue;
                String id = item.optString("id", "");
                String title = item.optString("title", "").trim();
                if (id.isEmpty() || title.isEmpty()) continue;
                tasks.add(new Task(id, title, item.optBoolean("done", false)));
            }
        } catch (JSONException ignored) {
            // Corrupt local state is treated as an empty queue, never as executable work.
        }
        return tasks;
    }

    synchronized Task add(String title) {
        String clean = title == null ? "" : title.trim();
        if (clean.isEmpty()) throw new IllegalArgumentException("عنوان المهمة فارغ");
        if (clean.length() > 180) throw new IllegalArgumentException("عنوان المهمة طويل جداً");
        Task task = new Task(UUID.randomUUID().toString(), clean, false);
        List<Task> tasks = all();
        tasks.add(0, task);
        save(tasks);
        return task;
    }

    synchronized boolean setDone(String id, boolean done) {
        List<Task> tasks = all();
        boolean found = false;
        for (Task task : tasks) {
            if (task.id.equals(id)) {
                task.done = done;
                found = true;
                break;
            }
        }
        if (found) save(tasks);
        return found;
    }

    synchronized boolean delete(String id) {
        List<Task> tasks = all();
        boolean removed = false;
        for (int i = tasks.size() - 1; i >= 0; i--) {
            if (tasks.get(i).id.equals(id)) {
                tasks.remove(i);
                removed = true;
            }
        }
        if (removed) save(tasks);
        return removed;
    }

    private void save(List<Task> tasks) {
        JSONArray array = new JSONArray();
        for (Task task : tasks) {
            JSONObject item = new JSONObject();
            try {
                item.put("id", task.id);
                item.put("title", task.title);
                item.put("done", task.done);
                array.put(item);
            } catch (JSONException impossible) {
                throw new IllegalStateException(impossible);
            }
        }
        if (!preferences.edit().putString(KEY_TASKS, array.toString()).commit()) {
            throw new IllegalStateException("تعذر حفظ قائمة المهام على الهاتف");
        }
    }

    static final class Task {
        final String id;
        final String title;
        boolean done;

        Task(String id, String title, boolean done) {
            this.id = id;
            this.title = title;
            this.done = done;
        }
    }
}
