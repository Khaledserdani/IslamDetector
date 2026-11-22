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
    static final int MAX_TASKS = 500;
    static final int MAX_TITLE_CHARS = 80;
    static final int MAX_DESCRIPTION_CHARS = 65536;
    private final SharedPreferences preferences;
    AgentTaskStore(Context context) {
        preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }
    synchronized List<Task> all() {
        ArrayList<Task> tasks = new ArrayList<>();
        try {
            JSONArray array = new JSONArray(preferences.getString(KEY_TASKS, "[]"));
            for (int i=0;i<array.length();i++) {
                JSONObject item=array.optJSONObject(i); if(item==null) continue;
                String id=item.optString("id",""), title=item.optString("title","").trim();
                String description=item.optString("description",title);
                if(id.isEmpty()||title.isEmpty()) continue;
                tasks.add(new Task(id,title,description,item.optBoolean("done",false),item.optString("result","")));
            }
        } catch(JSONException ignored) { }
        return tasks;
    }
    synchronized Task add(String title) { return add(title,title); }
    synchronized Task add(String title,String description) {
        String t=title==null?"":title.trim(), d=description==null?"":description.trim();
        if(t.isEmpty()) throw new IllegalArgumentException("عنوان المهمة فارغ");
        if(t.length()>MAX_TITLE_CHARS) throw new IllegalArgumentException("العنوان تجاوز الحد الآمن للتخزين (8192 حرفاً)");
        if(d.isEmpty()) throw new IllegalArgumentException("وصف المهمة فارغ");
        if(d.length()>MAX_DESCRIPTION_CHARS) throw new IllegalArgumentException("وصف المهمة تجاوز الحد الآمن للتخزين (65536 حرفاً)");
        List<Task> tasks=all(); if(tasks.size()>=MAX_TASKS) throw new IllegalStateException("وصلت إلى الحد الأقصى للمهام المحفوظة (500)");
        Task task=new Task(UUID.randomUUID().toString(),t,d,false,""); tasks.add(0,task); save(tasks); return task;
    }
    synchronized boolean contains(String id) {
        if(id==null||id.isEmpty()) return false;
        for(Task task:all()) if(task.id.equals(id)) return true;
        return false;
    }
    synchronized boolean setDone(String id,boolean done) {
        List<Task> tasks=all();
        for(Task task:tasks) if(task.id.equals(id)) { task.done=done; save(tasks); return true; }
        return false;
    }
    synchronized boolean setExecutionResult(String id,boolean done,String result) {
        List<Task> tasks=all();
        for(Task task:tasks) if(task.id.equals(id)) {
            task.done=done; task.result=result==null?"":result; save(tasks); return true;
        }
        return false;
    }
    synchronized boolean delete(String id) {
        List<Task> tasks=all(); boolean removed=tasks.removeIf(t->t.id.equals(id));
        if(removed) save(tasks); return removed;
    }
    private void save(List<Task> tasks) {
        JSONArray array=new JSONArray();
        for(Task task:tasks) {
            JSONObject item=new JSONObject();
            try {
                item.put("id",task.id); item.put("title",task.title); item.put("description",task.description);
                item.put("done",task.done); item.put("result",task.result); array.put(item);
            } catch(JSONException impossible) { throw new IllegalStateException(impossible); }
        }
        if(!preferences.edit().putString(KEY_TASKS,array.toString()).commit())
            throw new IllegalStateException("تعذر حفظ قائمة المهام على الهاتف");
    }
    static final class Task {
        final String id,title,description; boolean done; String result;
        Task(String id,String title,boolean done) { this(id,title,title,done,""); }
        Task(String id,String title,boolean done,String result) { this(id,title,title,done,result); }
        Task(String id,String title,String description,boolean done,String result) {
            this.id=id; this.title=title; this.description=description==null?title:description;
            this.done=done; this.result=result==null?"":result;
        }
    }
}