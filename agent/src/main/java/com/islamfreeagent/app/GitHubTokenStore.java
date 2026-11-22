package com.islamfreeagent.app;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.nio.charset.StandardCharsets;
import java.security.KeyStore;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

final class GitHubTokenStore {
    private static final String PREFS = "islam_github_secure";
    private static final String KEY_ALIAS = "IslamFreeAgentGitHubTokenKey";
    private static final String IV = "token_iv";
    private static final String TOKEN = "token_ciphertext";

    private GitHubTokenStore() {}

    static void save(Context context, String token) throws Exception {
        if (token == null || token.trim().length() < 20 || token.contains("\n") || token.contains("\r")) {
            throw new IllegalArgumentException("رمز GitHub غير صالح");
        }
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey());
        byte[] encrypted = cipher.doFinal(token.trim().getBytes(StandardCharsets.UTF_8));
        SharedPreferences.Editor edit = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit();
        edit.putString(IV, Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP));
        edit.putString(TOKEN, Base64.encodeToString(encrypted, Base64.NO_WRAP));
        if (!edit.commit()) throw new IllegalStateException("تعذر حفظ الرمز على الهاتف");
    }

    static String load(Context context) throws Exception {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String ivText = prefs.getString(IV, null);
        String tokenText = prefs.getString(TOKEN, null);
        if (ivText == null && tokenText == null) return null;
        if (ivText == null || tokenText == null) {
            throw new IllegalStateException("بيانات الرمز المشفّر غير مكتملة؛ لم يتم حذفها تلقائياً.");
        }
        SecretKey key = getExistingKey();
        if (key == null) {
            throw new IllegalStateException("مفتاح تشفير رمز GitHub غير موجود؛ يجب تنظيف البيانات القديمة وإعادة الربط.");
        }
        return decrypt(key, ivText, tokenText);
    }

    static String decrypt(SecretKey key, String ivText, String tokenText) throws Exception {
        if (key == null || ivText == null || tokenText == null) {
            throw new IllegalArgumentException("بيانات الرمز المشفّر غير مكتملة");
        }
        byte[] iv = Base64.decode(ivText, Base64.NO_WRAP);
        byte[] encrypted = Base64.decode(tokenText, Base64.NO_WRAP);
        if (iv.length != 12 || encrypted.length < 16) {
            throw new IllegalArgumentException("بيانات الرمز المشفّر تالفة أو غير مكتملة");
        }
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, key, new GCMParameterSpec(128, iv));
        return new String(cipher.doFinal(encrypted), StandardCharsets.UTF_8);
    }

    static boolean clear(Context context) {
        if (context == null) return false;
        boolean preferencesCleared = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().clear().commit();
        if (!preferencesCleared) return false;
        boolean keyDeleted;
        try {
            KeyStore keyStore = KeyStore.getInstance("AndroidKeyStore");
            keyStore.load(null);
            if (keyStore.containsAlias(KEY_ALIAS)) keyStore.deleteEntry(KEY_ALIAS);
            keyDeleted = !keyStore.containsAlias(KEY_ALIAS);
        } catch (Exception error) {
            keyDeleted = false;
        }
        return preferencesCleared && keyDeleted;
    }

    private static SecretKey getExistingKey() throws Exception {
        KeyStore keyStore = KeyStore.getInstance("AndroidKeyStore");
        keyStore.load(null);
        if (!keyStore.containsAlias(KEY_ALIAS)) return null;
        return ((KeyStore.SecretKeyEntry) keyStore.getEntry(KEY_ALIAS, null)).getSecretKey();
    }

    private static SecretKey getOrCreateKey() throws Exception {
        SecretKey existing = getExistingKey();
        if (existing != null) return existing;
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build());
        return generator.generateKey();
    }
}
