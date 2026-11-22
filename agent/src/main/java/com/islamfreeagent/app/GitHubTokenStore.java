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
        if (ivText == null || tokenText == null) return null;
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(),
                new GCMParameterSpec(128, Base64.decode(ivText, Base64.NO_WRAP)));
        return new String(cipher.doFinal(Base64.decode(tokenText, Base64.NO_WRAP)), StandardCharsets.UTF_8);
    }

    static boolean clear(Context context) {
        if (context == null) return false;
        boolean preferencesCleared = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().clear().commit();
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

    private static SecretKey getOrCreateKey() throws Exception {
        KeyStore keyStore = KeyStore.getInstance("AndroidKeyStore");
        keyStore.load(null);
        if (keyStore.containsAlias(KEY_ALIAS)) {
            return ((KeyStore.SecretKeyEntry) keyStore.getEntry(KEY_ALIAS, null)).getSecretKey();
        }
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
