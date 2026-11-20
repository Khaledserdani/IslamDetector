package com.islamfreeagent.app;

import android.util.Base64;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

final class GitHubClient {
    private static final String OWNER = "Khaledserdani";
    private static final String REPO = "IslamDetector";
    private static final String API = "https://api.github.com";
    private static final int MAX_BYTES = 512 * 1024;
    private final String token;

    GitHubClient(String token) {
        if (token == null || token.trim().length() < 20 || token.contains("\n") || token.contains("\r")) {
            throw new IllegalArgumentException("رمز GitHub غير صالح");
        }
        this.token = token.trim();
    }

    String dashboard() throws Exception {
        JSONObject user = get("/user");
        JSONObject repo = get("/repos/" + OWNER + "/" + REPO);
        JSONArray branches = getArray("/repos/" + OWNER + "/" + REPO + "/branches?per_page=30");
        JSONArray pulls = getArray("/repos/" + OWNER + "/" + REPO + "/pulls?state=open&per_page=20");
        String runsText;
        try {
            JSONObject runs = get("/repos/" + OWNER + "/" + REPO + "/actions/runs?per_page=5");
            JSONArray list = runs.optJSONArray("workflow_runs");
            StringBuilder value = new StringBuilder();
            if (list != null) {
                for (int i = 0; i < list.length(); i++) {
                    JSONObject run = list.getJSONObject(i);
                    value.append("• ").append(run.optString("name", "Workflow"))
                            .append(" — ").append(run.optString("conclusion",
                                    run.optString("status", "غير معروف")))
                            .append(" (").append(run.optString("head_branch", "—")).append(")\n");
                }
            }
            runsText = value.length() == 0 ? "لا توجد عمليات بناء حديثة." : value.toString();
        } catch (Exception denied) {
            runsText = "غير متاح: تحقق من صلاحية Actions: Read.";
        }

        StringBuilder branchText = new StringBuilder();
        for (int i = 0; i < branches.length(); i++) {
            JSONObject item = branches.getJSONObject(i);
            branchText.append("• ").append(item.optString("name")).append("\n");
        }
        StringBuilder pullText = new StringBuilder();
        for (int i = 0; i < pulls.length(); i++) {
            JSONObject item = pulls.getJSONObject(i);
            pullText.append("• #").append(item.optInt("number")).append(" ")
                    .append(item.optString("title")).append(" [")
                    .append(item.optString("state")).append(item.optBoolean("draft") ? ", مسودة" : "")
                    .append("]\n");
        }
        return "الحساب: @" + user.optString("login", "—") + "\n"
                + "المستودع: " + repo.optString("full_name", OWNER + "/" + REPO) + "\n"
                + "الفرع الافتراضي: " + repo.optString("default_branch", "—") + "\n"
                + "الرؤية: " + (repo.optBoolean("private") ? "خاص" : "عام") + "\n\n"
                + "الفروع (" + branches.length() + "):\n" + branchText + "\n"
                + "طلبات الدمج المفتوحة (" + pulls.length() + "):\n"
                + (pullText.length() == 0 ? "لا توجد طلبات مفتوحة.\n" : pullText)
                + "\nآخر عمليات Actions:\n" + runsText;
    }

    private static final String WRITE_BRANCH = "feature/islam-free-agent-safe-write";
    private static final java.util.Set<String> ALLOWED_WRITE_PATHS = new java.util.HashSet<>(
            java.util.Arrays.asList(
                    "agent/src/main/java/com/islamfreeagent/app/MainActivity.java",
                    "agent/src/main/java/com/islamfreeagent/app/GitHubClient.java",
                    "agent/src/main/java/com/islamfreeagent/app/BridgeClient.java",
                    "tools/islam_agent/local_agent.py",
                    "tools/islam_agent/orchestrator.py",
                    "tools/islam_agent/agent_cycle.py",
                    "docs/agent/ISLAM_FREE_AGENT_EXECUTION_AR.md",
                    "docs/agent/agent_worklog.md"
            )
    );

    String commitApprovedFile(String path, String content, String summary) throws Exception {
        if (!ALLOWED_WRITE_PATHS.contains(path)) {
            throw new SecurityException("مسار الملف غير مسموح للرفع");
        }
        if (content == null || content.trim().isEmpty() || content.length() > 12000) {
            throw new IllegalArgumentException("محتوى الملف فارغ أو أكبر من الحد المسموح");
        }
        String existingSha = existingFileSha(path);
        JSONObject payload = new JSONObject();
        payload.put("message", "ISLAM FREE AGENT: " + (summary == null ? "approved change" : summary.substring(0, Math.min(100, summary.length()))));
        payload.put("content", Base64.encodeToString(content.getBytes(StandardCharsets.UTF_8), Base64.NO_WRAP));
        payload.put("branch", WRITE_BRANCH);
        if (existingSha != null) payload.put("sha", existingSha);

        String encodedPath = encodePath(path);
        URL url = new URL(API + "/repos/" + OWNER + "/" + REPO + "/contents/" + encodedPath);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setRequestMethod("PUT");
        connection.setConnectTimeout(8000);
        connection.setReadTimeout(20000);
        connection.setInstanceFollowRedirects(false);
        connection.setDoOutput(true);
        connection.setRequestProperty("Authorization", "Bearer " + token);
        connection.setRequestProperty("Accept", "application/vnd.github+json");
        connection.setRequestProperty("X-GitHub-Api-Version", "2022-11-28");
        connection.setRequestProperty("User-Agent", "ISLAM-FREE-AGENT-Android");
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        byte[] bytes = payload.toString().getBytes(StandardCharsets.UTF_8);
        connection.setFixedLengthStreamingMode(bytes.length);
        try (java.io.OutputStream output = connection.getOutputStream()) {
            output.write(bytes);
        }
        int status = connection.getResponseCode();
        InputStream stream = status >= 400 ? connection.getErrorStream() : connection.getInputStream();
        String response = readBounded(stream);
        connection.disconnect();
        if (status < 200 || status >= 300) {
            String message = "تعذر رفع الملف إلى GitHub (HTTP " + status + ").";
            try {
                String detail = new JSONObject(response).optString("message", "");
                if (!detail.isEmpty()) message += " " + detail;
            } catch (Exception ignored) { }
            if (status == 401) message = "رمز GitHub غير صالح أو منتهي.";
            if (status == 403) message = "الرمز لا يملك Contents: Read and write أو أن سياسة المستودع منعت الكتابة.";
            if (status == 409 || status == 422) message = "تعارض في الملف أو الفرع؛ لم يُستبدل الملف تلقائياً.";
            throw new java.io.IOException(message);
        }
        JSONObject commit = new JSONObject(response).optJSONObject("commit");
        return commit == null ? "" : commit.optString("sha", "");
    }

    private String existingFileSha(String path) throws Exception {
        URL url = new URL(API + "/repos/" + OWNER + "/" + REPO + "/contents/"
                + encodePath(path) + "?ref=" + URLEncoder.encode(WRITE_BRANCH, "UTF-8"));
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setRequestMethod("GET");
        connection.setConnectTimeout(8000);
        connection.setReadTimeout(15000);
        connection.setInstanceFollowRedirects(false);
        connection.setRequestProperty("Authorization", "Bearer " + token);
        connection.setRequestProperty("Accept", "application/vnd.github+json");
        connection.setRequestProperty("X-GitHub-Api-Version", "2022-11-28");
        connection.setRequestProperty("User-Agent", "ISLAM-FREE-AGENT-Android");
        int status = connection.getResponseCode();
        InputStream stream = status >= 400 ? connection.getErrorStream() : connection.getInputStream();
        String response = readBounded(stream);
        connection.disconnect();
        if (status == 404) return null;
        if (status < 200 || status >= 300) {
            throw new java.io.IOException("تعذر قراءة SHA للملف قبل تحديثه (HTTP " + status + ").");
        }
        return new JSONObject(response).optString("sha", null);
    }

    private static String encodePath(String path) throws Exception {
        String[] parts = path.split("/");
        StringBuilder encoded = new StringBuilder();
        for (String part : parts) {
            if (encoded.length() > 0) encoded.append('/');
            encoded.append(URLEncoder.encode(part, "UTF-8").replace("+", "%20"));
        }
        return encoded.toString();
    }

    private JSONObject get(String path) throws Exception {
        String body = request(path);
        return new JSONObject(body);
    }

    private JSONArray getArray(String path) throws Exception {
        return new JSONArray(request(path));
    }

    private String request(String path) throws Exception {
        if (!path.startsWith("/") || path.contains("..")) throw new IllegalArgumentException("مسار API غير صالح");
        HttpURLConnection connection = (HttpURLConnection) new URL(API + path).openConnection();
        connection.setRequestMethod("GET");
        connection.setConnectTimeout(8000);
        connection.setReadTimeout(15000);
        connection.setInstanceFollowRedirects(false);
        connection.setRequestProperty("Authorization", "Bearer " + token);
        connection.setRequestProperty("Accept", "application/vnd.github+json");
        connection.setRequestProperty("X-GitHub-Api-Version", "2022-11-28");
        connection.setRequestProperty("User-Agent", "ISLAM-FREE-AGENT-Android");
        connection.setRequestProperty("Cache-Control", "no-store");
        int status = connection.getResponseCode();
        InputStream stream = status >= 400 ? connection.getErrorStream() : connection.getInputStream();
        String response = readBounded(stream);
        connection.disconnect();
        if (status < 200 || status >= 300) {
            String message = "رفض GitHub الطلب (HTTP " + status + ").";
            try {
                JSONObject error = new JSONObject(response);
                String detail = error.optString("message", "");
                if (!detail.isEmpty()) message += " " + detail;
            } catch (Exception ignored) { }
            if (status == 401) message = "رمز GitHub غير صحيح أو منتهي.";
            if (status == 403) message = "صلاحية الرمز غير كافية أو تجاوزت حد الطلبات. راجع صلاحيات القراءة.";
            if (status == 404) message = "المستودع غير ظاهر لهذا الرمز؛ تحقق من اختيار IslamDetector وصلاحية Metadata.";
            throw new java.io.IOException(message);
        }
        return response;
    }

    private static String readBounded(InputStream input) throws Exception {
        if (input == null) return "";
        try (InputStream in = input; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int total = 0;
            int count;
            while ((count = in.read(buffer)) != -1) {
                total += count;
                if (total > MAX_BYTES) throw new java.io.IOException("رد GitHub أكبر من الحد المسموح");
                out.write(buffer, 0, count);
            }
            return new String(out.toByteArray(), StandardCharsets.UTF_8);
        }
    }
}
