package com.islamlab.app;

import android.content.Context;
import org.json.JSONObject;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

/**
 * Installs data-only scientific packages. Packages never contain executable code.
 * Each package is a UTF-8 JSON object: schemaVersion, id, title, version, type, data.
 */
public final class ModuleCenter {
    private static final int MAX_PACKAGE_BYTES = 5 * 1024 * 1024;
    private static final String ID_PATTERN = "[a-z0-9][a-z0-9._-]{1,63}";
    private ModuleCenter() {}

    public static final class InstalledModule {
        public final String id, title, version, type;
        public final File file;
        InstalledModule(String id, String title, String version, String type, File file) {
            this.id=id; this.title=title; this.version=version; this.type=type; this.file=file;
        }
        @Override public String toString() {
            return title + "  •  " + version + "  (" + type + ")";
        }
    }

    public static InstalledModule install(Context context, InputStream input) throws Exception {
        File dir = moduleDir(context);
        if (!dir.exists() && !dir.mkdirs()) throw new IllegalStateException("تعذر إنشاء مجلد الوحدات");
        File temp = new File(dir, ".incoming.tmp");
        try {
            try (InputStream in = input; FileOutputStream out = new FileOutputStream(temp)) {
                byte[] buffer = new byte[8192];
                int n; long total = 0;
                while ((n = in.read(buffer)) != -1) {
                    total += n;
                    if (total > MAX_PACKAGE_BYTES) throw new IllegalArgumentException("حجم الحزمة يتجاوز 5 ميغابايت");
                    out.write(buffer, 0, n);
                }
                out.getFD().sync();
            }
            byte[] bytes;
            try (FileInputStream in = new FileInputStream(temp)) {
                bytes = new byte[(int) temp.length()];
                int offset = 0, n;
                while (offset < bytes.length && (n = in.read(bytes, offset, bytes.length-offset)) > 0) offset += n;
                if (offset != bytes.length) throw new IllegalStateException("تعذرت قراءة الحزمة كاملة");
            }
            JSONObject pkg = new JSONObject(new String(bytes, StandardCharsets.UTF_8));
            if (pkg.optInt("schemaVersion", -1) != 1) throw new IllegalArgumentException("إصدار بنية الحزمة غير مدعوم");
            String id = pkg.optString("id", "");
            String title = pkg.optString("title", "").trim();
            String version = pkg.optString("version", "").trim();
            String type = pkg.optString("type", "").trim();
            if (!id.matches(ID_PATTERN)) throw new IllegalArgumentException("معرّف الوحدة غير صالح");
            if (title.isEmpty() || title.length() > 100) throw new IllegalArgumentException("اسم الوحدة غير صالح");
            if (version.isEmpty() || version.length() > 40) throw new IllegalArgumentException("رقم إصدار الوحدة غير صالح");
            if (!("dataset".equals(type) || "model-config".equals(type) || "experiment-template".equals(type)))
                throw new IllegalArgumentException("نوع الوحدة غير مسموح");
            if (!pkg.has("data") || pkg.isNull("data")) throw new IllegalArgumentException("محتوى الوحدة مفقود");
            File target = new File(dir, id + ".json");
            File backup = new File(dir, id + ".json.bak");
            if (target.exists() && !target.renameTo(backup)) throw new IllegalStateException("تعذر تجهيز النسخة السابقة");
            if (!temp.renameTo(target)) {
                if (backup.exists()) backup.renameTo(target);
                throw new IllegalStateException("تعذر تثبيت الوحدة");
            }
            if (backup.exists()) backup.delete();
            return new InstalledModule(id, title, version, type, target);
        } finally {
            if (temp.exists()) temp.delete();
        }
    }

    public static List<InstalledModule> list(Context context) {
        File dir = moduleDir(context);
        File[] files = dir.listFiles((d, name) -> name.endsWith(".json") && !name.startsWith("."));
        List<InstalledModule> result = new ArrayList<>();
        if (files == null) return result;
        for (File file : files) {
            try (FileInputStream in = new FileInputStream(file)) {
                if (file.length() > MAX_PACKAGE_BYTES) continue;
                byte[] bytes = new byte[(int)file.length()];
                int offset=0, n;
                while(offset<bytes.length && (n=in.read(bytes,offset,bytes.length-offset))>0) offset+=n;
                if(offset!=bytes.length) continue;
                JSONObject pkg = new JSONObject(new String(bytes, StandardCharsets.UTF_8));
                String id=pkg.optString("id","");
                if (!id.matches(ID_PATTERN) || !file.getName().equals(id + ".json")) continue;
                result.add(new InstalledModule(id, pkg.optString("title",id),
                        pkg.optString("version","?"), pkg.optString("type","unknown"), file));
            } catch (Exception ignored) { }
        }
        Collections.sort(result, Comparator.comparing(m -> m.title.toLowerCase(java.util.Locale.ROOT)));
        return result;
    }

    public static boolean delete(Context context, String id) {
        if (id == null || !id.matches(ID_PATTERN)) return false;
        File file = new File(moduleDir(context), id + ".json");
        return !file.exists() || file.delete();
    }

    private static File moduleDir(Context context) {
        return new File(context.getFilesDir(), "scientific_modules");
    }
}
