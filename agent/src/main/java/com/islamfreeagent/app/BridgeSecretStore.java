package com.islamfreeagent.app;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.util.Arrays;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

final class BridgeSecretStore {
    private static final String PREFS = "islam_bridge_secure";
    private static final String KEY_ALIAS = "IslamFreeAgentBridgeSessionKey";
    private static final String HOST = "host";
    private static final String PORT = "port";
    private static final String PIN = "certificate_sha256";
    private static final String IV = "session_iv";
    private static final String TOKEN = "session_ciphertext";

    private BridgeSecretStore() {}

    static void save(Context context, String host, int port, String pin, String token) throws Exception {
        if (host == null || host.trim().isEmpty() || port < 1024 || port > 65535
                || pin == null || !pin.matches("[0-9a-fA-F]{64}")
                || token == null || token.length() < 32) {
            throw new IllegalArgumentException("بيانات الاقتران غير صالحة");
        }
        SecretKey key = getOrCreateKey();
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key);
        byte[] encrypted = cipher.doFinal(token.getBytes(StandardCharsets.UTF_8));
        SharedPreferences.Editor edit = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit();
        edit.putString(HOST, host.trim());
        edit.putInt(PORT, port);
        edit.putString(PIN, pin.toLowerCase(java.util.Locale.ROOT));
        edit.putString(IV, Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP));
        edit.putString(TOKEN, Base64.encodeToString(encrypted, Base64.NO_WRAP));
        if (!edit.commit()) throw new IllegalStateException("تعذر حفظ إعدادات الاتصال");
    }

    static String[] load(Context context) throws Exception {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String host = prefs.getString(HOST, null);
        String pin = prefs.getString(PIN, null);
        String ivText = prefs.getString(IV, null);
        String cipherText = prefs.getString(TOKEN, null);
        int port = prefs.getInt(PORT, -1);
        if (host == null || pin == null || ivText == null || cipherText == null || port < 1024) {
            return null;
        }
        byte[] iv = Base64.decode(ivText, Base64.NO_WRAP);
        byte[] encrypted = Base64.decode(cipherText, Base64.NO_WRAP);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(), new GCMParameterSpec(128, iv));
        String token = new String(cipher.doFinal(encrypted), StandardCharsets.UTF_8);
        return new String[]{host, String.valueOf(port), pin, token};
    }

    static void clear(Context context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().clear().commit();
        try {
            KeyStore store = KeyStore.getInstance("AndroidKeyStore");
            store.load(null);
            if (store.containsAlias(KEY_ALIAS)) store.deleteEntry(KEY_ALIAS);
        } catch (Exception ignored) {
            // Session data is cleared even if key cleanup is unavailable.
        }
    }

    private static SecretKey getOrCreateKey() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        if (store.containsAlias(KEY_ALIAS)) {
            return ((KeyStore.SecretKeyEntry) store.getEntry(KEY_ALIAS, null)).getSecretKey();
        }
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build());
        return generator.generateKey();
    }
}
