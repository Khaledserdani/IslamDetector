package com.islamfreeagent.app;

import android.content.Context;
import android.util.AtomicFile;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Narrow, local-only task tool. It can create and read one plain-text file
 * inside the app's own workspace; it cannot access arbitrary paths, shell, or network.
 */
final class AgentTaskToolRunner {
    private static final Pattern SAFE_NAME = Pattern.compile("[A-Za-z0-9][A-Za-z0-9._-]{0,59}\\.txt");
    private static final int MAX_CONTENT_BYTES = 16 * 1024;
    private final File workspace;

    AgentTaskToolRunner(Context context) {
        File external = context.getExternalFilesDir("agent_workspace");
        this.workspace = external != null ? external : new File(context.getFilesDir(), "agent_workspace");
    }

    AgentTaskToolRunner(File workspace) {
        this.workspace = workspace;
    }

    static void validate(JSONObject plan) throws Exception {
        if (plan == null) throw new IllegalArgumentException("خطة التنفيذ فارغة");
        Set<String> keys = new HashSet<>();
        Iterator<String> iterator = plan.keys();
        while (iterator.hasNext()) keys.add(iterator.next());
        Set<String> expected = new HashSet<>();
        expected.add("action");
        expected.add("filename");
        expected.add("content");
        if (!keys.equals(expected)) throw new IllegalArgumentException("حقول خطة التنفيذ غير مطابقة");
        if (!"write_and_read_text_file".equals(plan.getString("action"))) {
            throw new IllegalArgumentException("الأداة المطلوبة غير مسموحة");
        }
        String filename = plan.getString("filename");
        if (!SAFE_NAME.matcher(filename).matches() || filename.contains("..")) {
            throw new IllegalArgumentException("اسم الملف غير آمن؛ يسمح باسم TXT بسيط فقط");
        }
        String content = plan.getString("content");
        if (content.indexOf('\0') >= 0
                || content.getBytes(StandardCharsets.UTF_8).length > MAX_CONTENT_BYTES) {
            throw new IllegalArgumentException("محتوى الملف فارغ البنية أو يتجاوز الحد المسموح");
        }
    }

    JSONObject execute(JSONObject plan) throws Exception {
        validate(plan);
        String filename = plan.getString("filename");
        String content = plan.getString("content");
        if (!workspace.exists() && !workspace.mkdirs()) {
            throw new IllegalStateException("تعذر إنشاء مجلد عمل التطبيق");
        }
        File root = workspace.getCanonicalFile();
        File target = new File(root, filename).getCanonicalFile();
        if (!root.equals(target.getParentFile())) {
            throw new SecurityException("مسار الملف خارج مجلد العمل");
        }

        AtomicFile atomic = new AtomicFile(target);
        byte[] bytes = content.getBytes(StandardCharsets.UTF_8);
        FileOutputStream output = atomic.startWrite();
        try {
            output.write(bytes);
            output.getFD().sync();
            atomic.finishWrite(output);
        } catch (Exception error) {
            atomic.failWrite(output);
            throw error;
        }

        String readBack;
        try (FileInputStream input = atomic.openRead();
             ByteArrayOutputStream buffer = new ByteArrayOutputStream()) {
            byte[] chunk = new byte[4096];
            int count;
            while ((count = input.read(chunk)) != -1) {
                if (buffer.size() + count > MAX_CONTENT_BYTES) {
                    throw new IllegalStateException("الملف المقروء تجاوز الحد المسموح");
                }
                buffer.write(chunk, 0, count);
            }
            readBack = new String(buffer.toByteArray(), StandardCharsets.UTF_8);
        }
        if (!content.equals(readBack)) {
            throw new IllegalStateException("فشل التحقق: المحتوى المقروء لا يطابق المكتوب");
        }

        JSONObject result = new JSONObject();
        result.put("verified", true);
        result.put("filename", filename);
        result.put("path", target.getAbsolutePath());
        result.put("bytes", bytes.length);
        result.put("content", readBack);
        return result;
    }
}
