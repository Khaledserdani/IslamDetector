package com.islamfreeagent.app;

import android.content.Context;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.io.ByteArrayOutputStream;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Resumable, disk-backed model downloader. A network failure never deletes the .part file.
 * The final model is published only after the complete expected byte count is present;
 * SHA-256 verification remains a separate, mandatory step before loading the model.
 */
final class ResumableModelDownloader {
    interface Listener {
        void onProgress(long downloaded, long total, String message);
        void onComplete(File modelFile);
        void onFailure(String message, long preservedBytes);
    }

    private static final int CONNECT_TIMEOUT_MS = 20000;
    private static final int READ_TIMEOUT_MS = 30000;
    private static final int MAX_ATTEMPTS = 8;
    private final File destination;
    private final File partial;
    private final File validatorFile;
    private final AtomicBoolean cancelled = new AtomicBoolean(false);

    ResumableModelDownloader(Context context) {
        File directory = context.getExternalFilesDir(null);
        if (directory == null) throw new IllegalStateException("مساحة ملفات التطبيق غير متاحة");
        destination = new File(directory, OnDeviceModelSpec.FILE_NAME);
        partial = new File(directory, OnDeviceModelSpec.FILE_NAME + ".part");
        validatorFile = new File(directory, OnDeviceModelSpec.FILE_NAME + ".etag");
    }

    void cancel() {
        cancelled.set(true);
    }

    void download(Listener listener) {
        long total = OnDeviceModelSpec.EXPECTED_BYTES;
        for (int attempt = 1; attempt <= MAX_ATTEMPTS && !cancelled.get(); attempt++) {
            HttpURLConnection connection = null;
            try {
                long offset = partial.isFile() ? partial.length() : 0L;
                if (offset > total) {
                    throw new IOException("حجم الجزء المحفوظ أكبر من الحجم المتوقع؛ أوقفنا الاستكمال لحماية الملف.");
                }
                if (offset == total) {
                    publishCompletedFile(listener);
                    return;
                }

                connection = (HttpURLConnection) new URL(OnDeviceModelSpec.DOWNLOAD_URL).openConnection();
                connection.setRequestMethod("GET");
                connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
                connection.setReadTimeout(READ_TIMEOUT_MS);
                connection.setInstanceFollowRedirects(true);
                connection.setRequestProperty("Accept-Encoding", "identity");
                String savedValidator = readValidator();
                if (offset > 0) {
                    connection.setRequestProperty("Range", "bytes=" + offset + "-");
                    String ifRange = ifRangeValue(savedValidator);
                    if (ifRange != null) connection.setRequestProperty("If-Range", ifRange);
                }

                int status = connection.getResponseCode();
                if (offset > 0 && status != HttpURLConnection.HTTP_PARTIAL) {
                    throw new IOException("الخادم لم يقبل استكمال التنزيل (HTTP " + status
                            + "). احتفظنا بالـ " + offset + " بايت المحفوظة ولم نحذفها.");
                }
                if (offset == 0 && status != HttpURLConnection.HTTP_OK
                        && status != HttpURLConnection.HTTP_PARTIAL) {
                    throw new IOException("الخادم رفض التنزيل (HTTP " + status + ").");
                }

                if (status == HttpURLConnection.HTTP_PARTIAL) {
                    String range = connection.getHeaderField("Content-Range");
                    String expectedPrefix = "bytes " + offset + "-";
                    if (range == null || !range.startsWith(expectedPrefix)) {
                        throw new IOException("استجابة الاستكمال غير متطابقة؛ الجزء السابق محفوظ كما هو.");
                    }
                }

                String responseValidator = responseValidator(connection);
                if (offset > 0 && status == HttpURLConnection.HTTP_PARTIAL
                        && savedValidator != null && responseValidator != null
                        && !savedValidator.equals(responseValidator)) {
                    throw new IOException("تغيّرت نسخة الملف على الخادم؛ احتفظنا بالجزء السابق ولم نخلطه بالنسخة الجديدة.");
                }
                if (responseValidator != null) writeValidator(responseValidator);

                long responseLength = connection.getContentLengthLong();
                if (responseLength > 0 && offset + responseLength > total) {
                    throw new IOException("حجم الاستجابة يتجاوز الحجم المتوقع للنموذج.");
                }

                try (InputStream input = connection.getInputStream();
                     FileOutputStream output = new FileOutputStream(partial, offset > 0)) {
                    byte[] buffer = new byte[256 * 1024];
                    int count;
                    long current = offset;
                    long nextSyncAt = offset + (4L * 1024L * 1024L);
                    while (!cancelled.get() && (count = input.read(buffer)) != -1) {
                        output.write(buffer, 0, count);
                        current += count;
                        if (current > total) throw new IOException("تجاوز التنزيل الحجم المتوقع؛ أوقفناه.");
                        if (current >= nextSyncAt) {
                            output.getFD().sync();
                            nextSyncAt = current + (4L * 1024L * 1024L);
                        }
                        listener.onProgress(current, total, "تنزيل واستكمال النموذج…");
                    }
                    output.getFD().sync();
                }

                if (cancelled.get()) {
                    listener.onFailure("أُوقف التنزيل بناءً على الطلب. الجزء المحفوظ باقٍ للاستكمال.", partial.length());
                    return;
                }

                long saved = partial.isFile() ? partial.length() : 0L;
                if (saved == total) {
                    publishCompletedFile(listener);
                    return;
                }
                throw new IOException("انقطع الاتصال بعد حفظ " + saved + " من " + total + " بايت.");
            } catch (Exception error) {
                long saved = partial.isFile() ? partial.length() : 0L;
                if (cancelled.get()) {
                    listener.onFailure("أُوقف التنزيل. الجزء المحفوظ باقٍ للاستكمال.", saved);
                    return;
                }
                if (attempt == MAX_ATTEMPTS || (error instanceof IOException
                        && error.getMessage() != null
                        && (error.getMessage().contains("لم يقبل استكمال")
                        || error.getMessage().contains("غير متطابقة")
                        || error.getMessage().contains("يتجاوز الحجم")))) {
                    listener.onFailure((error.getMessage() == null ? "تعذر إكمال التنزيل." : error.getMessage())
                            + "\nيمكنك المحاولة لاحقاً وسيبدأ من " + saved + " بايت دون العودة للصفر.", saved);
                    return;
                }
                listener.onProgress(saved, total, "انقطع الاتصال؛ محاولة الاستكمال " + (attempt + 1)
                        + " من " + MAX_ATTEMPTS + "…");
                try {
                    Thread.sleep(Math.min(30000L, 1500L * attempt));
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    listener.onFailure("توقف التنزيل. الجزء المحفوظ باقٍ للاستكمال.", saved);
                    return;
                }
            } finally {
                if (connection != null) connection.disconnect();
            }
        }
    }

    private void publishCompletedFile(Listener listener) throws IOException {
        if (!partial.isFile() || partial.length() != OnDeviceModelSpec.EXPECTED_BYTES) {
            throw new IOException("لم يكتمل حجم الملف بعد؛ الجزء المحفوظ لم يُحذف.");
        }
        // File.renameTo is available on minSdk 24; java.nio.file.Files requires API 26.
        if (destination.exists() && !destination.delete()) {
            throw new IOException("تعذر استبدال ملف النموذج القديم بعد اكتمال الجزء الجديد.");
        }
        if (!partial.renameTo(destination)) {
            throw new IOException("اكتمل التنزيل لكن تعذر تثبيت الملف النهائي؛ الجزء الكامل محفوظ للاستعادة.");
        }
        validatorFile.delete();
        listener.onComplete(destination);
    }

    private static String responseValidator(HttpURLConnection connection) {
        String etag = connection.getHeaderField("ETag");
        if (etag != null && !etag.isEmpty() && !etag.regionMatches(true, 0, "W/", 0, 2)) {
            return "E:" + etag;
        }
        String modified = connection.getHeaderField("Last-Modified");
        return modified == null || modified.isEmpty() ? null : "M:" + modified;
    }

    private static String ifRangeValue(String validator) {
        if (validator == null || validator.isEmpty()) return null;
        if (validator.startsWith("E:") || validator.startsWith("M:")) return validator.substring(2);
        return validator;
    }

    private String readValidator() {
        try {
            if (!validatorFile.isFile()) return null;
            try (InputStream input = new java.io.FileInputStream(validatorFile);
                 ByteArrayOutputStream output = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[1024];
                int count;
                while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
                return new String(output.toByteArray(), StandardCharsets.UTF_8);
            }
        } catch (Exception ignored) {
            return null;
        }
    }

    private void writeValidator(String value) {
        try (FileOutputStream output = new FileOutputStream(validatorFile, false)) {
            output.write(value.getBytes(StandardCharsets.UTF_8));
            output.getFD().sync();
        } catch (Exception ignored) {
            // Range offsets are still checked against Content-Range before appending.
        }
    }
}
