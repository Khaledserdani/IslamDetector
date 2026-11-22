package com.islamfreeagent.app;

import android.util.Base64;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;

import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
public class GitHubTokenStoreTest {
    private SecretKey newAesKey() throws Exception {
        KeyGenerator generator = KeyGenerator.getInstance("AES");
        generator.init(128);
        return generator.generateKey();
    }

    private String[] encrypt(SecretKey key, String token) throws Exception {
        byte[] iv = new byte[12];
        new SecureRandom().nextBytes(iv);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key, new GCMParameterSpec(128, iv));
        byte[] ciphertext = cipher.doFinal(token.getBytes(StandardCharsets.UTF_8));
        return new String[] {
                Base64.encodeToString(iv, Base64.NO_WRAP),
                Base64.encodeToString(ciphertext, Base64.NO_WRAP)
        };
    }

    @Test public void decryptsValidAuthenticatedToken() throws Exception {
        SecretKey key = newAesKey();
        String expected = "github_pat_test_token_value_1234567890";
        String[] encrypted = encrypt(key, expected);
        assertEquals(expected, GitHubTokenStore.decrypt(key, encrypted[0], encrypted[1]));
    }

    @Test public void rejectsCiphertextTampering() throws Exception {
        SecretKey key = newAesKey();
        String[] encrypted = encrypt(key, "github_pat_test_token_value_1234567890");
        byte[] ciphertext = Base64.decode(encrypted[1], Base64.NO_WRAP);
        ciphertext[ciphertext.length - 1] ^= 0x01;
        String tampered = Base64.encodeToString(ciphertext, Base64.NO_WRAP);
        try {
            GitHubTokenStore.decrypt(key, encrypted[0], tampered);
            fail("GCM authentication must reject modified ciphertext");
        } catch (javax.crypto.AEADBadTagException expected) {
            // Expected: GCM authentication tag does not match.
        }
    }

    @Test public void rejectsIncompleteOrInvalidEncryptedState() throws Exception {
        SecretKey key = newAesKey();
        try {
            GitHubTokenStore.decrypt(key, null, "AAAA");
            fail("missing IV must fail");
        } catch (IllegalArgumentException expected) { }

        try {
            GitHubTokenStore.decrypt(key, Base64.encodeToString(new byte[8], Base64.NO_WRAP),
                    Base64.encodeToString(new byte[32], Base64.NO_WRAP));
            fail("non-12-byte GCM IV must fail");
        } catch (IllegalArgumentException expected) { }
    }
}
