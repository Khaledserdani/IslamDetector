package com.islamfreeagent.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final int BG = Color.rgb(8, 16, 29);
    private static final int PANEL = Color.rgb(19, 33, 51);
    private static final int MUTED = Color.rgb(157, 177, 199);
    private static final int GREEN = Color.rgb(34, 145, 116);
    private AgentTaskStore store;
    private LinearLayout taskList;
    private TextView countText;
    private TextView bridgeStatusText;
    private EditText bridgeHostInput;
    private EditText bridgePortInput;
    private EditText bridgePinInput;
    private EditText bridgeCodeInput;
    private final ExecutorService networkExecutor = Executors.newSingleThreadExecutor();

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        store = new AgentTaskStore(this);
        buildScreen();
        loadSavedBridgeSettings();
        renderTasks();
    }

    @Override protected void onDestroy() {
        networkExecutor.shutdownNow();
        super.onDestroy();
    }

    private void buildScreen() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(BG);

        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(dp(18), dp(22), dp(18), dp(28));
        page.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);
        scroll.addView(page);

        TextView title = text("ISLAM FREE AGENT", 25, Color.WHITE, true);
        title.setGravity(Gravity.CENTER);
        page.addView(title, matchWrap());

        TextView subtitle = text("المدير المساعد لمشروع إسلام", 15, MUTED, false);
        subtitle.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams sub = matchWrap();
        sub.topMargin = dp(6);
        page.addView(subtitle, sub);

        LinearLayout notice = panel();
        TextView noticeTitle = text("إدارة محلية + اتصال آمن اختياري", 16, Color.rgb(255, 205, 120), true);
        notice.addView(noticeTitle, matchWrap());
        TextView noticeBody = text("المهام المحلية تعمل دون إنترنت. عند تشغيل جسر الكمبيوتر واقتران الهاتف، يمكن عرض مهام المشروع وطلب اقتراح من Ollama ومراجعته. لا يُنفذ أي اقتراح دون موافقتك الصريحة.", 13, MUTED, false);
        LinearLayout.LayoutParams nb = matchWrap(); nb.topMargin = dp(8);
        notice.addView(noticeBody, nb);
        addPanel(page, notice, 18);

        LinearLayout status = panel();
        status.addView(text("حالة التطبيق", 16, Color.WHITE, true), matchWrap());
        TextView state = text("واجهة الهاتف: تعمل", 14, Color.rgb(130, 220, 185), true);
        LinearLayout.LayoutParams st = matchWrap(); st.topMargin = dp(8);
        status.addView(state, st);
        TextView engine = text("محرك الكمبيوتر: افحص الاتصال أدناه", 13, MUTED, false);
        LinearLayout.LayoutParams en = matchWrap(); en.topMargin = dp(5);
        status.addView(engine, en);
        addPanel(page, status, 12);

        LinearLayout bridge = panel();
        bridge.addView(text("ربط محرك الكمبيوتر", 18, Color.WHITE, true), matchWrap());
        TextView help = text("أدخل عنوان IPv4 الخاص الذي يعرضه برنامج run_bridge.py، ثم بصمة الشهادة ورمز الاقتران. الاتصال HTTPS مع تثبيت البصمة فقط.", 12, MUTED, false);
        LinearLayout.LayoutParams helpLp = matchWrap(); helpLp.topMargin = dp(7);
        bridge.addView(help, helpLp);

        bridgeHostInput = bridgeInput("عنوان الكمبيوتر مثل 192.168.1.5", InputType.TYPE_CLASS_TEXT);
        bridgePortInput = bridgeInput("المنفذ", InputType.TYPE_CLASS_NUMBER);
        bridgePortInput.setText("8765");
        bridgePinInput = bridgeInput("بصمة شهادة SHA-256 (64 خانة)", InputType.TYPE_CLASS_TEXT);
        bridgeCodeInput = bridgeInput("رمز الاقتران المؤقت (6 أرقام)", InputType.TYPE_CLASS_NUMBER);
        addInput(bridge, bridgeHostInput);
        addInput(bridge, bridgePortInput);
        addInput(bridge, bridgePinInput);
        addInput(bridge, bridgeCodeInput);

        Button pair = bridgeButton("اقتران الهاتف بالكمبيوتر");
        pair.setOnClickListener(v -> pairBridge());
        bridge.addView(pair, bridgeButtonParams());

        Button health = bridgeButton("فحص حالة المحرك");
        health.setOnClickListener(v -> checkBridgeHealth());
        bridge.addView(health, bridgeButtonParams());

        Button tasks = bridgeButton("عرض مهام المشروع على الكمبيوتر");
        tasks.setOnClickListener(v -> loadRemoteTasks());
        bridge.addView(tasks, bridgeButtonParams());

        Button propose = bridgeButton("اطلب اقتراحاً من Ollama");
        propose.setOnClickListener(v -> requestProposal());
        bridge.addView(propose, bridgeButtonParams());

        Button pending = bridgeButton("مراجعة الاقتراح المعلق");
        pending.setOnClickListener(v -> loadPendingProposal());
        bridge.addView(pending, bridgeButtonParams());

        bridgeStatusText = text("غير متصل — المهام المحلية تعمل بشكل مستقل", 12, MUTED, false);
        LinearLayout.LayoutParams bsp = matchWrap(); bsp.topMargin = dp(10);
        bridge.addView(bridgeStatusText, bsp);
        addPanel(page, bridge, 12);

        addGitHubPanel(page);

        LinearLayout heading = new LinearLayout(this);
        heading.setGravity(Gravity.CENTER_VERTICAL);
        heading.setOrientation(LinearLayout.HORIZONTAL);
        TextView queueTitle = text("مهامي المحلية", 19, Color.WHITE, true);
        heading.addView(queueTitle, new LinearLayout.LayoutParams(0, -2, 1));
        countText = text("0 مهمة", 12, MUTED, false);
        heading.addView(countText, wrap());
        LinearLayout.LayoutParams hp = matchWrap(); hp.topMargin = dp(22);
        page.addView(heading, hp);

        Button add = button("＋ إضافة مهمة", GREEN);
        LinearLayout.LayoutParams ap = matchWrap(); ap.height = dp(50); ap.topMargin = dp(10);
        page.addView(add, ap);
        add.setOnClickListener(v -> showAddTaskDialog());

        taskList = new LinearLayout(this);
        taskList.setOrientation(LinearLayout.VERTICAL);
        LinearLayout.LayoutParams listLp = matchWrap(); listLp.topMargin = dp(8);
        page.addView(taskList, listLp);

        TextView footer = text("بيانات المهام المحلية تبقى على الهاتف. اتصال الكمبيوتر لا يرسل رموز الاقتران إلى السجلات ولا يفتح منفذ Ollama للشبكة.", 12, MUTED, false);
        LinearLayout.LayoutParams fp = matchWrap(); fp.topMargin = dp(20);
        page.addView(footer, fp);
        setContentView(scroll);
    }

    private EditText bridgeInput(String hint, int type) {
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setTextSize(13);
        input.setHint(hint);
        input.setInputType(type);
        input.setTextColor(Color.WHITE);
        input.setHintTextColor(MUTED);
        input.setLayoutDirection(View.LAYOUT_DIRECTION_LTR);
        input.setSelectAllOnFocus(false);
        return input;
    }

    private void addInput(LinearLayout parent, EditText input) {
        LinearLayout.LayoutParams lp = matchWrap();
        lp.topMargin = dp(5);
        parent.addView(input, lp);
    }

    private Button bridgeButton(String title) {
        Button b = button(title, Color.rgb(40, 83, 112));
        b.setTextSize(13);
        return b;
    }

    private LinearLayout.LayoutParams bridgeButtonParams() {
        LinearLayout.LayoutParams lp = matchWrap();
        lp.height = dp(44);
        lp.topMargin = dp(6);
        return lp;
    }

    private void loadSavedBridgeSettings() {
        try {
            String[] saved = BridgeSecretStore.load(this);
            if (saved != null) {
                bridgeHostInput.setText(saved[0]);
                bridgePortInput.setText(saved[1]);
                bridgePinInput.setText(saved[2]);
                bridgeStatusText.setText("جلسة اقتران محفوظة على الهاتف");
                bridgeStatusText.setTextColor(Color.rgb(130, 220, 185));
            }
        } catch (Exception error) {
            BridgeSecretStore.clear(this);
            bridgeStatusText.setText("تعذر فتح الجلسة المحفوظة؛ أعد الاقتران");
        }
    }

    private BridgeClient bridgeClient(boolean authenticated) throws Exception {
        String host = bridgeHostInput.getText().toString().trim();
        int port = Integer.parseInt(bridgePortInput.getText().toString().trim());
        String pin = bridgePinInput.getText().toString().trim().replace(":", "").replace(" ", "");
        String token = null;
        if (authenticated) {
            String[] saved = BridgeSecretStore.load(this);
            if (saved == null || !saved[0].equals(host) || !saved[1].equals(String.valueOf(port))
                    || !saved[2].equalsIgnoreCase(pin)) {
                throw new SecurityException("أكمل الاقتران أولاً أو أعد إدخال إعدادات المضيف المحفوظة");
            }
            token = saved[3];
        }
        return new BridgeClient(host, port, pin, token);
    }

    private void pairBridge() {
        final String code = bridgeCodeInput.getText().toString().trim();
        runBridgeOperation("جارٍ تنفيذ الاقتران الآمن…", () -> {
            BridgeClient client = bridgeClient(false);
            JSONObject response = client.pair(code);
            String token = response.getString("session_token");
            String host = bridgeHostInput.getText().toString().trim();
            int port = Integer.parseInt(bridgePortInput.getText().toString().trim());
            String pin = bridgePinInput.getText().toString().trim().replace(":", "").replace(" ", "");
            BridgeSecretStore.save(this, host, port, pin, token);
            runOnUiThread(() -> bridgeCodeInput.setText(""));
            return "تم اقتران الهاتف بنجاح. الجلسة محفوظة مشفرة في Android Keystore.";
        });
    }

    private void checkBridgeHealth() {
        runBridgeOperation("جارٍ فحص الكمبيوتر وOllama…", () -> {
            JSONObject health = bridgeClient(false).health();
            return "الجسر: " + health.optString("bridge")
                    + " • Ollama: " + health.optString("ollama")
                    + " • النموذج: " + health.optString("model");
        });
    }

    private void loadRemoteTasks() {
        runBridgeOperation("جارٍ تحميل مهام الكمبيوتر…", () -> {
            JSONObject response = bridgeClient(true).tasks();
            JSONArray tasks = response.optJSONArray("tasks");
            StringBuilder message = new StringBuilder();
            if (tasks == null || tasks.length() == 0) return "لا توجد مهام مشروع في قائمة الكمبيوتر.";
            for (int i = 0; i < tasks.length(); i++) {
                JSONObject task = tasks.getJSONObject(i);
                message.append(i + 1).append(". ")
                        .append(task.optString("title")).append("\n")
                        .append("الحالة: ").append(task.optString("status")).append("\n")
                        .append("المعرّف: ").append(task.optString("id")).append("\n\n");
            }
            String value = message.toString();
            runOnUiThread(() -> new AlertDialog.Builder(this)
                    .setTitle("مهام المشروع")
                    .setMessage(value)
                    .setPositiveButton("إغلاق", null)
                    .show());
            return "تم تحميل " + tasks.length() + " مهمة من الكمبيوتر.";
        });
    }

    private void requestProposal() {
        runBridgeOperation("Ollama يعمل على إعداد اقتراح آمن…", () -> {
            JSONObject response = bridgeClient(true).createProposal();
            if ("no_task".equals(response.optString("status"))) return "لا توجد مهمة قابلة للعمل حالياً.";
            JSONObject proposal = response.optJSONObject("proposal");
            if (proposal == null) throw new IllegalStateException("رد الخادم لا يحتوي على اقتراح صالح");
            runOnUiThread(() -> showProposalDialog(proposal));
            return "وصل اقتراح جديد. راجعه قبل الموافقة.";
        });
    }

    private void loadPendingProposal() {
        runBridgeOperation("جارٍ تحميل الاقتراح المعلق…", () -> {
            JSONObject response = bridgeClient(true).pendingProposal();
            JSONObject proposal = response.optJSONObject("proposal");
            if (proposal == null) return "لا يوجد اقتراح معلق.";
            runOnUiThread(() -> showProposalDialog(proposal));
            return "تم تحميل الاقتراح للمراجعة.";
        });
    }

    private void showProposalDialog(JSONObject wrapper) {
        JSONObject task = wrapper.optJSONObject("task");
        JSONObject proposal = wrapper.optJSONObject("proposal");
        if (task == null || proposal == null) {
            showMessage("اقتراح غير صالح", "لم تصل تفاصيل الاقتراح كاملة.");
            return;
        }
        String taskId = task.optString("id");
        StringBuilder details = new StringBuilder();
        details.append("المهمة: ").append(task.optString("title")).append("\n\n");
        details.append("النموذج: ").append(wrapper.optString("model")).append("\n\n");
        details.append(proposal.optString("summary_ar")).append("\n\n");
        JSONArray steps = proposal.optJSONArray("steps");
        details.append("الخطوات المقترحة:\n");
        if (steps != null) {
            for (int i = 0; i < steps.length(); i++) {
                JSONObject step = steps.optJSONObject(i);
                if (step != null) details.append("• ").append(step.optString("kind"))
                        .append(": ").append(step.optString("target")).append("\n");
            }
        }
        JSONArray claims = proposal.optJSONArray("claims_to_verify");
        if (claims != null && claims.length() > 0) {
            details.append("\nنقاط تحتاج تحققاً:\n");
            for (int i = 0; i < claims.length(); i++) details.append("• ").append(claims.optString(i)).append("\n");
        }
        details.append("\nالموافقة لا تعني أن التنفيذ نجح؛ ستظهر النتيجة بعد تشغيل الخطوات.");
        EditText confirmation = bridgeInput("اكتب: أوافق على تنفيذ الاقتراح " + taskId, InputType.TYPE_CLASS_TEXT);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.addView(confirmation, matchWrap());
        new AlertDialog.Builder(this)
                .setTitle("مراجعة اقتراح المدير")
                .setMessage(details.toString())
                .setView(content)
                .setPositiveButton("موافقة وتنفيذ", (dialog, which) ->
                        sendProposalDecision(wrapper.optString("proposal_id"), "approve", confirmation.getText().toString().trim()))
                .setNeutralButton("رفض الاقتراح", (dialog, which) ->
                        sendProposalDecision(wrapper.optString("proposal_id"), "reject", ""))
                .setNegativeButton("إغلاق", null)
                .show();
    }

    private void sendProposalDecision(String proposalId, String decision, String confirmation) {
        runBridgeOperation(decision.equals("approve") ? "جارٍ التحقق من الموافقة وتنفيذ الخطوات المسموحة…" : "جارٍ رفض الاقتراح…", () -> {
            JSONObject result = bridgeClient(true).decide(proposalId, decision, confirmation);
            return "نتيجة القرار: " + result.optString("status")
                    + " • تم تنفيذ خطوة: " + result.optBoolean("executed", false);
        });
    }

    private void showMessage(String title, String message) {
        new AlertDialog.Builder(this).setTitle(title).setMessage(message)
                .setPositiveButton("حسناً", null).show();
    }

    private interface BridgeOperation {
        String run() throws Exception;
    }

    private void runBridgeOperation(String working, BridgeOperation operation) {
        bridgeStatusText.setText(working);
        bridgeStatusText.setTextColor(Color.rgb(255, 205, 120));
        networkExecutor.execute(() -> {
            try {
                String result = operation.run();
                runOnUiThread(() -> {
                    bridgeStatusText.setText(result);
                    bridgeStatusText.setTextColor(Color.rgb(130, 220, 185));
                });
            } catch (Exception error) {
                String message = error.getMessage() == null ? "تعذر إكمال العملية" : error.getMessage();
                runOnUiThread(() -> {
                    bridgeStatusText.setText("لم يكتمل الاتصال: " + message);
                    bridgeStatusText.setTextColor(Color.rgb(255, 150, 140));
                });
            }
        });
    }


    private EditText githubTokenInput;
    private TextView githubStatusText;

    private void addGitHubPanel(LinearLayout page) {
        LinearLayout github = panel();
        github.addView(text("ربط GitHub — مجاني", 18, Color.WHITE, true), matchWrap());
        TextView explanation = text("اتصال مباشر وآمن بمستودع Khaledserdani/IslamDetector. النسخة الحالية للقراءة والمتابعة فقط: الفروع وطلبات الدمج ونتائج Actions. لا تنشئ رمزاً بصلاحية كاملة.", 12, MUTED, false);
        LinearLayout.LayoutParams explainLp = matchWrap(); explainLp.topMargin = dp(7);
        github.addView(explanation, explainLp);

        githubTokenInput = bridgeInput("ألصق Fine-grained token هنا", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        githubTokenInput.setSingleLine(true);
        LinearLayout.LayoutParams tokenLp = matchWrap(); tokenLp.topMargin = dp(8);
        github.addView(githubTokenInput, tokenLp);

        Button connect = bridgeButton("تحقق من الرمز واحفظه بأمان");
        connect.setOnClickListener(v -> connectGitHub());
        github.addView(connect, bridgeButtonParams());

        Button refresh = bridgeButton("تحديث بيانات GitHub");
        refresh.setOnClickListener(v -> refreshGitHub());
        github.addView(refresh, bridgeButtonParams());

        Button disconnect = bridgeButton("فصل GitHub وحذف الرمز من الهاتف");
        disconnect.setOnClickListener(v -> {
            GitHubTokenStore.clear(this);
            githubTokenInput.setText("");
            githubStatusText.setText("تم فصل الربط محلياً. أعد إنشاء الرمز أو ربطه عند الحاجة.");
            githubStatusText.setTextColor(MUTED);
        });
        github.addView(disconnect, bridgeButtonParams());

        githubStatusText = text("GitHub غير مربوط. المهام المحلية لا تتأثر.", 12, MUTED, false);
        LinearLayout.LayoutParams statusLp = matchWrap(); statusLp.topMargin = dp(10);
        github.addView(githubStatusText, statusLp);
        addPanel(page, github, 12);
    }

    private void connectGitHub() {
        String token = githubTokenInput.getText().toString().trim();
        runGitHubOperation("جارٍ التحقق من GitHub…", () -> {
            GitHubClient client = new GitHubClient(token);
            String dashboard = client.dashboard();
            GitHubTokenStore.save(this, token);
            runOnUiThread(() -> githubTokenInput.setText(""));
            return dashboard;
        });
    }

    private void refreshGitHub() {
        runGitHubOperation("جارٍ تحديث بيانات المستودع…", () -> {
            String token = GitHubTokenStore.load(this);
            if (token == null) throw new SecurityException("أدخل رمز GitHub واربط الحساب أولاً.");
            return new GitHubClient(token).dashboard();
        });
    }

    private void runGitHubOperation(String working, BridgeOperation operation) {
        githubStatusText.setText(working);
        githubStatusText.setTextColor(Color.rgb(255, 205, 120));
        networkExecutor.execute(() -> {
            try {
                String result = operation.run();
                runOnUiThread(() -> {
                    githubStatusText.setText("تم الاتصال بنجاح — بيانات مباشرة من GitHub.");
                    githubStatusText.setTextColor(Color.rgb(130, 220, 185));
                    new AlertDialog.Builder(this)
                            .setTitle("لوحة GitHub")
                            .setMessage(result)
                            .setPositiveButton("إغلاق", null)
                            .show();
                });
            } catch (Exception error) {
                String message = error.getMessage() == null ? "تعذر الاتصال بـ GitHub" : error.getMessage();
                runOnUiThread(() -> {
                    githubStatusText.setText("لم ينجح الاتصال: " + message);
                    githubStatusText.setTextColor(Color.rgb(255, 150, 140));
                });
            }
        });
    }

    private void renderTasks() {
        taskList.removeAllViews();
        List<AgentTaskStore.Task> tasks = store.all();
        int done = 0;
        for (AgentTaskStore.Task task : tasks) if (task.done) done++;
        countText.setText(tasks.size() + " مهمة • " + done + " مكتملة");

        if (tasks.isEmpty()) {
            TextView empty = text("لا توجد مهام بعد. أضف أول مهمة للمدير المساعد.", 14, MUTED, false);
            LinearLayout.LayoutParams ep = matchWrap(); ep.topMargin = dp(12);
            taskList.addView(empty, ep);
            return;
        }

        for (AgentTaskStore.Task task : tasks) {
            LinearLayout card = panel();
            LinearLayout row = new LinearLayout(this);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setOrientation(LinearLayout.HORIZONTAL);

            TextView taskTitle = text(task.title, 14, task.done ? MUTED : Color.WHITE, true);
            if (task.done) taskTitle.setPaintFlags(taskTitle.getPaintFlags() | 16);
            row.addView(taskTitle, new LinearLayout.LayoutParams(0, -2, 1));

            Button toggle = smallButton(task.done ? "إعادة" : "تم", task.done ? Color.rgb(75, 91, 111) : GREEN);
            row.addView(toggle, new LinearLayout.LayoutParams(dp(66), dp(38)));
            toggle.setOnClickListener(v -> {
                store.setDone(task.id, !task.done);
                renderTasks();
            });

            Button delete = smallButton("حذف", Color.rgb(132, 61, 65));
            LinearLayout.LayoutParams del = new LinearLayout.LayoutParams(dp(62), dp(38));
            del.rightMargin = dp(6);
            row.addView(delete, del);
            delete.setOnClickListener(v -> {
                store.delete(task.id);
                renderTasks();
            });

            card.addView(row, matchWrap());
            LinearLayout.LayoutParams cp = matchWrap(); cp.topMargin = dp(8);
            taskList.addView(card, cp);
        }
    }

    private void showAddTaskDialog() {
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setTextSize(16);
        input.setHint("اكتب عنوان المهمة");
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        input.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);
        new AlertDialog.Builder(this)
                .setTitle("مهمة جديدة")
                .setView(input)
                .setNegativeButton("إلغاء", null)
                .setPositiveButton("حفظ", (dialog, which) -> {
                    String title = input.getText().toString().trim();
                    if (!title.isEmpty()) {
                        try {
                            store.add(title);
                            renderTasks();
                        } catch (IllegalArgumentException | IllegalStateException error) {
                            new AlertDialog.Builder(this).setMessage(error.getMessage()).setPositiveButton("حسناً", null).show();
                        }
                    }
                }).show();
    }

    private LinearLayout panel() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(14), dp(14), dp(14), dp(14));
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(PANEL);
        bg.setCornerRadius(dp(14));
        bg.setStroke(dp(1), Color.rgb(40, 59, 81));
        box.setBackground(bg);
        return box;
    }

    private void addPanel(LinearLayout parent, LinearLayout panel, int top) {
        LinearLayout.LayoutParams lp = matchWrap(); lp.topMargin = dp(top);
        parent.addView(panel, lp);
    }

    private TextView text(String value, int size, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        view.setGravity(Gravity.RIGHT);
        view.setLineSpacing(dp(3), 1f);
        return view;
    }

    private Button button(String value, int color) {
        Button b = new Button(this);
        b.setText(value);
        b.setTextColor(Color.WHITE);
        b.setTextSize(15);
        b.setAllCaps(false);
        b.setBackground(round(color, 12));
        return b;
    }

    private Button smallButton(String value, int color) {
        Button b = button(value, color);
        b.setTextSize(12);
        b.setPadding(dp(2), 0, dp(2), 0);
        return b;
    }

    private GradientDrawable round(int color, int radius) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color);
        d.setCornerRadius(dp(radius));
        return d;
    }

    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(-1, -2);
    }

    private LinearLayout.LayoutParams wrap() {
        return new LinearLayout.LayoutParams(-2, -2);
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }
}
