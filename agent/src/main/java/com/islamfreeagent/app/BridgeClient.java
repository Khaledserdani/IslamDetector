package com.islamfreeagent.app;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.Inet4Address;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;
import java.util.Locale;

import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;

final class BridgeClient {
    private static final int MAX_RESPONSE_BYTES = 1024 * 1024;
    private static final int CONNECT_TIMEOUT_MS = 6000;
    private static final int READ_TIMEOUT_MS = 30000;

    private final String host;
    private final int port;
    private final String pin;
    private final String token;
    private final SSLContext sslContext;

    BridgeClient(String host, int port, String pin, String token) throws Exception {
        if (!isAllowedBridgeIpv4(host)) throw new IllegalArgumentException("عنوان المضيف يجب أن يكون IPv4 خاصاً بالشبكة المحلية أو شبكة Tailscale");
        if (port < 1024 || port > 65535) throw new IllegalArgumentException("رقم المنفذ غير صالح");
        if (pin == null || !pin.matches("[0-9a-fA-F]{64}")) throw new IllegalArgumentException("بصمة الشهادة يجب أن تكون 64 خانة");
        this.host = host;
        this.port = port;
        this.pin = pin.replace(":", "").toLowerCase(Locale.ROOT);
        this.token = token;
        this.sslContext = createPinnedContext(this.pin);
    }

    static boolean isPrivateIpv4(String value) {
        return isAllowedBridgeIpv4(value);
    }

    static boolean isAllowedBridgeIpv4(String value) {
        if (value == null || !value.matches("[0-9]{1,3}(\\.[0-9]{1,3}){3}")) return false;
        try {
            InetAddress address = InetAddress.getByName(value);
            if (!(address instanceof Inet4Address)
                    || address.isLoopbackAddress()
                    || address.isAnyLocalAddress()
                    || address.isMulticastAddress()) return false;
            byte[] bytes = address.getAddress();
            boolean rfc1918 = (bytes[0] & 0xff) == 10
                    || ((bytes[0] & 0xff) == 172 && (bytes[1] & 0xf0) == 16)
                    || ((bytes[0] & 0xff) == 192 && (bytes[1] & 0xff) == 168);
            boolean tailscale = (bytes[0] & 0xff) == 100 && (bytes[1] & 0xc0) == 64;
            return rfc1918 || tailscale;
        } catch (Exception ignored) {
            return false;
        }
    }

    private static SSLContext createPinnedContext(String expectedPin) throws Exception {
        X509TrustManager pinnedTrust = new X509TrustManager() {
            @Override public void checkClientTrusted(X509Certificate[] chain, String authType)
                    throws CertificateException {
                throw new CertificateException("Client certificates are not accepted");
            }

            @Override public void checkServerTrusted(X509Certificate[] chain, String authType)
                    throws CertificateException {
                if (chain == null || chain.length == 0) throw new CertificateException("Missing server certificate");
                try {
                    X509Certificate leaf = chain[0];
                    leaf.checkValidity();
                    byte[] digest = MessageDigest.getInstance("SHA-256").digest(leaf.getEncoded());
                    StringBuilder actual = new StringBuilder(64);
                    for (byte value : digest) actual.append(String.format(Locale.ROOT, "%02x", value & 0xff));
                    if (!MessageDigest.isEqual(
                            actual.toString().getBytes(StandardCharsets.US_ASCII),
                            expectedPin.getBytes(StandardCharsets.US_ASCII))) {
                        throw new CertificateException("TLS certificate pin mismatch");
                    }
                } catch (CertificateException e) {
                    throw e;
                } catch (Exception e) {
                    throw new CertificateException("Could not validate pinned certificate", e);
                }
            }

            @Override public X509Certificate[] getAcceptedIssuers() {
                return new X509Certificate[0];
            }
        };
        SSLContext context = SSLContext.getInstance("TLSv1.2");
        context.init(null, new TrustManager[]{pinnedTrust}, new java.security.SecureRandom());
        return context;
    }

    JSONObject health() throws Exception {
        return request("GET", "/v1/health", null, false);
    }

    JSONObject pair(String code) throws Exception {
        JSONObject body = new JSONObject();
        body.put("code", code);
        return request("POST", "/v1/pair", body, false);
    }

    JSONObject tasks() throws Exception {
        return request("GET", "/v1/tasks", null, true);
    }

    JSONObject createProposal() throws Exception {
        return request("POST", "/v1/proposals", new JSONObject(), true);
    }

    JSONObject pendingProposal() throws Exception {
        return request("GET", "/v1/proposals/pending", null, true);
    }

    JSONObject decide(String proposalId, String decision, String confirmationText) throws Exception {
        JSONObject body = new JSONObject();
        body.put("decision", decision);
        body.put("confirmation_text", confirmationText == null ? "" : confirmationText);
        return request("POST", "/v1/proposals/" + proposalId + "/decision", body, true);
    }

    JSONObject completeUpload(String proposalId, JSONArray files) throws Exception {
        JSONObject body = new JSONObject();
        body.put("proposal_id", proposalId);
        body.put("files", files);
        return request("POST", "/v1/uploads/complete", body, true);
    }

    private JSONObject request(String method, String path, JSONObject body, boolean authenticated)
            throws Exception {
        URL url = new URL("https", host, port, path);
        HttpsURLConnection connection = (HttpsURLConnection) url.openConnection();
        connection.setSSLSocketFactory(sslContext.getSocketFactory());
        connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
        connection.setReadTimeout(READ_TIMEOUT_MS);
        connection.setRequestMethod(method);
        connection.setInstanceFollowRedirects(false);
        connection.setRequestProperty("Accept", "application/json");
        connection.setRequestProperty("Cache-Control", "no-store");
        if (authenticated) {
            if (token == null || token.isEmpty()) throw new SecurityException("الهاتف غير مقترن");
            connection.setRequestProperty("Authorization", "Bearer " + token);
        }
        if (body != null) {
            byte[] bytes = body.toString().getBytes(StandardCharsets.UTF_8);
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            connection.setFixedLengthStreamingMode(bytes.length);
            try (OutputStream output = connection.getOutputStream()) {
                output.write(bytes);
            }
        }
        int status = connection.getResponseCode();
        InputStream input = status >= 400 ? connection.getErrorStream() : connection.getInputStream();
        byte[] response = readBounded(input, MAX_RESPONSE_BYTES);
        connection.disconnect();
        JSONObject json = new JSONObject(new String(response, StandardCharsets.UTF_8));
        if (status < 200 || status >= 300) {
            JSONObject error = json.optJSONObject("error");
            String message = error == null ? "فشل الاتصال بالخادم" : error.optString("message_ar", error.optString("code", "خطأ غير معروف"));
            throw new BridgeHttpException(status, message, json);
        }
        return json;
    }

    private static byte[] readBounded(InputStream input, int maximum) throws Exception {
        if (input == null) return "{}".getBytes(StandardCharsets.UTF_8);
        try (InputStream source = input; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int total = 0;
            int read;
            while ((read = source.read(buffer)) != -1) {
                total += read;
                if (total > maximum) throw new IllegalStateException("رد الخادم أكبر من الحد المسموح");
                output.write(buffer, 0, read);
            }
            return output.toByteArray();
        }
    }

    static final class BridgeHttpException extends Exception {
        final int status;
        final JSONObject response;
        BridgeHttpException(int status, String message, JSONObject response) {
            super(message);
            this.status = status;
            this.response = response;
        }
    }
}
