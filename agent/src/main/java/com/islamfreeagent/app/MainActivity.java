package com.islamfreeagent.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.database.Cursor;
import android.net.Uri;
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

import java.io.File;
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
    private EditText dcVoltageInput;
    private EditText dcResistorsInput;
    private TextView dcResultText;
    private TextView aiStatusText;
    private TextView aiReplyText;
    private EditText aiPromptInput;
    private Button aiSendButton;
    private DownloadManager downloadManager;
    private long modelDownloadId = -1L;
    private OnDeviceAiEngine localAi;
    private final ExecutorService modelExecutor = Executors.newSingleThreadExecutor();
    private final ExecutorService networkExecutor = Executors.newSingleThreadExecutor();

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        store = new AgentTaskStore(this);
        downloadManager = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
        modelDownloadId = getSharedPreferences("local_ai_model", MODE_PRIVATE).getLong("download_id", -1L);
        localAi = new OnDeviceAiEngine(getCacheDir().getAbsolutePath());
        buildScreen();
        loadSavedGitHubSettings();
        renderTasks();
    }

    @Override protected void onDestroy() {
        localAi.close();
        modelExecutor.shutdownNow();
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
        TextView noticeTitle = text("مدير محلي مستقل على الهاتف", 16, Color.rgb(255, 205, 120), true);
        notice.addView(noticeTitle, matchWrap());
        TextView noticeBody = text("إدارة المهام والمختبر الحسابي تعمل على الهاتف. ويمكن تشغيل نموذج ذكاء اصطناعي محلي بعد تنزيله مجاناً مرة واحدة؛ لا نستخدم خادماً أو اشتراكاً.", 13, MUTED, false);
        LinearLayout.LayoutParams nb = matchWrap(); nb.topMargin = dp(8);
        notice.addView(noticeBody, nb);
        addPanel(page, notice, 18);

        LinearLayout status = panel();
        status.addView(text("حالة التطبيق", 16, Color.WHITE, true), matchWrap());
        TextView state = text("واجهة الهاتف: تعمل", 14, Color.rgb(130, 220, 185), true);
        LinearLayout.LayoutParams st = matchWrap(); st.topMargin = dp(8);
        status.addView(state, st);
        TextView engine = text("الذكاء المحلي: نزّل النموذج المجاني أول مرة لتشغيله دون إنترنت", 13, MUTED, false);
        LinearLayout.LayoutParams en = matchWrap(); en.topMargin = dp(5);
        status.addView(engine, en);
        addPanel(page, status, 12);

        LinearLayout dcLab = panel();
        dcLab.addView(text("مختبر DC المحلي — يعمل دون كمبيوتر أو إنترنت", 17, Color.WHITE, true), matchWrap());
        TextView dcHelp = text("مصدر جهد مثالي بين vcc والأرضي 0. اكتب المقاومات كسطور مفصولة بفاصلة منقوطة، وكل سطر: العقدة الأولى,العقدة الثانية,المقاومة بالأوم. مثال: vcc,mid,1000;mid,0,1000", 12, MUTED, false);
        LinearLayout.LayoutParams dh = matchWrap(); dh.topMargin = dp(7);
        dcLab.addView(dcHelp, dh);
        dcVoltageInput = textInput("جهد المصدر بالفولت — مثال 10", InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL | InputType.TYPE_NUMBER_FLAG_SIGNED);
        dcResistorsInput = textInput("vcc,mid,1000;mid,0,1000", InputType.TYPE_CLASS_TEXT);
        dcResistorsInput.setSingleLine(false);
        dcResistorsInput.setMinLines(2);
        dcResistorsInput.setGravity(Gravity.TOP | Gravity.LEFT);
        addInput(dcLab, dcVoltageInput);
        addInput(dcLab, dcResistorsInput);
        Button runDc = actionButton("تشغيل محاكاة DC على الهاتف");
        runDc.setOnClickListener(v -> runDcLabSimulation());
        dcLab.addView(runDc, actionButtonParams());
        Button queueDc = actionButton("حفظ التجربة لتعمل ليلاً");
        queueDc.setOnClickListener(v -> enqueueDcLab());
        dcLab.addView(queueDc, actionButtonParams());
        Button enableNight = actionButton("تفعيل الجدولة الليلية 20:00–06:00");
        enableNight.setOnClickListener(v -> {
            try {
                AgentLabScheduler.enable(this);
                dcResultText.setText("تم تفعيل الجدولة الدورية؛ التنفيذ داخل نافذة الجزائر الليلية فقط، وقد يؤخر Android وقت التشغيل.");
            } catch (Exception error) {
                dcResultText.setText("تعذر تفعيل الجدولة: " + error.getMessage());
            }
        });
        dcLab.addView(enableNight, actionButtonParams());
        Button disableNight = actionButton("إيقاف الجدولة الليلية");
        disableNight.setOnClickListener(v -> {
            AgentLabScheduler.disable(this);
            dcResultText.setText("تم طلب إيقاف الجدولة الليلية.");
        });
        dcLab.addView(disableNight, actionButtonParams());
        Button queueStatus = actionButton("تحديث حالة تجارب المختبر");
        queueStatus.setOnClickListener(v -> dcResultText.setText(AgentLabQueue.summary(this)));
        dcLab.addView(queueStatus, actionButtonParams());
        dcResultText = text("لم تُشغّل محاكاة بعد.", 13, MUTED, false);
        LinearLayout.LayoutParams dr = matchWrap(); dr.topMargin = dp(9);
        dcLab.addView(dcResultText, dr);
        addPanel(page, dcLab, 12);

        addLocalAiPanel(page);
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

        TextView footer = text("المهام والاختبارات والذكاء الاصطناعي بعد تنزيل النموذج تعمل محلياً على الهاتف. تنزيل النموذج يحتاج اتصال Wi-Fi مرة واحدة.", 12, MUTED, false);
        LinearLayout.LayoutParams fp = matchWrap(); fp.topMargin = dp(20);
        page.addView(footer, fp);
        setContentView(scroll);
    }

    private void addLocalAiPanel(LinearLayout page) {
        LinearLayout ai = panel();
        ai.addView(text("الذكاء الاصطناعي المحلي — Qwen3 0.6B", 17, Color.WHITE, true), matchWrap());
        TextView details = text("نموذج مفتوح بترخيص Apache 2.0. حجمه 586 MB تقريباً. التنزيل عبر Wi-Fi فقط، وبعد اكتماله يعمل على معالج الهاتف دون إنترنت أو API مدفوع.", 12, MUTED, false);
        LinearLayout.LayoutParams detailsLp = matchWrap(); detailsLp.topMargin = dp(7);
        ai.addView(details, detailsLp);

        Button download = actionButton("تنزيل النموذج المجاني (Wi-Fi فقط)");
        download.setOnClickListener(v -> startModelDownload());
        ai.addView(download, actionButtonParams());

        Button checkDownload = actionButton("تحديث حالة التنزيل");
        checkDownload.setOnClickListener(v -> refreshModelStatus());
        ai.addView(checkDownload, actionButtonParams());

        Button load = actionButton("التحقق من النموذج وتشغيل الذكاء المحلي");
        load.setOnClickListener(v -> verifyAndLoadModel());
        ai.addView(load, actionButtonParams());

        aiPromptInput = textInput("اكتب سؤالك لإسلام — يعمل محلياً بعد تحميل النموذج", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        aiPromptInput.setSingleLine(false);
        aiPromptInput.setMinLines(2);
        aiPromptInput.setGravity(Gravity.TOP | Gravity.RIGHT);
        addInput(ai, aiPromptInput);

        aiSendButton = actionButton("إرسال إلى الذكاء المحلي");
        aiSendButton.setEnabled(false);
        aiSendButton.setOnClickListener(v -> sendLocalAiMessage());
        ai.addView(aiSendButton, actionButtonParams());

        Button reset = actionButton("بدء محادثة جديدة");
        reset.setOnClickListener(v -> localAi.resetConversation(new OnDeviceAiEngine.Callback() {
            @Override public void onSuccess(String message) {
                runOnUiThread(() -> aiStatusText.setText(message));
            }
            @Override public void onFailure(String message) {
                runOnUiThread(() -> aiStatusText.setText("تعذر إعادة المحادثة: " + message));
            }
        }));
        ai.addView(reset, actionButtonParams());

        aiStatusText = text("النموذج غير منزّل بعد.", 12, MUTED, false);
        LinearLayout.LayoutParams statusLp = matchWrap(); statusLp.topMargin = dp(9);
        ai.addView(aiStatusText, statusLp);
        aiReplyText = text("ستظهر إجابة النموذج هنا.", 13, Color.WHITE, false);
        LinearLayout.LayoutParams replyLp = matchWrap(); replyLp.topMargin = dp(9);
        ai.addView(aiReplyText, replyLp);
        addPanel(page, ai, 12);
        refreshModelStatus();
    }

    private File modelFile() {
        File directory = getExternalFilesDir(null);
        return directory == null ? null : new File(directory, OnDeviceModelSpec.FILE_NAME);
    }

    private void startModelDownload() {
        File file = modelFile();
        if (file == null) {
            aiStatusText.setText("مساحة ملفات التطبيق غير متاحة.");
            return;
        }
        if (file.exists() && file.length() == OnDeviceModelSpec.EXPECTED_BYTES) {
            aiStatusText.setText("ملف النموذج موجود. اضغط التحقق والتشغيل.");
            return;
        }
        if (modelDownloadId > 0 && isDownloadActive(modelDownloadId)) {
            refreshModelStatus();
            return;
        }
        if (file.exists()) file.delete();
        try {
            DownloadManager.Request request =
                    new DownloadManager.Request(Uri.parse(OnDeviceModelSpec.DOWNLOAD_URL));
            request.setTitle("تنزيل نموذج إسلام المحلي");
            request.setDescription("Qwen3 0.6B — 586 MB — Wi-Fi فقط");
            request.setAllowedNetworkTypes(DownloadManager.Request.NETWORK_WIFI);
            request.setAllowedOverMetered(false);
            request.setAllowedOverRoaming(false);
            request.setNotificationVisibility(
                    DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            request.setDestinationInExternalFilesDir(this, null, OnDeviceModelSpec.FILE_NAME);
            modelDownloadId = downloadManager.enqueue(request);
            getSharedPreferences("local_ai_model", MODE_PRIVATE).edit()
                    .putLong("download_id", modelDownloadId).apply();
            aiStatusText.setText("بدأ التنزيل عبر Wi-Fi فقط. يمكنك مغادرة الشاشة والعودة لمتابعة الحالة.");
        } catch (Exception error) {
            aiStatusText.setText("تعذر بدء التنزيل: " + error.getMessage());
        }
    }

    private boolean isDownloadActive(long id) {
        try (Cursor cursor = downloadManager.query(new DownloadManager.Query().setFilterById(id))) {
            if (cursor == null || !cursor.moveToFirst()) return false;
            int status = cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS));
            return status == DownloadManager.STATUS_PENDING
                    || status == DownloadManager.STATUS_RUNNING
                    || status == DownloadManager.STATUS_PAUSED;
        } catch (Exception ignored) {
            return false;
        }
    }

    private void refreshModelStatus() {
        File file = modelFile();
        if (file != null && file.isFile() && file.length() == OnDeviceModelSpec.EXPECTED_BYTES) {
            aiStatusText.setText("اكتمل تنزيل ملف النموذج (" + file.length() + " بايت). تحقّق من البصمة قبل التشغيل.");
            return;
        }
        if (modelDownloadId <= 0) {
            aiStatusText.setText("النموذج غير منزّل بعد. التنزيل المجاني يحتاج Wi-Fi.");
            return;
        }
        try (Cursor cursor = downloadManager.query(new DownloadManager.Query().setFilterById(modelDownloadId))) {
            if (cursor == null || !cursor.moveToFirst()) {
                aiStatusText.setText("لم نعثر على مهمة التنزيل. يمكنك بدء التنزيل من جديد.");
                return;
            }
            int status = cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS));
            long downloaded = cursor.getLong(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR));
            long total = cursor.getLong(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES));
            if (status == DownloadManager.STATUS_SUCCESSFUL) {
                aiStatusText.setText("اكتمل التنزيل. الحجم: " + downloaded + " بايت. اضغط التحقق والتشغيل.");
            } else if (status == DownloadManager.STATUS_FAILED) {
                int reason = cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_REASON));
                aiStatusText.setText("فشل التنزيل (رمز " + reason + "). تحقق من Wi-Fi ثم أعد المحاولة.");
            } else {
                String progress = total > 0 ? (downloaded * 100 / total) + "%" : "جارٍ الاتصال";
                aiStatusText.setText("تنزيل النموذج: " + progress + " • "
                        + downloaded / (1024 * 1024) + " / "
                        + (total > 0 ? total / (1024 * 1024) : 0) + " MB");
            }
        } catch (Exception error) {
            aiStatusText.setText("تعذر قراءة حالة التنزيل: " + error.getMessage());
        }
    }

    private void verifyAndLoadModel() {
        File file = modelFile();
        if (file == null || !file.isFile()) {
            aiStatusText.setText("نزّل النموذج أولاً عبر Wi-Fi.");
            return;
        }
        aiStatusText.setText("جارٍ فحص حجم النموذج وبصمة SHA-256…");
        modelExecutor.execute(() -> {
            final boolean valid;
            try {
                valid = OnDeviceModelSpec.isValid(file);
            } catch (Exception error) {
                runOnUiThread(() -> aiStatusText.setText("تعذر فحص الملف: " + error.getMessage()));
                return;
            }
            runOnUiThread(() -> {
                if (!valid) {
                    aiStatusText.setText("ملف النموذج غير مكتمل أو بصمته غير صحيحة. احذف الملف وأعد تنزيله.");
                    return;
                }
                aiStatusText.setText("البصمة صحيحة. جارٍ تحميل النموذج على معالج الهاتف…");
                localAi.load(file.getAbsolutePath(), new OnDeviceAiEngine.Callback() {
                    @Override public void onSuccess(String message) {
                        runOnUiThread(() -> {
                            aiStatusText.setText(message + " — يعمل دون إنترنت.");
                            aiSendButton.setEnabled(true);
                        });
                    }
                    @Override public void onFailure(String message) {
                        runOnUiThread(() -> {
                            aiStatusText.setText("تعذر تشغيل النموذج: " + message);
                            aiSendButton.setEnabled(false);
                        });
                    }
                });
            });
        });
    }

    private void sendLocalAiMessage() {
        String prompt = aiPromptInput.getText().toString().trim();
        if (prompt.isEmpty()) return;
        aiPromptInput.setText("");
        aiSendButton.setEnabled(false);
        aiReplyText.setText("إسلام يفكر محلياً…");
        localAi.sendMessage(prompt, new OnDeviceAiEngine.Callback() {
            @Override public void onSuccess(String message) {
                runOnUiThread(() -> {
                    aiReplyText.setText(message);
                    aiSendButton.setEnabled(true);
                });
            }
            @Override public void onFailure(String message) {
                runOnUiThread(() -> {
                    aiReplyText.setText("تعذر توليد الرد: " + message);
                    aiSendButton.setEnabled(true);
                });
            }
        });
    }

    private java.util.ArrayList<AgentDcLab.Resistor> readDcResistors() {
        java.util.ArrayList<AgentDcLab.Resistor> resistors = new java.util.ArrayList<>();
        String raw = dcResistorsInput.getText().toString().trim();
        if (raw.isEmpty()) throw new IllegalArgumentException("أدخل مقاومة واحدة على الأقل");
        String[] rows = raw.split("[;\n]+");
        if (rows.length > 100) throw new IllegalArgumentException("الحد الأقصى 100 مقاومة في التجربة");
        for (String row : rows) {
            String[] fields = row.trim().split(",");
            if (fields.length != 3) throw new IllegalArgumentException("صيغة كل مقاومة: عقدة,عقدة,أوم");
            resistors.add(new AgentDcLab.Resistor(fields[0].trim(), fields[1].trim(),
                    Double.parseDouble(fields[2].trim())));
        }
        return resistors;
    }

    private void enqueueDcLab() {
        try {
            double volts = Double.parseDouble(dcVoltageInput.getText().toString().trim());
            String id = AgentLabQueue.enqueue(this, volts, readDcResistors());
            dcResultText.setText("حُفظت التجربة في قائمة العمل الليلي. المعرّف: " + id
                    + "\n" + AgentLabQueue.summary(this));
        } catch (Exception error) {
            dcResultText.setText("تعذر حفظ التجربة: " + error.getMessage());
        }
    }

    private void runDcLabSimulation() {
        final double volts;
        final java.util.ArrayList<AgentDcLab.Resistor> resistors = new java.util.ArrayList<>();
        try {
            volts = Double.parseDouble(dcVoltageInput.getText().toString().trim());
            String raw = dcResistorsInput.getText().toString().trim();
            if (raw.isEmpty()) throw new IllegalArgumentException("أدخل مقاومة واحدة على الأقل");
            String[] rows = raw.split("[;\n]+");
            if (rows.length > 100) throw new IllegalArgumentException("الحد الأقصى 100 مقاومة في التجربة");
            for (String row : rows) {
                String[] fields = row.trim().split(",");
                if (fields.length != 3) throw new IllegalArgumentException("صيغة كل مقاومة: عقدة,عقدة,أوم");
                resistors.add(new AgentDcLab.Resistor(fields[0].trim(), fields[1].trim(),
                        Double.parseDouble(fields[2].trim())));
            }
        } catch (Exception error) {
            dcResultText.setText("مدخلات غير صحيحة: " + error.getMessage());
            return;
        }
        dcResultText.setText("جارٍ حل الدارة والتحقق من قانون كيرشوف…");
        networkExecutor.execute(() -> {
            try {
                AgentDcLab.Result result = AgentDcLab.solve("0", "vcc", volts, resistors);
                StringBuilder report = new StringBuilder("النتيجة — جهد العقد:\n");
                for (java.util.Map.Entry<String, Double> entry : result.nodeVoltages.entrySet()) {
                    report.append(entry.getKey()).append(" = ")
                            .append(String.format(java.util.Locale.US, "%.6f V", entry.getValue())).append("\n");
                }
                report.append("تيار المصدر: ")
                        .append(String.format(java.util.Locale.US, "%.9f A", result.sourceCurrentAmps))
                        .append("\nأقصى خطأ KCL: ")
                        .append(String.format(java.util.Locale.US, "%.3e A", result.maximumKclResidualAmps));
                final String message = report.toString();
                runOnUiThread(() -> dcResultText.setText(message));
            } catch (Exception error) {
                runOnUiThread(() -> dcResultText.setText("تعذر حل الدارة: " + error.getMessage()));
            }
        });
    }

    private EditText textInput(String hint, int type) {
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

    private Button actionButton(String title) {
        Button b = button(title, Color.rgb(40, 83, 112));
        b.setTextSize(13);
        return b;
    }

    private LinearLayout.LayoutParams actionButtonParams() {
        LinearLayout.LayoutParams lp = matchWrap();
        lp.height = dp(44);
        lp.topMargin = dp(6);
        return lp;
    }

    private EditText githubTokenInput;
    private TextView githubStatusText;

    private void addGitHubPanel(LinearLayout page) {
        LinearLayout github = panel();
        github.addView(text("ربط GitHub — مجاني", 18, Color.WHITE, true), matchWrap());
        TextView explanation = text("لوحة اختيارية لقراءة حالة مستودع GitHub مباشرة من الهاتف. لا تنفذ تعديلات أو دمجاً تلقائياً.", 12, MUTED, false);
        LinearLayout.LayoutParams explainLp = matchWrap(); explainLp.topMargin = dp(7);
        github.addView(explanation, explainLp);

        githubTokenInput = textInput("ألصق Fine-grained token هنا", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        githubTokenInput.setSingleLine(true);
        LinearLayout.LayoutParams tokenLp = matchWrap(); tokenLp.topMargin = dp(8);
        github.addView(githubTokenInput, tokenLp);

        Button connect = actionButton("تحقق من الرمز واحفظه بأمان");
        connect.setOnClickListener(v -> connectGitHub());
        github.addView(connect, actionButtonParams());

        Button refresh = actionButton("تحديث بيانات GitHub");
        refresh.setOnClickListener(v -> refreshGitHub());
        github.addView(refresh, actionButtonParams());

        Button disconnect = actionButton("فصل GitHub وحذف الرمز من الهاتف");
        disconnect.setOnClickListener(v -> {
            GitHubTokenStore.clear(this);
            githubTokenInput.setText("");
            githubStatusText.setText("تم فصل الربط محلياً. أعد إنشاء الرمز أو ربطه عند الحاجة.");
            githubStatusText.setTextColor(MUTED);
        });
        github.addView(disconnect, actionButtonParams());

        githubStatusText = text("GitHub غير مربوط. المهام المحلية لا تتأثر.", 12, MUTED, false);
        LinearLayout.LayoutParams statusLp = matchWrap(); statusLp.topMargin = dp(10);
        github.addView(githubStatusText, statusLp);
        addPanel(page, github, 12);
    }

    private void loadSavedGitHubSettings() {
        try {
            String savedToken = GitHubTokenStore.load(this);
            if (savedToken != null && !savedToken.isEmpty()) {
                githubStatusText.setText("رمز GitHub محفوظ ومشفّر على الهاتف. اضغط «تحديث بيانات GitHub» للتحقق من الجلسة.");
                githubStatusText.setTextColor(Color.rgb(130, 220, 185));
            }
        } catch (Exception error) {
            GitHubTokenStore.clear(this);
            githubStatusText.setText("تعذر فتح الرمز المحفوظ؛ احذفه وأنشئ رمزاً جديداً.");
            githubStatusText.setTextColor(Color.rgb(255, 150, 140));
        }
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

    private interface Operation { String run() throws Exception; }

    private void runGitHubOperation(String working, Operation operation) {
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
