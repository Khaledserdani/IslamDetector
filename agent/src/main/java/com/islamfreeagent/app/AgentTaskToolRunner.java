package com.islamfreeagent.app;
import android.content.Context;
import android.util.AtomicFile;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.regex.Pattern;

/** Restricted local TXT tool: no arbitrary paths, shell commands, or network. */
final class AgentTaskToolRunner {
    private static final Pattern SAFE_NAME=Pattern.compile("[A-Za-z0-9][A-Za-z0-9._-]{0,59}\\.txt");
    private static final int MAX_CONTENT_BYTES=16*1024, MAX_FILES=20;
    private final File workspace;
    AgentTaskToolRunner(Context context) {
        File external=context.getExternalFilesDir("agent_workspace");
        workspace=external!=null?external:new File(context.getFilesDir(),"agent_workspace");
    }
    AgentTaskToolRunner(File workspace) { this.workspace=workspace; }

    static void validate(JSONObject plan) throws Exception {
        if(plan==null) throw new IllegalArgumentException("خطة التنفيذ فارغة");
        String action=plan.optString("action","");
        if("write_and_read_text_file".equals(action)) {
            requireKeys(plan,new HashSet<>(Arrays.asList("action","filename","content")));
            validateFile(plan.getString("filename"),plan.getString("content")); return;
        }
        if(!"write_and_read_text_files".equals(action)) throw new IllegalArgumentException("الأداة المطلوبة غير مسموحة");
        requireKeys(plan,new HashSet<>(Arrays.asList("action","files")));
        JSONArray files=plan.getJSONArray("files");
        if(files.length()<1||files.length()>MAX_FILES) throw new IllegalArgumentException("يسمح من ملف واحد إلى 20 ملفاً");
        Set<String> names=new HashSet<>(); int total=0;
        for(int i=0;i<files.length();i++) {
            JSONObject file=files.getJSONObject(i);
            requireKeys(file,new HashSet<>(Arrays.asList("filename","content")));
            String name=file.getString("filename"), body=file.getString("content");
            validateFile(name,body);
            if(!names.add(name)) throw new IllegalArgumentException("اسم ملف مكرر: "+name);
            total+=body.getBytes(StandardCharsets.UTF_8).length;
        }
        if(total>MAX_FILES*MAX_CONTENT_BYTES) throw new IllegalArgumentException("الحجم الإجمالي يتجاوز الحد المسموح");
    }
    private static void requireKeys(JSONObject object,Set<String> expected) {
        Set<String> keys=new HashSet<>(); Iterator<String> it=object.keys(); while(it.hasNext()) keys.add(it.next());
        if(!keys.equals(expected)) throw new IllegalArgumentException("حقول خطة التنفيذ غير مطابقة");
    }
    private static void validateFile(String name,String body) {
        if(!SAFE_NAME.matcher(name).matches()||name.contains("..")) throw new IllegalArgumentException("اسم الملف غير آمن؛ يسمح باسم TXT بسيط فقط");
        if(body.indexOf('\0')>=0||body.getBytes(StandardCharsets.UTF_8).length>MAX_CONTENT_BYTES)
            throw new IllegalArgumentException("محتوى الملف يتجاوز الحد المسموح");
    }
    JSONObject execute(JSONObject plan) throws Exception {
        validate(plan);
        JSONArray files;
        if("write_and_read_text_file".equals(plan.getString("action"))) {
            files=new JSONArray().put(new JSONObject().put("filename",plan.getString("filename")).put("content",plan.getString("content")));
        } else files=plan.getJSONArray("files");
        if(!workspace.exists()&&!workspace.mkdirs()) throw new IllegalStateException("تعذر إنشاء مجلد عمل التطبيق");
        File root=workspace.getCanonicalFile();
        List<File> targets=new ArrayList<>(); List<byte[]> backups=new ArrayList<>(); List<Boolean> existed=new ArrayList<>();
        for(int i=0;i<files.length();i++) {
            File target=new File(root,files.getJSONObject(i).getString("filename")).getCanonicalFile();
            if(!root.equals(target.getParentFile())) throw new SecurityException("مسار الملف خارج مجلد العمل");
            if(target.exists() && !target.isFile())
                throw new IllegalArgumentException("المسار موجود لكنه ليس ملفاً عادياً: " + target.getName());
            targets.add(target); existed.add(target.isFile()); backups.add(target.isFile()?readBytes(target):null);
        }
        JSONArray results=new JSONArray(); int written=0;
        try {
            for(int i=0;i<files.length();i++) {
                JSONObject spec=files.getJSONObject(i); String body=spec.getString("content");
                File target=targets.get(i); AtomicFile atomic=new AtomicFile(target);
                FileOutputStream out=atomic.startWrite();
                try { out.write(body.getBytes(StandardCharsets.UTF_8)); out.getFD().sync(); atomic.finishWrite(out); }
                catch(Exception error) { atomic.failWrite(out); throw error; }
                written++;
                String readBack=new String(readBytes(target),StandardCharsets.UTF_8);
                if(!body.equals(readBack)) throw new IllegalStateException("فشل التحقق من الملف: "+target.getName());
                results.put(new JSONObject().put("filename",target.getName()).put("path",target.getAbsolutePath())
                    .put("bytes",body.getBytes(StandardCharsets.UTF_8).length).put("content",readBack).put("verified",true));
            }
        } catch(Exception failure) {
            for(int i=0;i<written;i++) {
                try {
                    File target=targets.get(i);
                    if(existed.get(i)) {
                        AtomicFile atomic=new AtomicFile(target); FileOutputStream out=atomic.startWrite();
                        try { out.write(backups.get(i)); out.getFD().sync(); atomic.finishWrite(out); }
                        catch(Exception rollback) { atomic.failWrite(out); throw rollback; }
                    } else new AtomicFile(target).delete();
                } catch(Exception rollbackFailure) { failure.addSuppressed(rollbackFailure); }
            }
            throw failure;
        }
        return new JSONObject().put("verified",true).put("files",results);
    }
    private static byte[] readBytes(File file) throws Exception {
        try(FileInputStream in=new FileInputStream(file); ByteArrayOutputStream buffer=new ByteArrayOutputStream()) {
            byte[] chunk=new byte[4096]; int count;
            while((count=in.read(chunk))!=-1) {
                if(buffer.size()+count>MAX_CONTENT_BYTES) throw new IllegalStateException("الملف المقروء تجاوز الحد المسموح");
                buffer.write(chunk,0,count);
            }
            return buffer.toByteArray();
        }
    }
}