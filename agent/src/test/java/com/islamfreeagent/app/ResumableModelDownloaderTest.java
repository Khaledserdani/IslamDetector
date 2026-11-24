package com.islamfreeagent.app;

import static org.junit.Assert.*;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.concurrent.atomic.AtomicReference;

import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.mockwebserver.RecordedRequest;
import okhttp3.mockwebserver.SocketPolicy;
import org.junit.Test;

public class ResumableModelDownloaderTest {
    @Test public void resumesFromSavedByteOffsetAfterConnectionDrops() throws Exception {
        File directory = Files.createTempDirectory("islam-resume-ok").toFile();
        try (MockWebServer server = new MockWebServer()) {
            server.enqueue(new MockResponse()
                    .setResponseCode(200)
                    .setHeader("ETag", "\"model-v1\"")
                    .setBody("abcdefghij")
                    .setSocketPolicy(SocketPolicy.DISCONNECT_DURING_RESPONSE_BODY));
            server.enqueue(new MockResponse()
                    .setResponseCode(206)
                    .setHeader("ETag", "\"model-v1\"")
                    .setHeader("Content-Range", "bytes 5-9/10")
                    .setBody("fghij"));
            server.start();

            AtomicReference<File> completed = new AtomicReference<>();
            AtomicReference<String> failure = new AtomicReference<>();
            new ResumableModelDownloader(directory, server.url("/model").toString(), 10L)
                    .download(new ResumableModelDownloader.Listener() {
                        @Override public void onProgress(long downloaded, long total, String message) {}
                        @Override public void onComplete(File modelFile) { completed.set(modelFile); }
                        @Override public void onFailure(String message, long preservedBytes) { failure.set(message); }
                    });

            assertNull("download should complete after resume: " + failure.get(), failure.get());
            assertNotNull(completed.get());
            assertEquals("abcdefghij", new String(Files.readAllBytes(completed.get().toPath()),
                    StandardCharsets.UTF_8));
            RecordedRequest first = server.takeRequest();
            RecordedRequest second = server.takeRequest();
            assertNull(first.getHeader("Range"));
            assertEquals("bytes=5-", second.getHeader("Range"));
            assertEquals("\"model-v1\"", second.getHeader("If-Range"));
            assertFalse(new File(directory, OnDeviceModelSpec.FILE_NAME + ".part").exists());
        }
    }

    @Test public void keepsPartialFileWhenServerDoesNotHonorRange() throws Exception {
        File directory = Files.createTempDirectory("islam-resume-preserve").toFile();
        try (MockWebServer server = new MockWebServer()) {
            server.enqueue(new MockResponse()
                    .setResponseCode(200)
                    .setHeader("ETag", "\"model-v1\"")
                    .setBody("abcdefghij")
                    .setSocketPolicy(SocketPolicy.DISCONNECT_DURING_RESPONSE_BODY));
            server.enqueue(new MockResponse()
                    .setResponseCode(200)
                    .setHeader("ETag", "\"model-v1\"")
                    .setBody("abcdefghij"));
            server.start();

            AtomicReference<String> failure = new AtomicReference<>();
            AtomicReference<Long> preserved = new AtomicReference<>(0L);
            new ResumableModelDownloader(directory, server.url("/model").toString(), 10L)
                    .download(new ResumableModelDownloader.Listener() {
                        @Override public void onProgress(long downloaded, long total, String message) {}
                        @Override public void onComplete(File modelFile) { fail("must not publish an unresumed file"); }
                        @Override public void onFailure(String message, long preservedBytes) {
                            failure.set(message);
                            preserved.set(preservedBytes);
                        }
                    });

            assertNotNull(failure.get());
            assertTrue(failure.get().contains("لم يقبل استكمال"));
            File partial = new File(directory, OnDeviceModelSpec.FILE_NAME + ".part");
            assertTrue(partial.isFile());
            assertEquals(preserved.get().longValue(), partial.length());
            assertTrue(partial.length() > 0L);
            assertTrue(partial.length() < 10L);
            RecordedRequest first = server.takeRequest();
            RecordedRequest second = server.takeRequest();
            assertNull(first.getHeader("Range"));
            assertTrue(second.getHeader("Range").startsWith("bytes="));
        }
    }
}
