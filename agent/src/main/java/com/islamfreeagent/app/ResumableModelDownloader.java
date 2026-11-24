package com.islamfreeagent.app;

import android.content.Context;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
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
                if (offset > 0) {
                    connection.setRequestProperty("Range", "bytes=" + offset + "-");
                    String etag = readValidator();
                    if (etag != null && !etag.isEmpty()) connection.setRequestProperty("If-Range", etag);
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

                String responseEtag = connection.getHeaderField("ETag");
                if (responseEtag != null && !responseEtag.isEmpty()) writeValidator(responseEtag);

                long responseLength = connection.getContentLengthLong();
                if (responseLength > 0 && offset + responseLength > total) {
                    throw new IOException("حجم الاستجابة يتجاوز الحجم المتوقع للنموذج.");
                }

                try (InputStream input = connection.getInputStream();
                     FileOutputStream output = new FileOutputStream(partial, offset > 0)) {
                    byte[] buffer = new byte[256 * 1024];
                    int count;
                    long current = offset;
                    while (!cancelled.get() && (count = input.read(buffer)) != -1) {
                        output.write(buffer, 0, count);
                        current += count;
                        if (current > total) throw new IOException("تجاوز التنزيل الحجم المتوقع؛ أوقفناه.");
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
        try {
            Files.move(partial.toPath(), destination.toPath(), StandardCopyOption.REPLACE_EXISTING,
                    StandardCopyOption.ATOMIC_MOVE);
        } catch (Exception atomicMoveError) {
            Files.move(partial.toPath(), destination.toPath(), StandardCopyOption.REPLACE_EXISTING);
        }
        validatorFile.delete();
        listener.onComplete(destination);
    }

    private String readValidator() {
        try {
            if (!validatorFile.isFile()) return null;
            byte[] bytes = Files.readAllBytes(validatorFile.toPath());
            return new String(bytes, StandardCharsets.UTF_8);
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
