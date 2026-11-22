package com.islamfreeagent.app;


import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

final class GitHubClient {
    private static final String OWNER = "Khaledserdani";
    private static final String REPO = "IslamDetector";
    private static final String API = "https://api.github.com";
    private static final int MAX_BYTES = 512 * 1024;
    // Keep remote writes disabled until a separately reviewed human-approval flow exists.
    private static final boolean WRITE_API_ENABLED = false;
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

    // Deliberate fail-closed stub. No GitHub write implementation is shipped in this build.
    static boolean isWriteApiEnabled() {
        return false;
    }

    String commitApprovedFile(String path, String content, String summary) {
        throw new SecurityException("الكتابة إلى GitHub غير مدعومة في هذه النسخة؛ استخدم مراجعة ورفعاً يدوياً خارج التطبيق.");
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
        try {
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
        } finally {
            connection.disconnect();
        }
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
