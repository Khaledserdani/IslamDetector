package com.islamfreeagent.app;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.database.Cursor;
import android.net.Uri;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Build;
import android.text.InputType;
import android.text.InputFilter;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONObject;
import org.json.JSONArray;

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
    private boolean downloadReceiverRegistered = false;
    private final BroadcastReceiver modelDownloadReceiver = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            if (DownloadManager.ACTION_DOWNLOAD_COMPLETE.equals(intent.getAction())) {
                long completedId = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1L);
                if (completedId == modelDownloadId && aiStatusText != null) refreshModelStatus();
            }
        }
    };
    private OnDeviceAiEngine localAi;
    private String activeExecutionTaskId = null;
    private final ExecutorService modelExecutor = Executors.newSingleThreadExecutor();
    private final ExecutorService networkExecutor = Executors.newSingleThreadExecutor();

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        store = new AgentTaskStore(this);
        downloadManager = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
        modelDownloadId = getSharedPreferences("local_ai_model", MODE_PRIVATE).getLong("download_id", -1L);
        registerModelDownloadReceiver();
        localAi = new OnDeviceAiEngine(getCacheDir().getAbsolutePath());
        buildScreen();
        loadSavedGitHubSettings();
        renderTasks();
    }

    @Override protected void onResume() {
        super.onResume();
        if (aiStatusText != null) refreshModelStatus();
    }

    @Override protected void onDestroy() {
        if (downloadReceiverRegistered) {
            try {
                unregisterReceiver(modelDownloadReceiver);
            } catch (IllegalArgumentException ignored) {
                // Receiver was already unregistered by the platform or lifecycle cleanup.
            }
            downloadReceiverRegistered = false;
        }
        localAi.close();
        modelExecutor.shutdownNow();
        networkExecutor.shutdownNow();
        super.onDestroy();
    }

    private void buildScreen() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(BG);
        // Android 15 enforces edge-to-edge for targetSdk 35; keep content clear
        // of the status and navigation bars on both new and older Android versions.
        scroll.setClipToPadding(false);
        scroll.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(0, insets.getSystemWindowInsetTop(), 0, insets.getSystemWindowInsetBottom());
            return insets;
        });

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
        TextView taskHelp = text("بعد إضافة المهمة، اضغط «تنفيذ» ليحللها Qwen ويعرض خطة محدودة قبل أي كتابة.", 12, MUTED, false);
        LinearLayout.LayoutParams taskHelpLp = matchWrap(); taskHelpLp.topMargin = dp(6);
        page.addView(taskHelp, taskHelpLp);

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
        scroll.requestApplyInsets();
    }

    private void addLocalAiPanel(LinearLayout page) {
        LinearLayout ai = panel();
        ai.addView(text("الذكاء الاصطناعي المحلي — Qwen3 0.6B", 17, Color.WHITE, true), matchWrap());
        TextView details = text("نموذج مفتوح بترخيص Apache 2.0. حجمه 586 MB تقريباً. يمكن تنزيله عبر Wi-Fi أو بيانات الهاتف، وبعد اكتماله يعمل على معالج الهاتف دون إنترنت أو API مدفوع.", 12, MUTED, false);
        LinearLayout.LayoutParams detailsLp = matchWrap(); detailsLp.topMargin = dp(7);
        ai.addView(details, detailsLp);

        Button download = actionButton("تنزيل النموذج المجاني عبر الإنترنت");
        download.setOnClickListener(v -> startModelDownload());
        ai.addView(download, actionButtonParams());

        Button checkDownload = actionButton("تحديث حالة التنزيل");
        checkDownload.setOnClickListener(v -> refreshModelStatus());
        ai.addView(checkDownload, actionButtonParams());

        Button load = actionButton("التحقق من النموذج وتشغيل الذكاء المحلي");
        load.setOnClickListener(v -> verifyAndLoadModel());
        ai.addView(load, actionButtonParams());

        TextView promptLabel = text("اكتب رسالتك أو سؤالك هنا", 13, Color.WHITE, true);
        LinearLayout.LayoutParams promptLabelLp = matchWrap(); promptLabelLp.topMargin = dp(10);
        ai.addView(promptLabel, promptLabelLp);
        aiPromptInput = textInput("اكتب رسالتك لإسلام هنا", InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
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

    private void registerModelDownloadReceiver() {
        IntentFilter filter = new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE);
        if (Build.VERSION.SDK_INT >= 33) {
            registerReceiver(modelDownloadReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(modelDownloadReceiver, filter);
        }
        downloadReceiverRegistered = true;
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
        if (modelDownloadId > 0 && isDownloadActive(modelDownloadId)) {
            refreshModelStatus();
            return;
        }
        if (file.exists() && file.length() == OnDeviceModelSpec.EXPECTED_BYTES) {
            aiStatusText.setText("جارٍ التحقق من الملف الموجود قبل إعادة استخدامه…");
            modelExecutor.execute(() -> {
                boolean valid;
                try {
                    valid = OnDeviceModelSpec.isValid(file);
                } catch (Exception error) {
                    valid = false;
                }
                final boolean fileValid = valid;
                runOnUiThread(() -> {
                    if (fileValid) {
                        aiStatusText.setText("النموذج موجود وبصمته صحيحة. اضغط التحقق والتشغيل.");
                    } else {
                        file.delete();
                        enqueueModelDownload(file);
                    }
                });
            });
            return;
        }
        if (file.exists()) file.delete();
        enqueueModelDownload(file);
    }

    private void enqueueModelDownload(File file) {
        try {
            DownloadManager.Request request =
                    new DownloadManager.Request(Uri.parse(OnDeviceModelSpec.DOWNLOAD_URL));
            request.setTitle("تنزيل نموذج إسلام المحلي");
            request.setDescription("Qwen3 0.6B — 586 MB — عبر الإنترنت المتاح");
            request.setNotificationVisibility(
                    DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            request.setDestinationInExternalFilesDir(this, null, OnDeviceModelSpec.FILE_NAME);
            modelDownloadId = downloadManager.enqueue(request);
            getSharedPreferences("local_ai_model", MODE_PRIVATE).edit()
                    .putLong("download_id", modelDownloadId).apply();
            aiStatusText.setText("بدأ التنزيل عبر اتصال الإنترنت المتاح (Wi-Fi أو بيانات الهاتف). يمكنك مغادرة الشاشة والعودة لمتابعة الحالة.");
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
            aiStatusText.setText("النموذج غير منزّل بعد. يمكنك تنزيله عبر Wi-Fi أو بيانات الهاتف.");
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
                aiStatusText.setText("فشل التنزيل (رمز " + reason + "). تحقق من اتصال الإنترنت ثم أعد المحاولة.");
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
            aiStatusText.setText("نزّل النموذج أولاً عبر اتصال الإنترنت.");
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

    private void executeTaskWithLocalAi(AgentTaskStore.Task task) {
        if (!store.contains(task.id)) return;
        if (activeExecutionTaskId != null) {
            showMessage("تنفيذ جارٍ", "انتظر انتهاء المهمة الحالية أولاً.");
            return;
        }
        activeExecutionTaskId = task.id;
        store.setExecutionResult(task.id, false, "");
        aiReplyText.setText("جارٍ تحليل المهمة الحالية: " + task.title);
        renderTasks();
        localAi.planTask("عنوان المهمة: " + task.title + "\nالتفاصيل الكاملة: " + task.description, new OnDeviceAiEngine.Callback() {
            @Override public void onSuccess(String rawPlan) {
                try {
                    String cleaned = rawPlan.trim();
                    int start = cleaned.indexOf('{'), end = cleaned.lastIndexOf('}');
                    if (start < 0 || end <= start) throw new IllegalArgumentException("لم يرجع النموذج خطة JSON صالحة.");
                    JSONObject plan = new JSONObject(cleaned.substring(start, end + 1));
                    if ("unsupported".equals(plan.optString("action", "")))
                        throw new IllegalArgumentException("هذه المهمة خارج الأدوات المحلية المسموحة حالياً.");
                    AgentTaskToolRunner.validate(plan);
                    runOnUiThread(() -> {
                        if (store.contains(task.id) && task.id.equals(activeExecutionTaskId))
                            showTaskPlanConfirmation(task, plan);
                        else if (task.id.equals(activeExecutionTaskId)) activeExecutionTaskId = null;
                    });
                } catch (Exception error) {
                    String message = error.getMessage() == null ? "خطة غير صالحة" : error.getMessage();
                    store.setExecutionResult(task.id, false, "لم تُنفذ المهمة: " + message);
                    runOnUiThread(() -> {
                        if (!task.id.equals(activeExecutionTaskId)) return;
                        activeExecutionTaskId = null;
                        aiReplyText.setText("لم تُنفذ المهمة: " + message);
                        renderTasks();
                        showMessage("تعذر تنفيذ المهمة", message);
                    });
                }
            }
            @Override public void onFailure(String message) {
                store.setExecutionResult(task.id, false, "لم تُنفذ المهمة: " + message);
                runOnUiThread(() -> {
                    if (!task.id.equals(activeExecutionTaskId)) return;
                    activeExecutionTaskId = null;
                    aiReplyText.setText("تعذر تحليل المهمة: " + message);
                    renderTasks();
                });
            }
        });
    }

    private void showTaskPlanConfirmation(AgentTaskStore.Task task, JSONObject plan) {
        if (!store.contains(task.id) || !task.id.equals(activeExecutionTaskId)) {
            if (task.id.equals(activeExecutionTaskId)) activeExecutionTaskId = null;
            return;
        }
        StringBuilder preview = new StringBuilder("العملية: إنشاء الملفات وقراءتها للتحقق\n")
                .append("المجلد: مساحة عمل التطبيق الخاصة\n\n");
        JSONArray plannedFiles = plan.optJSONArray("files");
        if (plannedFiles != null) {
            for (int i = 0; i < plannedFiles.length(); i++) {
                JSONObject file = plannedFiles.optJSONObject(i);
                if (file != null) preview.append("الملف: ").append(file.optString("filename"))
                        .append("\nالمحتوى المقترح:\n").append(file.optString("content")).append("\n\n");
            }
        } else {
            preview.append("الملف: ").append(plan.optString("filename"))
                    .append("\nالمحتوى المقترح:\n").append(plan.optString("content"));
        }
        preview.append("\nلن يسمح التطبيق بمسارات خارج مجلد العمل أو أوامر النظام.");
        new AlertDialog.Builder(this)
                .setTitle("مراجعة تنفيذ المهمة")
                .setMessage(preview.toString())
                .setPositiveButton("موافقة وكتابة الملفات", (dialog, which) -> {
                    if (!store.contains(task.id) || !task.id.equals(activeExecutionTaskId)) {
                        if (task.id.equals(activeExecutionTaskId)) activeExecutionTaskId = null;
                        showMessage("المهمة تغيّرت", "لم يتم التنفيذ لأن المهمة لم تعد موجودة أو لم تعد المهمة الحالية.");
                        return;
                    }
                    aiReplyText.setText("جارٍ إنشاء الملفات وقراءتها للتحقق…");
                    networkExecutor.execute(() -> {
                        try {
                            String verified;
                            // Serialize the final existence check, file writes, and result save
                            // against task deletion. If deletion wins the lock, no files are written.
                            synchronized (store) {
                                if (!store.contains(task.id))
                                    throw new IllegalStateException("حُذفت المهمة قبل بدء الكتابة؛ لم تُنشأ ملفات.");
                                JSONObject result = new AgentTaskToolRunner(this).execute(plan);
                                JSONArray files = result.getJSONArray("files");
                                StringBuilder report = new StringBuilder("تم التنفيذ والتحقق من جميع الملفات (")
                                        .append(files.length()).append(").\n");
                                for (int i = 0; i < files.length(); i++) {
                                    JSONObject file = files.getJSONObject(i);
                                    report.append("\nالملف: ").append(file.getString("filename"))
                                            .append("\nالمسار: ").append(file.getString("path"))
                                            .append("\nالحجم: ").append(file.getInt("bytes")).append(" بايت")
                                            .append("\nالمحتوى المقروء:\n").append(file.getString("content")).append("\n");
                                }
                                verified = report.toString();
                                if (!store.setExecutionResult(task.id, true, verified))
                                    throw new IllegalStateException("تعذر حفظ نتيجة المهمة.");
                            }
                            runOnUiThread(() -> {
                                if (!task.id.equals(activeExecutionTaskId)) return;
                                activeExecutionTaskId = null;
                                aiReplyText.setText(verified);
                                renderTasks();
                                showMessage("اكتملت المهمة بعد التحقق", verified);
                            });
                        } catch (Exception error) {
                            String message = error.getMessage() == null ? "فشل تنفيذ الملفات" : error.getMessage();
                            store.setExecutionResult(task.id, false, "فشل التنفيذ: " + message);
                            runOnUiThread(() -> {
                                if (!task.id.equals(activeExecutionTaskId)) return;
                                activeExecutionTaskId = null;
                                aiReplyText.setText("فشل التنفيذ: " + message);
                                renderTasks();
                                showMessage("لم تكتمل المهمة", message);
                            });
                        }
                    });
                })
                .setNegativeButton("إلغاء", (dialog, which) -> {
                    activeExecutionTaskId = null;
                    aiReplyText.setText("أُلغي تنفيذ المهمة دون كتابة ملفات.");
                })
                .show();
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

    private void showMessage(String title, String message) {
        new AlertDialog.Builder(this)
                .setTitle(title)
                .setMessage(message)
                .setPositiveButton("إغلاق", null)
                .show();
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
            taskTitle.setMaxLines(2);
            taskTitle.setEllipsize(android.text.TextUtils.TruncateAt.END);
            if (task.done) taskTitle.setPaintFlags(taskTitle.getPaintFlags() | 16);
            row.addView(taskTitle, new LinearLayout.LayoutParams(0, -2, 1));

            Button execute = smallButton(task.done ? "إعادة" : "تنفيذ", task.done ? Color.rgb(75, 91, 111) : GREEN);
            row.addView(execute, new LinearLayout.LayoutParams(dp(66), dp(38)));
            execute.setOnClickListener(v -> executeTaskWithLocalAi(task));

            Button delete = smallButton("حذف", Color.rgb(132, 61, 65));
            delete.setEnabled(!task.id.equals(activeExecutionTaskId));
            LinearLayout.LayoutParams del = new LinearLayout.LayoutParams(dp(62), dp(38));
            del.rightMargin = dp(6);
            row.addView(delete, del);
            delete.setOnClickListener(v -> {
                store.delete(task.id);
                renderTasks();
            });

            card.addView(row, matchWrap());
            if (!task.description.equals(task.title)) {
                TextView description = text(task.description, 12, MUTED, false);
                description.setMaxLines(3);
                description.setEllipsize(android.text.TextUtils.TruncateAt.END);
                LinearLayout.LayoutParams descriptionLp = matchWrap(); descriptionLp.topMargin = dp(5);
                card.addView(description, descriptionLp);
            }
            if (task.result != null && !task.result.isEmpty()) {
                TextView result = text(task.result, 12, task.done ? Color.rgb(130, 220, 185) : MUTED, false);
                LinearLayout.LayoutParams resultLp = matchWrap(); resultLp.topMargin = dp(8);
                card.addView(result, resultLp);
            }
            LinearLayout.LayoutParams cp = matchWrap(); cp.topMargin = dp(8);
            taskList.addView(card, cp);
        }
    }

    private void showAddTaskDialog() {
        LinearLayout fields = new LinearLayout(this);
        fields.setOrientation(LinearLayout.VERTICAL);
        fields.setPadding(dp(8), dp(4), dp(8), dp(4));
        EditText titleInput = new EditText(this);
        titleInput.setSingleLine(true);
        titleInput.setFilters(new InputFilter[]{new InputFilter.LengthFilter(AgentTaskStore.MAX_TITLE_CHARS)});
        titleInput.setTextSize(16);
        titleInput.setHint("عنوان مختصر (80 حرفاً كحد أقصى)");
        titleInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        titleInput.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);
        EditText descriptionInput = new EditText(this);
        descriptionInput.setSingleLine(false);
        descriptionInput.setMinLines(4);
        descriptionInput.setTextSize(15);
        descriptionInput.setHint("التعليمات والتفاصيل الكاملة — لا تختصرها");
        descriptionInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        descriptionInput.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);
        fields.addView(titleInput, matchWrap());
        fields.addView(descriptionInput, matchWrap());
        new AlertDialog.Builder(this).setTitle("مهمة جديدة").setView(fields)
                .setNegativeButton("إلغاء", null)
                .setPositiveButton("حفظ", (dialog, which) -> {
                    try {
                        store.add(titleInput.getText().toString(), descriptionInput.getText().toString());
                        renderTasks();
                    } catch (IllegalArgumentException | IllegalStateException error) {
                        new AlertDialog.Builder(this).setMessage(error.getMessage()).setPositiveButton("حسناً", null).show();
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
