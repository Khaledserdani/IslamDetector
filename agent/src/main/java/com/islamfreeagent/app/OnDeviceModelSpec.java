package com.islamfreeagent.app;

import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.security.MessageDigest;

final class OnDeviceModelSpec {
    static final String FILE_NAME = "Qwen3-0.6B.litertlm";
    static final String DOWNLOAD_URL =
            "https://huggingface.co/litert-community/Qwen3-0.6B/resolve/main/Qwen3-0.6B.litertlm";
    static final long EXPECTED_BYTES = 613722264L;
    static final String EXPECTED_SHA256 =
            "c5f39b4191926786c3e6668b62af4d6eb15248dfc7a5348252a9b406f33f2108";

    private OnDeviceModelSpec() {}

    static boolean isValid(File file) throws Exception {
        if (file == null || !file.isFile() || file.length() != EXPECTED_BYTES) return false;
        try (InputStream input = new FileInputStream(file)) {
            return EXPECTED_SHA256.equals(sha256(input));
        }
    }

    static String sha256(InputStream input) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] buffer = new byte[1024 * 1024];
        int count;
        while ((count = input.read(buffer)) != -1) {
            digest.update(buffer, 0, count);
        }
        StringBuilder result = new StringBuilder(64);
        for (byte value : digest.digest()) {
            result.append(String.format(java.util.Locale.US, "%02x", value & 0xff));
        }
        return result.toString();
    }
}
