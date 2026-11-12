package com.islamdetector.app;

import android.app.Activity;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.content.*;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.view.Gravity;
import android.view.View;
import android.widget.*;
import org.json.JSONObject;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public class MainActivity extends Activity {
    private static final String PREFS = "islam_detector_settings";
    private static final String DEFAULT_HOST = "192.168.4.1";
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService network = Executors.newSingleThreadExecutor();
    private final AtomicBoolean requestRunning = new AtomicBoolean(false);
    private final SimpleDateFormat timeFormat = new SimpleDateFormat("HH:mm:ss", Locale.getDefault());

    private EditText hostInput;
    private TextView connectionText, signalText, confidenceText, depthText, calibrationText, lastUpdateText, historyText;
    private Button connectButton, detectButton, calibrateButton;
    private boolean connected = false;
    private boolean detecting = false;
    private boolean activityVisible = false;
    private volatile boolean destroyed = false;
    private volatile String activeHost = DEFAULT_HOST;
    private long lastSavedAt = 0;
    private DetectorDb db;

    private final Runnable pollTask = new Runnable() {
        @Override public void run() {
            if (!activityVisible || !connected) return;
            fetchStatus();
            if (activityVisible && connected) handler.postDelayed(this, 2000);
        }
    };

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.rgb(8, 16, 29));
        getWindow().setNavigationBarColor(Color.rgb(8, 16, 29));
        db = new DetectorDb(this);
        buildScreen();
        loadSettings();
        activeHost = baseUrl();
        refreshHistory();
    }

    private void buildScreen() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.rgb(8, 16, 29));
        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(dp(18), dp(18), dp(18), dp(26));
        page.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);
        scroll.addView(page);

        TextView brand = text("ISLAM DETECTOR", 25, Color.WHITE, true);
        brand.setGravity(Gravity.CENTER);
        page.addView(brand, matchWrap());
        TextView subtitle = text("المستكشف الذكي • نظام الكشف النبضي PI", 14, Color.rgb(150, 174, 199), false);
        subtitle.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams subLp = matchWrap(); subLp.topMargin = dp(5);
        page.addView(subtitle, subLp);

        LinearLayout statusCard = card();
        connectionText = text("● غير متصل بالجهاز", 16, Color.rgb(255, 190, 90), true);
        statusCard.addView(connectionText, matchWrap());
        lastUpdateText = text("لم تصل أي قراءة بعد", 12, Color.LTGRAY, false);
        LinearLayout.LayoutParams upd = matchWrap(); upd.topMargin = dp(7);
        statusCard.addView(lastUpdateText, upd);
        addCard(page, statusCard);

        TextView connectionLabel = text("عنوان الجهاز عبر Wi‑Fi", 14, Color.WHITE, true);
        LinearLayout.LayoutParams labelLp = matchWrap(); labelLp.topMargin = dp(18);
        page.addView(connectionLabel, labelLp);
        LinearLayout connectionRow = new LinearLayout(this);
        connectionRow.setOrientation(LinearLayout.HORIZONTAL);
        hostInput = new EditText(this);
        hostInput.setSingleLine(true);
        hostInput.setTextColor(Color.WHITE);
        hostInput.setHintTextColor(Color.rgb(140,155,175));
        hostInput.setHint("مثال: 192.168.4.1");
        hostInput.setTextSize(15);
        hostInput.setPadding(dp(12), 0, dp(12), 0);
        hostInput.setInputType( android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_URI);
        hostInput.setBackground(round(Color.rgb(23, 37, 56), 12, Color.rgb(55,75,99)));
        LinearLayout.LayoutParams inputLp = new LinearLayout.LayoutParams(0, dp(50), 1);
        connectionRow.addView(hostInput, inputLp);
        connectButton = button("اتصال", Color.rgb(22, 125, 110));
        LinearLayout.LayoutParams connectLp = new LinearLayout.LayoutParams(dp(94), dp(50));
        connectLp.rightMargin = dp(8);
        connectionRow.addView(connectButton, connectLp);
        LinearLayout.LayoutParams rowLp = matchWrap(); rowLp.topMargin = dp(8);
        page.addView(connectionRow, rowLp);
        connectButton.setOnClickListener(v -> connectToDevice());

        TextView readingsTitle = text("قراءات الكشف", 18, Color.WHITE, true);
        LinearLayout.LayoutParams rt = matchWrap(); rt.topMargin = dp(22);
        page.addView(readingsTitle, rt);
        LinearLayout readings = new LinearLayout(this);
        readings.setOrientation(LinearLayout.HORIZONTAL);
        signalText = text("--", 27, Color.WHITE, true);
        confidenceText = text("--", 27, Color.WHITE, true);
        depthText = text("--", 27, Color.WHITE, true);
        addMetric(readings, "قوة الإشارة", signalText);
        addMetric(readings, "الثقة", confidenceText);
        addMetric(readings, "العمق", depthText);
        LinearLayout.LayoutParams metricLp = matchWrap(); metricLp.topMargin = dp(9);
        page.addView(readings, metricLp);

        LinearLayout calibrationCard = card();
        calibrationText = text("المعايرة: لم تبدأ بعد", 15, Color.rgb(130, 205, 190), true);
        calibrationCard.addView(calibrationText, matchWrap());
        LinearLayout.LayoutParams calLp = matchWrap(); calLp.topMargin = dp(12);
        page.addView(calibrationCard, calLp);

        detectButton = button("بدء الكشف", Color.rgb(20, 112, 91));
        LinearLayout.LayoutParams detectLp = matchWrap(); detectLp.height = dp(54); detectLp.topMargin = dp(16);
        page.addView(detectButton, detectLp);
        detectButton.setOnClickListener(v -> sendControl(detecting ? "stop" : "start"));
        detectButton.setEnabled(false);

        calibrateButton = button("معايرة التربة", Color.rgb(45, 75, 112));
        LinearLayout.LayoutParams calButtonLp = matchWrap(); calButtonLp.height = dp(50); calButtonLp.topMargin = dp(9);
        page.addView(calibrateButton, calButtonLp);
        calibrateButton.setEnabled(false);
        calibrateButton.setOnClickListener(v -> sendControl("calibrate"));

        TextView historyTitle = text("سجل القياسات المحفوظة", 18, Color.WHITE, true);
        LinearLayout.LayoutParams ht = matchWrap(); ht.topMargin = dp(24);
        page.addView(historyTitle, ht);
        LinearLayout historyCard = card();
        historyText = text("لا توجد قياسات محفوظة بعد", 13, Color.rgb(205, 216, 229), false);
        historyText.setGravity(Gravity.RIGHT);
        historyCard.addView(historyText, matchWrap());
        LinearLayout.LayoutParams hc = matchWrap(); hc.topMargin = dp(9);
        page.addView(historyCard, hc);

        Button export = button("تصدير سجل القياسات", Color.rgb(61, 76, 96));
        LinearLayout.LayoutParams ex = matchWrap(); ex.height = dp(48); ex.topMargin = dp(9);
        page.addView(export, ex);
        export.setOnClickListener(v -> exportHistory());

        TextView foot = text("البيانات محفوظة على الهاتف • لا يوجد اتصال حتى يشتغل ESP32", 11, Color.rgb(125, 145, 166), false);
        foot.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams fp = matchWrap(); fp.topMargin = dp(18);
        page.addView(foot, fp);

        setContentView(scroll);
    }

    private void addMetric(LinearLayout parent, String label, TextView value) {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER);
        box.setPadding(dp(5), dp(14), dp(5), dp(14));
        box.setBackground(round(Color.rgb(20, 33, 51), 14, Color.rgb(42, 61, 83)));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, dp(100), 1);
        lp.leftMargin = dp(4); lp.rightMargin = dp(4);
        parent.addView(box, lp);
        box.addView(value, matchWrap());
        value.setGravity(Gravity.CENTER);
        TextView caption = text(label, 12, Color.rgb(157, 178, 199), false);
        caption.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams cp = matchWrap(); cp.topMargin = dp(5);
        box.addView(caption, cp);
    }

    private LinearLayout card() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(15), dp(14), dp(15), dp(14));
        box.setBackground(round(Color.rgb(17, 29, 46), 16, Color.rgb(43, 62, 83)));
        return box;
    }
    private void addCard(LinearLayout parent, LinearLayout child) {
        LinearLayout.LayoutParams lp = matchWrap(); lp.topMargin = dp(18);
        parent.addView(child, lp);
    }
    private TextView text(String value, int size, int color, boolean bold) {
        TextView t = new TextView(this); t.setText(value); t.setTextSize(size);
        t.setTextColor(color); if (bold) t.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        t.setFontFeatureSettings("kern"); return t;
    }
    private Button button(String label, int color) {
        Button b = new Button(this); b.setText(label); b.setTextColor(Color.WHITE);
        b.setAllCaps(false); b.setTextSize(15); b.setBackground(round(color, 13, color));
        return b;
    }
    private GradientDrawable round(int color, int radius, int stroke) {
        GradientDrawable d = new GradientDrawable(); d.setColor(color); d.setCornerRadius(dp(radius));
        d.setStroke(dp(1), stroke); return d;
    }
    private int dp(float n) { return (int)(n * getResources().getDisplayMetrics().density + 0.5f); }
    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
    }

    private void loadSettings() {
        String host = getSharedPreferences(PREFS, MODE_PRIVATE).getString("host", DEFAULT_HOST);
        hostInput.setText(host);
    }
    private String baseUrl() {
        String host = hostInput.getText().toString().trim();
        if (host.isEmpty()) host = DEFAULT_HOST;
        if (!host.startsWith("http://") && !host.startsWith("https://")) host = "http://" + host;
        while (host.endsWith("/")) host = host.substring(0, host.length()-1);
        return host;
    }
    private void connectToDevice() {
        final String host = baseUrl();
        activeHost = host;
        getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString("host", host).apply();
        connectButton.setEnabled(false); connectionText.setText("● جارٍ الاتصال...");
        network.execute(() -> {
            try {
                JSONObject data = requestJson(host + "/status", "GET", null);
                runOnUiThread(() -> {
                    if (destroyed) return;
                    connected = true; connectButton.setEnabled(true); connectButton.setText("تحديث");
                    connectionText.setText("● متصل بالجهاز");
                    connectionText.setTextColor(Color.rgb(91, 220, 167));
                    detectButton.setEnabled(true); calibrateButton.setEnabled(true);
                    applyStatus(data);
                    handler.removeCallbacks(pollTask);
                    if (activityVisible) handler.post(pollTask);
                    toast("تم الاتصال بالجهاز");
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    if (destroyed) return;
                    connected = false; connectButton.setEnabled(true);
                    connectionText.setText("● تعذّر الاتصال — تحقق من Wi‑Fi والعنوان");
                    connectionText.setTextColor(Color.rgb(255, 170, 110));
                    detectButton.setEnabled(false); calibrateButton.setEnabled(false);
                    toast("لم نتمكن من قراءة /status");
                });
            }
        });
    }

    private void fetchStatus() {
        if (!requestRunning.compareAndSet(false, true)) return;
        final String host = activeHost;
        network.execute(() -> {
            try {
                JSONObject data = requestJson(host + "/status", "GET", null);
                runOnUiThread(() -> {
                    if (destroyed) return;
                    connected = true; connectionText.setText("● متصل بالجهاز");
                    connectionText.setTextColor(Color.rgb(91,220,167));
                    applyStatus(data);
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    if (destroyed) return;
                    connected = false; connectionText.setText("● انقطع الاتصال بالجهاز");
                    connectionText.setTextColor(Color.rgb(255,170,110));
                    detectButton.setEnabled(false); calibrateButton.setEnabled(false);
                });
            } finally { requestRunning.set(false); }
        });
    }

    private JSONObject requestJson(String address, String method, JSONObject body) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(address).openConnection();
        try {
            c.setRequestMethod(method); c.setConnectTimeout(2500); c.setReadTimeout(2500);
            c.setRequestProperty("Accept", "application/json");
            if (body != null) {
                c.setDoOutput(true); c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                try (OutputStream out = c.getOutputStream()) {
                    out.write(body.toString().getBytes(StandardCharsets.UTF_8));
                }
            }
            int code = c.getResponseCode();
            InputStream stream = code >= 200 && code < 300 ? c.getInputStream() : c.getErrorStream();
            String response;
            if (stream == null) {
                response = "{}";
            } else {
                try (InputStream in = stream) { response = readAll(in); }
            }
            if (code < 200 || code >= 300) throw new IOException("HTTP " + code + ": " + response);
            return new JSONObject(response);
        } finally {
            c.disconnect();
        }
    }
    private String readAll(InputStream in) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[2048]; int n;
        while ((n = in.read(buffer)) != -1) out.write(buffer, 0, n);
        return out.toString("UTF-8");
    }

    private void applyStatus(JSONObject root) {
        JSONObject data = root.optJSONObject("data");
        if (data == null) data = root;
        double signal = number(data, "signal", "raw", "amplitude");
        double confidence = number(data, "confidence", "confidence_percent");
        double depth = number(data, "depth_cm", "depth");
        signalText.setText(Double.isNaN(signal) ? "--" : format(signal));
        confidenceText.setText(Double.isNaN(confidence) ? "--" : format(confidence) + "%");
        depthText.setText(Double.isNaN(depth) ? "--" : format(depth) + " سم");
        boolean calibrated = data.optBoolean("calibrated", false);
        double calibration = number(data, "calibration_percent", "calibration");
        if (!Double.isNaN(calibration)) calibrationText.setText("معايرة التربة: " + format(calibration) + "%");
        else calibrationText.setText(calibrated ? "التربة مُعايرة" : "المعايرة: لم تؤكد بعد");
        String state = data.optString("state", data.optString("status", ""));
        if ("detecting".equalsIgnoreCase(state) || data.optBoolean("detecting", false)) {
            detecting = true; detectButton.setText("إيقاف الكشف");
        } else if ("stopped".equalsIgnoreCase(state) || "idle".equalsIgnoreCase(state)) {
            detecting = false; detectButton.setText("بدء الكشف");
        }
        lastUpdateText.setText("آخر تحديث: " + timeFormat.format(new Date()) +
                (data.has("device") ? " • " + data.optString("device") : ""));
        if (!Double.isNaN(signal) && System.currentTimeMillis() - lastSavedAt > 5000) {
            db.add(signal, confidence, depth, calibrated ? 1 : 0);
            lastSavedAt = System.currentTimeMillis(); refreshHistory();
        }
    }
    private double number(JSONObject o, String... keys) {
        for (String key : keys) if (o.has(key) && !o.isNull(key)) {
            Object v = o.opt(key);
            if (v instanceof Number) return ((Number)v).doubleValue();
            try { return Double.parseDouble(String.valueOf(v)); } catch (Exception ignored) {}
        }
        return Double.NaN;
    }
    private String format(double n) {
        if (Double.isNaN(n) || Double.isInfinite(n)) return "--";
        return String.format(Locale.getDefault(), "%.1f", n);
    }

    private void sendControl(String command) {
        if (!connected) { toast("اتصل بالجهاز أولاً"); return; }
        final String host = activeHost;
        detectButton.setEnabled(false); calibrateButton.setEnabled(false);
        network.execute(() -> {
            try {
                JSONObject body = new JSONObject(); body.put("command", command);
                requestJson(host + "/control", "POST", body);
                runOnUiThread(() -> {
                    if (destroyed) return;
                    if ("start".equals(command)) { detecting = true; detectButton.setText("إيقاف الكشف"); }
                    if ("stop".equals(command)) { detecting = false; detectButton.setText("بدء الكشف"); }
                    toast("تم إرسال الأمر: " + command);
                    detectButton.setEnabled(true); calibrateButton.setEnabled(true);
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    if (destroyed) return;
                    detectButton.setEnabled(true); calibrateButton.setEnabled(true);
                    toast("الجهاز لم يقبل الأمر. تحقق من إصدار ESP32");
                });
            }
        });
    }

    private void refreshHistory() {
        if (historyText == null) return;
        StringBuilder b = new StringBuilder();
        try (Cursor c = db.latest(8)) {
            if (!c.moveToFirst()) { historyText.setText("لا توجد قياسات محفوظة بعد"); return; }
            do {
                String date = new SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()).format(new Date(c.getLong(1)));
                b.append(date).append("  |  إشارة ").append(format(c.getDouble(2)));
                if (!c.isNull(3)) b.append("  |  ثقة ").append(format(c.getDouble(3))).append("%");
                if (!c.isNull(4)) b.append("  |  عمق ").append(format(c.getDouble(4))).append(" سم");
                b.append("\n");
            } while (c.moveToNext());
        }
        historyText.setText(b.toString().trim());
    }
    private void exportHistory() {
        String csv = db.exportCsv();
        if (csv.isEmpty()) { toast("السجل فارغ حالياً"); return; }
        Intent share = new Intent(Intent.ACTION_SEND); share.setType("text/csv");
        share.putExtra(Intent.EXTRA_SUBJECT, "سجل قياسات Islam Detector");
        share.putExtra(Intent.EXTRA_TEXT, csv);
        startActivity(Intent.createChooser(share, "تصدير سجل القياسات"));
    }
    private void toast(String message) {
        if (!destroyed) Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
    }

    @Override protected void onResume() {
        super.onResume();
        activityVisible = true;
        if (connected) {
            handler.removeCallbacks(pollTask);
            handler.post(pollTask);
        }
    }

    @Override protected void onPause() {
        activityVisible = false;
        handler.removeCallbacks(pollTask);
        super.onPause();
    }

    @Override protected void onDestroy() {
        destroyed = true;
        activityVisible = false;
        handler.removeCallbacksAndMessages(null);
        network.shutdownNow();
        if (db != null) db.close();
        super.onDestroy();
    }

    private static class DetectorDb extends SQLiteOpenHelper {
        DetectorDb(Context c) { super(c, "islam_detector.db", null, 1); }
        @Override public void onCreate(SQLiteDatabase db) {
            db.execSQL("CREATE TABLE readings (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp INTEGER NOT NULL, signal REAL NOT NULL, confidence REAL, depth REAL, calibrated INTEGER NOT NULL)");
            db.execSQL("CREATE INDEX idx_readings_time ON readings(timestamp DESC)");
        }
        @Override public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) { }
        void add(double signal, double confidence, double depth, int calibrated) {
            android.content.ContentValues v = new android.content.ContentValues();
            v.put("timestamp", System.currentTimeMillis()); v.put("signal", signal);
            if (!Double.isNaN(confidence)) v.put("confidence", confidence);
            if (!Double.isNaN(depth)) v.put("depth", depth);
            v.put("calibrated", calibrated); getWritableDatabase().insert("readings", null, v);
        }
        Cursor latest(int limit) {
            return getReadableDatabase().rawQuery("SELECT id,timestamp,signal,confidence,depth,calibrated FROM readings ORDER BY timestamp DESC LIMIT " + limit, null);
        }
        String exportCsv() {
            StringBuilder b = new StringBuilder("timestamp,signal,confidence_percent,depth_cm,calibrated\n");
            try (Cursor c = getReadableDatabase().rawQuery("SELECT timestamp,signal,confidence,depth,calibrated FROM readings ORDER BY timestamp ASC", null)) {
                while (c.moveToNext()) {
                    b.append(c.getLong(0)).append(',').append(c.getDouble(1)).append(',');
                    b.append(c.isNull(2) ? "" : c.getDouble(2)).append(',');
                    b.append(c.isNull(3) ? "" : c.getDouble(3)).append(',').append(c.getInt(4)).append('\n');
                }
            }
            return b.toString();
        }
    }
}
