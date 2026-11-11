package com.islamlab.app;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.Settings;
import android.widget.Toast;

import androidx.core.content.FileProvider;

import org.json.JSONObject;

import java.io.File;
import java.io.InputStream;
import java.io.FileOutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** HTTPS update checker. Android remains responsible for signature verification and install consent. */
public final class UpdateCenter {
    private static final String MANIFEST_URL =
            "https://raw.githubusercontent.com/Khaledserdani/IslamDetector/feature/islam-lab-foundation/updates/channel.json";
    private static final long MAX_APK_BYTES = 150L * 1024L * 1024L;
    private static final ExecutorService WORKER = Executors.newSingleThreadExecutor();

    public interface Listener {
        void onMessage(String message);
        void onReady(File apk);
    }

    private UpdateCenter() {}

    public static void check(Activity activity, Listener listener) {
        WORKER.execute(() -> {
            try {
                JSONObject manifest = readManifest();
                int remoteCode = manifest.optInt("versionCode", 0);
                PackageInfo info = activity.getPackageManager().getPackageInfo(activity.getPackageName(), 0);
                long localCode = Build.VERSION.SDK_INT >= 28 ? info.getLongVersionCode() : info.versionCode;
                if (remoteCode <= localCode) {
                    post(activity, listener, "لا يوجد تحديث أحدث حالياً. الإصدار المثبت: " + info.versionName);
                    return;
                }
                String url = manifest.optString("apkUrl", "");
                String hash = manifest.optString("sha256", "").toLowerCase(Locale.ROOT);
                if (!url.startsWith("https://") || !hash.matches("[a-f0-9]{64}")) {
                    post(activity, listener, "التحديث متاح لكن ملفه أو بصمته غير مكتملة. لن ننزّل ملفاً غير موثوق.");
                    return;
                }
                post(activity, listener, "يوجد تحديث " + manifest.optString("versionName", "") + " — جارٍ تنزيله والتحقق منه…");
                File dir = activity.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
                if (dir == null) throw new IllegalStateException("مساحة التنزيل غير متاحة");
                File updates = new File(dir, "updates");
                if (!updates.exists() && !updates.mkdirs()) throw new IllegalStateException("تعذر إنشاء مجلد التحديثات");
                File apk = new File(updates, "islam-lab-update.apk");
                download(url, apk);
                String actual = sha256(apk);
                if (!actual.equals(hash)) {
                    apk.delete();
                    throw new SecurityException("فشل التحقق من بصمة الملف؛ حُذف التنزيل");
                }
                postReady(activity, listener, apk);
            } catch (Exception ex) {
                post(activity, listener, "تعذر التحديث: " + (ex.getMessage() == null ? "خطأ غير معروف" : ex.getMessage()));
            }
        });
    }

    public static void install(Activity activity, File apk) {
        try {
            if (Build.VERSION.SDK_INT >= 26 && !activity.getPackageManager().canRequestPackageInstalls()) {
                Intent settings = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                        Uri.parse("package:" + activity.getPackageName()));
                activity.startActivity(settings);
                Toast.makeText(activity, "اسمح لهذا التطبيق بطلب التثبيت، ثم ارجع واضغط فحص التحديثات.", Toast.LENGTH_LONG).show();
                return;
            }
            Uri uri = FileProvider.getUriForFile(activity,
                    activity.getPackageName() + ".fileprovider", apk);
            Intent intent = new Intent(Intent.ACTION_VIEW);
            intent.setDataAndType(uri, "application/vnd.android.package-archive");
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
            activity.startActivity(intent);
        } catch (Exception ex) {
            Toast.makeText(activity, "تعذر فتح مثبت أندرويد: " + ex.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private static JSONObject readManifest() throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(MANIFEST_URL).openConnection();
        c.setConnectTimeout(12000);
        c.setReadTimeout(12000);
        c.setRequestProperty("Accept", "application/json");
        try {
            if (c.getResponseCode() != 200) throw new IllegalStateException("خادم التحديثات غير متاح");
            StringBuilder b = new StringBuilder();
            try (InputStream in = c.getInputStream()) {
                byte[] buffer = new byte[4096];
                int n;
                while ((n = in.read(buffer)) != -1) {
                    if (b.length() + n > 65536) throw new IllegalStateException("ملف بيانات التحديث كبير جداً");
                    b.append(new String(buffer, 0, n, java.nio.charset.StandardCharsets.UTF_8));
                }
            }
            return new JSONObject(b.toString());
        } finally { c.disconnect(); }
    }

    private static void download(String address, File target) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(address).openConnection();
        c.setConnectTimeout(15000);
        c.setReadTimeout(30000);
        c.setInstanceFollowRedirects(true);
        try {
            if (c.getResponseCode() != 200) throw new IllegalStateException("فشل تنزيل ملف التحديث");
            long length = c.getContentLengthLong();
            if (length > MAX_APK_BYTES) throw new IllegalStateException("حجم التحديث يتجاوز الحد الآمن");
            long total = 0;
            try (InputStream in = c.getInputStream(); FileOutputStream out = new FileOutputStream(target)) {
                byte[] buffer = new byte[8192];
                int n;
                while ((n = in.read(buffer)) != -1) {
                    total += n;
                    if (total > MAX_APK_BYTES) throw new IllegalStateException("حجم التحديث يتجاوز الحد الآمن");
                    out.write(buffer, 0, n);
                }
                out.getFD().sync();
            }
            if (total < 1024) throw new IllegalStateException("ملف التحديث ناقص أو فارغ");
        } finally { c.disconnect(); }
    }

    private static String sha256(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream in = new java.io.FileInputStream(file)) {
            byte[] buffer = new byte[8192];
            int n;
            while ((n = in.read(buffer)) != -1) digest.update(buffer, 0, n);
        }
        StringBuilder out = new StringBuilder();
        for (byte b : digest.digest()) out.append(String.format(Locale.ROOT, "%02x", b & 0xff));
        return out.toString();
    }

    private static void post(Activity a, Listener l, String message) {
        a.runOnUiThread(() -> l.onMessage(message));
    }
    private static void postReady(Activity a, Listener l, File apk) {
        a.runOnUiThread(() -> l.onReady(apk));
    }
}