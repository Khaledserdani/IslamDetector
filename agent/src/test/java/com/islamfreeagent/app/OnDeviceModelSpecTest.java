package com.islamfreeagent.app;

import org.junit.Test;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import static org.junit.Assert.*;

public class OnDeviceModelSpecTest {
    @Test public void sha256UsesStandardDigest() throws Exception {
        String hash = OnDeviceModelSpec.sha256(
                new ByteArrayInputStream("abc".getBytes(StandardCharsets.UTF_8)));
        assertEquals("ba7816bf8f01cfea414140de5dae2223"
                + "b00361a396177a9cb410ff61f20015ad", hash);
    }

    @Test public void modelSpecPinsTheExpectedArtifact() {
        assertEquals("Qwen3-0.6B.litertlm", OnDeviceModelSpec.FILE_NAME);
        assertEquals(613722264L, OnDeviceModelSpec.EXPECTED_BYTES);
        assertEquals(64, OnDeviceModelSpec.EXPECTED_SHA256.length());
    }
}
