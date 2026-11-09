package com.islamdetector.aipro;

import android.app.Activity;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.tts.TextToSpeech;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public class MainActivity extends Activity {
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final AtomicBoolean requestInFlight = new AtomicBoolean(false);

    private LinearLayout root;
    private LinearLayout content;
    private TextView connectionView;
    private TextView physicsView;
    private TextView aiView;
    private TextView judgeView;
    private TextView depthView;
    private TextView calibrationView;
    private TextView rawView;
    private TextView sampleCountView;
    private TextView mapInfoView;
    private EditText hostInput;
    private GroundMapView groundMap;

    private ExperimentStore experimentStore;
    private TextToSpeech speech;
    private boolean speechReady = false;
    private boolean audioEnabled = true;
    private boolean periodicVoiceEnabled = true;
    private float speechVolume = 0.75f;
    private float mapZoom = 1.0f;
    private boolean mapAutomaticScale = true;
    private long lastPeriodicSpeech = 0;

    private boolean connected = false;
    private boolean running = false;
    private boolean destroyed = false;
    private int activeScreen = 0;
    private String activeBase = "http://192.168.4.1";
    private String hostAddress = "192.168.4.1";
    private String lastAnnouncedState = "";
    private String physicsText = "بانتظار بيانات القياس";
    private String aiText = "محرك LiteRT ينتظر النموذج المدرّب والبيانات الحقيقية";
    private String judgeText = "غير حاسم — لا توجد مخرجات مستقلة كافية";
    private String depthText = "العمق: غير متاح حتى تتوفر معايرة ميدانية";
    private String calibrationText = "المعايرة: لا توجد بيانات";
    private String rawText = "بانتظار الاتصال بلوحة ESP32";
    private long latestSampleId = -1;
    private long lastReconnectAttempt = 0;
    private String lastSavedRaw = "";

    private final Runnable ticker = new Runnable() {
        @Override public void run() {
            if (destroyed) return;
            if (connected) pollStatus();
            else reconnectIfDue();
            long now = System.currentTimeMillis();
            if (running && audioEnabled && periodicVoiceEnabled &&
                    now - lastPeriodicSpeech >= 30000) {
                lastPeriodicSpeech = now;
                speakNow("المسح مستمر، حافظ على حركة ثابتة للملف");
            }
            ui.postDelayed(this, 2000);
        }
    };

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(0xff071321);
        getWindow().setNavigationBarColor(0xff071321);
        experimentStore = new ExperimentStore(this);
        audioEnabled = getPreferences(0).getBoolean("audio_enabled", true);
        speechVolume = getPreferences(0).getFloat("speech_volume", 0.75f);
        periodicVoiceEnabled = getPreferences(0).getBoolean("periodic_voice", true);
        hostAddress = getPreferences(0).getString("host", "192.168.4.1");
        activeBase = normalizeHost(hostAddress);
        initializeSpeech();
        buildShell();
        ui.postDelayed(ticker, 1000);
    }

    private void initializeSpeech() {
        speech = new TextToSpeech(this, status -> {
            if (status == TextToSpeech.SUCCESS) {
                int result = speech.setLanguage(new Locale("ar"));
                speechReady = result != TextToSpeech.LANG_MISSING_DATA
                        && result != TextToSpeech.LANG_NOT_SUPPORTED;
            }
        });
    }

    private void buildShell() {
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(0xff071321);
        root.setPadding(dp(14), dp(12), dp(14), dp(8));

        TextView title = text("ISLAM DETECTOR", 23, Color.WHITE, true);
        title.setGravity(Gravity.CENTER);
        root.addView(title, match());

        TextView subtitle = text("ULTIMATE EDITION  •  نظام الكشف والتحليل", 12,
                0xff9bb4c9, false);
        subtitle.setGravity(Gravity.CENTER);
        add(root, subtitle, 3);

        LinearLayout statusCard = card();
        connectionView = text("● غير متصل بلوحة ESP32", 13, 0xffffc477, true);
        statusCard.addView(connectionView, match());
        add(root, statusCard, 10);

        content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f);
        cp.topMargin = dp(8);
        root.addView(content, cp);

        LinearLayout navigation = new LinearLayout(this);
        navigation.setOrientation(LinearLayout.HORIZONTAL);
        Button detectionTab = button("الكشف والتحكم", 0xff126c68);
        Button mapTab = button("الخريطة ثلاثية الأبعاد", 0xff294765);
        navigation.addView(detectionTab, new LinearLayout.LayoutParams(0, dp(48), 1f));
        LinearLayout.LayoutParams mp = new LinearLayout.LayoutParams(0, dp(48), 1f);
        mp.leftMargin = dp(7);
        navigation.addView(mapTab, mp);
        detectionTab.setOnClickListener(v -> showScreen(0));
        mapTab.setOnClickListener(v -> showScreen(1));
        add(root, navigation, 8);

        setContentView(root);
        showScreen(0);
    }

    private void showScreen(int screen) {
        activeScreen = screen;
        content.removeAllViews();
        if (screen == 0) renderDetectionScreen();
        else renderMapScreen();
    }

    private void renderDetectionScreen() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(0, dp(2), 0, dp(14));
        scroll.addView(page);
        content.addView(scroll, match());

        add(page, text("مركز الكشف والتحكم", 19, Color.WHITE, true), 3);

        LinearLayout network = card();
        hostInput = new EditText(this);
        hostInput.setSingleLine(true);
        hostInput.setText(hostAddress);
        hostInput.setTextColor(Color.WHITE);
        hostInput.setHintTextColor(0xff8ca4ba);
        hostInput.setHint("عنوان لوحة ESP32 — 192.168.4.1");
        hostInput.setTextSize(14);
        hostInput.setBackground(background(0xff1a2d43));
        network.addView(hostInput, match());

        Button connectButton = button("اتصال / إعادة اتصال", 0xff147b70);
        add(network, connectButton, 8);
        connectButton.setOnClickListener(v -> connectManually());
        add(page, network, 9);

        add(page, text("نتائج التحليل المستقلة", 17, Color.WHITE, true), 15);
        physicsView = engineCard(page, "المحرك الأول • الفيزيائي والرياضي", physicsText);
        aiView = engineCard(page, "المحرك الثاني • الذكاء الاصطناعي المحلي", aiText);
        judgeView = engineCard(page, "المحرك الثالث • المقارنة والتحكيم النهائي", judgeText);

        add(page, text("العمق والمعايرة", 17, Color.WHITE, true), 12);
        LinearLayout depthCard = card();
        depthView = text(depthText, 14, 0xffe7d4a4, true);
        calibrationView = text(calibrationText, 13, 0xff8bd8c6, false);
        depthCard.addView(depthView, match());
        add(depthCard, calibrationView, 8);
        add(page, depthCard, 8);

        LinearLayout commands = new LinearLayout(this);
        Button startButton = button(running ? "إيقاف الكشف" : "بدء الكشف", 0xff16845f);
        Button calibrateButton = button("معايرة التربة", 0xff315b91);
        commands.addView(startButton, new LinearLayout.LayoutParams(0, dp(48), 1f));
        LinearLayout.LayoutParams calParams = new LinearLayout.LayoutParams(0, dp(48), 1f);
        calParams.leftMargin = dp(7);
        commands.addView(calibrateButton, calParams);
        add(page, commands, 9);
        startButton.setEnabled(connected);
        calibrateButton.setEnabled(connected);
        startButton.setOnClickListener(v -> sendCommand(running ? "stop" : "start"));
        calibrateButton.setOnClickListener(v -> sendCommand("calibrate"));

        add(page, text("الصوت من الهاتف", 17, Color.WHITE, true), 15);
        LinearLayout audioCard = card();
        CheckBox audioSwitch = new CheckBox(this);
        audioSwitch.setText("تشغيل التنبيهات الصوتية العربية");
        audioSwitch.setTextColor(Color.WHITE);
        audioSwitch.setTextSize(14);
        audioSwitch.setButtonTintList(android.content.res.ColorStateList.valueOf(0xff70d6c3));
        audioSwitch.setChecked(audioEnabled);
        audioCard.addView(audioSwitch, match());
        audioSwitch.setOnCheckedChangeListener((button, checked) -> {
            audioEnabled = checked;
            getPreferences(0).edit().putBoolean("audio_enabled", checked).apply();
            if (!checked && speech != null) speech.stop();
            else if (checked) speak("تم تشغيل التنبيهات الصوتية");
        });

        TextView volumeLabel = text("مستوى صوت التنبيهات: " +
                Math.round(speechVolume * 100) + "%", 12, 0xffb8c9d9, false);
        add(audioCard, volumeLabel, 6);
        SeekBar volume = new SeekBar(this);
        volume.setMax(100);
        volume.setProgress(Math.round(speechVolume * 100));
        volume.setProgressTintList(android.content.res.ColorStateList.valueOf(0xff53b9a8));
        audioCard.addView(volume, match());
        CheckBox periodic = new CheckBox(this);
        periodic.setText("تذكير صوتي دوري أثناء المسح كل 30 ثانية");
        periodic.setTextColor(0xffd4e1eb);
        periodic.setTextSize(12);
        periodic.setChecked(periodicVoiceEnabled);
        audioCard.addView(periodic, match());
        periodic.setOnCheckedChangeListener((button, checked) -> {
            periodicVoiceEnabled = checked;
            getPreferences(0).edit().putBoolean("periodic_voice", checked).apply();
        });
        volume.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar bar, int value, boolean user) {
                speechVolume = value / 100f;
                volumeLabel.setText("مستوى صوت التنبيهات: " + value + "%");
                getPreferences(0).edit().putFloat("speech_volume", speechVolume).apply();
            }
            @Override public void onStartTrackingTouch(SeekBar bar) { }
            @Override public void onStopTrackingTouch(SeekBar bar) { }
        });
        add(page, audioCard, 8);

        add(page, text("سجل التجارب المحلي", 17, Color.WHITE, true), 14);
        LinearLayout history = card();
        sampleCountView = text("العينات المحفوظة: " + experimentStore.countSamples(),
                13, 0xffb8c9d9, false);
        history.addView(sampleCountView, match());
        rawView = text(rawText, 11, 0xffc0cfdd, false);
        rawView.setTextIsSelectable(true);
        add(history, rawView, 8);
        add(page, history, 8);

        add(page, text("تأكيد النتيجة بعد التحقق الميداني", 16, Color.WHITE, true), 14);
        add(page, text("يُحفظ التأكيد مع القراءة، ولا يُدرّب النموذج تلقائياً قبل مراجعة العينة واختبارها.", 12,
                0xffa9bdcf, false), 5);
        LinearLayout feedback = new LinearLayout(this);
        Button yes = button("هدف مؤكد", 0xff236c54);
        Button no = button("لا يوجد هدف", 0xff795044);
        Button unknown = button("غير حاسم", 0xff53657a);
        feedback.addView(yes, new LinearLayout.LayoutParams(0, dp(46), 1f));
        feedback.addView(no, new LinearLayout.LayoutParams(0, dp(46), 1f));
        feedback.addView(unknown, new LinearLayout.LayoutParams(0, dp(46), 1f));
        add(page, feedback, 8);
        yes.setOnClickListener(v -> saveFeedback("confirmed"));
        no.setOnClickListener(v -> saveFeedback("no_target"));
        unknown.setOnClickListener(v -> saveFeedback("inconclusive"));
    }

    private void renderMapScreen() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(0, dp(2), 0, dp(14));
        scroll.addView(page);
        content.addView(scroll, match());

        add(page, text("الخريطة ثلاثية الأبعاد", 19, Color.WHITE, true), 3);
        add(page, text("واجهة مستقلة؛ يستمر القياس والتحليل حتى عند الانتقال إليها.", 12,
                0xffa9bdcf, false), 5);

        LinearLayout mapCard = card();
        mapInfoView = text("الخريطة تنتظر بيانات مسح مكانية حقيقية مرتبطة بحركة الملف. لن نعرض معادن أو فجوات افتراضية.",
                13, 0xffffd99b, true);
        mapCard.addView(mapInfoView, match());
        groundMap = new GroundMapView(this);
        groundMap.setScaleState(mapZoom, mapAutomaticScale);
        LinearLayout.LayoutParams mapParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(340));
        mapParams.topMargin = dp(10);
        mapCard.addView(groundMap, mapParams);
        add(page, mapCard, 10);

        LinearLayout scaleControls = new LinearLayout(this);
        Button auto = button("مقياس تلقائي", 0xff126c68);
        Button minus = button("تصغير −", 0xff294765);
        Button plus = button("تكبير +", 0xff294765);
        scaleControls.addView(auto, new LinearLayout.LayoutParams(0, dp(46), 1f));
        scaleControls.addView(minus, new LinearLayout.LayoutParams(0, dp(46), 1f));
        scaleControls.addView(plus, new LinearLayout.LayoutParams(0, dp(46), 1f));
        add(page, scaleControls, 8);
        auto.setOnClickListener(v -> {
            mapAutomaticScale = true;
            mapZoom = 1.0f;
            groundMap.useAutomaticScale();
            mapInfoView.setText("المقياس تلقائي. الخريطة ما زالت تنتظر قياسات مكانية حقيقية.");
        });
        minus.setOnClickListener(v -> {
            mapAutomaticScale = false;
            mapZoom = Math.max(0.55f, mapZoom / 1.2f);
            groundMap.setScaleState(mapZoom, false);
        });
        plus.setOnClickListener(v -> {
            mapAutomaticScale = false;
            mapZoom = Math.min(2.5f, mapZoom * 1.2f);
            groundMap.setScaleState(mapZoom, false);
        });

        LinearLayout legend = card();
        add(legend, text("قواعد عرض الخريطة", 15, Color.WHITE, true), 1);
        add(legend, text("• الاحتفاظ بتاريخ كل منطقة ممسوحة.\n" +
                "• إضافة المناطق الجديدة دون محو المناطق السابقة.\n" +
                "• إظهار درجة الثقة ونقص البيانات.\n" +
                "• التكبير لا يضيف دقة غير موجودة في القياسات.\n" +
                "• لا GPS ولا صور ولا تحديد موقع جغرافي.", 12, 0xffb8c9d9, false), 8);
        add(page, legend, 10);
    }

    private TextView engineCard(LinearLayout parent, String heading, String initial) {
        LinearLayout panel = card();
        panel.addView(text(heading, 14, 0xff8dd9d0, true), match());
        TextView value = text(initial, 12, 0xffd2deeb, false);
        add(panel, value, 7);
        add(parent, panel, 8);
        return value;
    }

    private void connectManually() {
        if (hostInput != null) hostAddress = hostInput.getText().toString().trim();
        if (hostAddress.isEmpty()) hostAddress = "192.168.4.1";
        activeBase = normalizeHost(hostAddress);
        getPreferences(0).edit().putString("host", hostAddress).apply();
        connected = false;
        updateConnection("جارٍ الاتصال بلوحة ESP32...", 0xffffd080);
        requestStatus(true);
    }

    private String normalizeHost(String value) {
        String host = value == null ? "" : value.trim();
        if (host.isEmpty()) host = "192.168.4.1";
        if (!host.startsWith("http://") && !host.startsWith("https://")) host = "http://" + host;
        while (host.endsWith("/")) host = host.substring(0, host.length() - 1);
        return host;
    }

    private void reconnectIfDue() {
        long now = System.currentTimeMillis();
        if (now - lastReconnectAttempt < 5000) return;
        lastReconnectAttempt = now;
        requestStatus(false);
    }

    private void pollStatus() {
        requestStatus(false);
    }

    private void requestStatus(boolean manual) {
        if (!requestInFlight.compareAndSet(false, true)) return;
        final String url = activeBase + "/status";
        io.execute(() -> {
            try {
                JSONObject result = request(url, "GET", null);
                ui.post(() -> {
                    boolean wasConnected = connected;
                    connected = true;
                    updateConnection("● متصل بلوحة ESP32", 0xff69dfad);
                    applyReading(result);
                    if (!wasConnected) speak("تم الاتصال بلوحة الجهاز");
                });
            } catch (Exception error) {
                ui.post(() -> {
                    boolean wasConnected = connected;
                    connected = false;
                    updateConnection("● غير متصل — إعادة المحاولة تلقائياً", 0xffffb46e);
                    if (wasConnected || manual) speak("انقطع الاتصال بلوحة الجهاز");
                });
            } finally {
                requestInFlight.set(false);
            }
        });
    }

    private JSONObject request(String address, String method, JSONObject body) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(address).openConnection();
        try {
            connection.setRequestMethod(method);
            connection.setConnectTimeout(3000);
            connection.setReadTimeout(3000);
            connection.setUseCaches(false);
            if (body != null) {
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                try (OutputStream output = connection.getOutputStream()) {
                    output.write(body.toString().getBytes(StandardCharsets.UTF_8));
                }
            }
            int code = connection.getResponseCode();
            InputStream stream = code >= 200 && code < 300
                    ? connection.getInputStream() : connection.getErrorStream();
            String response = "";
            if (stream != null) {
                try (InputStream input = stream; ByteArrayOutputStream bytes = new ByteArrayOutputStream()) {
                    byte[] buffer = new byte[2048];
                    int count;
                    while ((count = input.read(buffer)) != -1) bytes.write(buffer, 0, count);
                    response = bytes.toString("UTF-8");
                }
            }
            if (code < 200 || code >= 300) throw new IOException("HTTP " + code);
            return new JSONObject(response);
        } finally {
            connection.disconnect();
        }
    }

    private void applyReading(JSONObject response) {
        JSONObject data = response.optJSONObject("data");
        if (data == null) data = response;
        JSONArray windows = data.optJSONArray("windows");
        double[] values = readWindows(windows);
        double regularity = regularityIndicator(values);

        physicsText = values.length >= 3
                ? "تم استلام " + values.length + " نوافذ. مؤشر انتظام القياسات: " +
                  String.format(Locale.US, "%.1f", regularity) + " / 100. هذا ليس احتمال وجود معدن."
                : "بيانات غير كافية: نحتاج 3 نوافذ زمنية صالحة على الأقل.";

        aiText = "LiteRT: النموذج المدرّب غير مدمج بعد؛ لا يوجد تصنيف معدن أو احتمال موثوق حالياً.";
        judgeText = values.length >= 3
                ? "التحكيم: غير حاسم حتى تتوفر نتيجة مستقلة من نموذج مختبر."
                : "التحكيم: غير حاسم — القياسات الحالية غير كافية.";

        if (data.has("depth_cm") && !data.isNull("depth_cm")) {
            depthText = "العمق المرسل من ESP32: " + data.optDouble("depth_cm") +
                    " سم — يحتاج تحققاً ومعايرة ميدانية.";
        } else {
            depthText = "العمق: غير متاح؛ لا نخمن العمق من قوة إشارة واحدة.";
        }

        boolean calibrated = data.optBoolean("calibrated", false);
        calibrationText = "المعايرة: " + (calibrated ? "مكتملة حسب بيانات ESP32" : "غير مؤكدة") +
                (data.has("calibration_percent")
                        ? " • " + data.optString("calibration_percent") + "%"
                        : " • لا توجد نسبة معايرة");

        rawText = response.toString();
        if (rawText.length() > 2200) rawText = rawText.substring(0, 2200) + "…";

        Double depth = data.has("depth_cm") && !data.isNull("depth_cm")
                ? data.optDouble("depth_cm") : null;
        try {
            latestSampleId = experimentStore.saveSampleIfNew(
                    response.toString(), values.length, depth, calibrated);
        } catch (Exception ignored) {
            latestSampleId = -1;
        }
        refreshDetectionViews();
    }

    private void refreshDetectionViews() {
        if (physicsView != null) physicsView.setText(physicsText);
        if (aiView != null) aiView.setText(aiText);
        if (judgeView != null) judgeView.setText(judgeText);
        if (depthView != null) depthView.setText(depthText);
        if (calibrationView != null) calibrationView.setText(calibrationText);
        if (rawView != null) rawView.setText(rawText);
        if (sampleCountView != null) {
            sampleCountView.setText("العينات المحفوظة محلياً: " + experimentStore.countSamples());
        }
    }

    private double[] readWindows(JSONArray array) {
        if (array == null) return new double[0];
        double[] values = new double[array.length()];
        int count = 0;
        for (int i = 0; i < array.length(); i++) {
            Object item = array.opt(i);
            double value = Double.NaN;
            if (item instanceof Number) value = ((Number) item).doubleValue();
            else if (item instanceof JSONObject) {
                JSONObject object = (JSONObject) item;
                String[] keys = {"value", "amplitude", "signal", "sample"};
                for (String key : keys) {
                    if (object.opt(key) instanceof Number) {
                        value = object.optDouble(key);
                        break;
                    }
                }
            }
            if (!Double.isNaN(value) && !Double.isInfinite(value)) values[count++] = value;
        }
        return Arrays.copyOf(values, count);
    }

    private double regularityIndicator(double[] values) {
        if (values.length < 3) return 0;
        double mean = 0;
        for (double value : values) mean += value;
        mean /= values.length;
        double variance = 0;
        for (double value : values) variance += (value - mean) * (value - mean);
        variance /= values.length;
        double coefficient = Math.sqrt(variance) / (Math.abs(mean) + 1e-9);
        return 100.0 / (1.0 + coefficient);
    }

    private void sendCommand(String command) {
        if (!connected) {
            Toast.makeText(this, "اتصل بلوحة ESP32 أولاً", Toast.LENGTH_SHORT).show();
            return;
        }
        final String url = activeBase + "/control";
        io.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("command", command);
                request(url, "POST", body);
                ui.post(() -> {
                    if ("start".equals(command)) {
                        running = true;
                        speak("بدأ المسح");
                    } else if ("stop".equals(command)) {
                        running = false;
                        speak("توقف المسح");
                    } else {
                        speak("بدأت معايرة التربة");
                    }
                    if (activeScreen == 0) showScreen(0);
                });
            } catch (Exception error) {
                ui.post(() -> Toast.makeText(this, "تعذر إرسال الأمر إلى الجهاز",
                        Toast.LENGTH_SHORT).show());
            }
        });
    }

    private void saveFeedback(String feedback) {
        if (latestSampleId <= 0) {
            Toast.makeText(this, "لا توجد عينة محفوظة لتأكيدها", Toast.LENGTH_SHORT).show();
            return;
        }
        experimentStore.saveFeedback(latestSampleId, feedback);
        Toast.makeText(this, "حُفظ التأكيد مع العينة؛ لن يُدرّب النموذج تلقائياً",
                Toast.LENGTH_LONG).show();
    }

    private void updateConnection(String message, int color) {
        if (connectionView != null) {
            connectionView.setText(message);
            connectionView.setTextColor(color);
        }
    }

    private void speak(String message) {
        if (message.equals(lastAnnouncedState)) return;
        lastAnnouncedState = message;
        speakNow(message);
    }

    private void speakNow(String message) {
        if (!audioEnabled || speech == null || !speechReady || speechVolume <= 0.01f) return;
        Bundle parameters = new Bundle();
        parameters.putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME, speechVolume);
        speech.speak(message, TextToSpeech.QUEUE_FLUSH, parameters, "islam-detector-status");
    }

    private int dp(float value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private LinearLayout.LayoutParams match() {
        return new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
    }

    private void add(LinearLayout parent, View child, int topMargin) {
        LinearLayout.LayoutParams params = match();
        params.topMargin = dp(topMargin);
        parent.addView(child, params);
    }

    private GradientDrawable background(int color) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(dp(14));
        drawable.setStroke(dp(1), 0xff2b435e);
        return drawable;
    }

    private LinearLayout card() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(dp(13), dp(12), dp(13), dp(12));
        layout.setBackground(background(0xff122238));
        return layout;
    }

    private TextView text(String value, int size, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return view;
    }

    private Button button(String label, int color) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextColor(Color.WHITE);
        button.setAllCaps(false);
        button.setTextSize(12);
        button.setBackground(background(color));
        return button;
    }

    @Override
    protected void onDestroy() {
        destroyed = true;
        ui.removeCallbacksAndMessages(null);
        io.shutdownNow();
        if (speech != null) {
            speech.stop();
            speech.shutdown();
        }
        if (experimentStore != null) experimentStore.close();
        super.onDestroy();
    }
}
