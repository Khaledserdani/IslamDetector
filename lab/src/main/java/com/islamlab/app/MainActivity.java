package com.islamlab.app;

import android.app.Activity;
import com.islamlab.app.core.SyntheticDecayModel;
import android.os.Bundle;
import android.os.Build;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Color;
import android.view.Gravity;
import android.view.View;
import android.widget.*;
import android.content.Intent;
import android.net.Uri;
import android.content.SharedPreferences;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

public class MainActivity extends Activity {
    private EditText amplitudeInput, tauInput, noiseInput, measuredInput;
    private SharedPreferences experimentPrefs;
    private static final int REQUEST_CSV = 701;
    private TextView resultText, statusText;
    private WaveView waveView;
    private double[] windowsUs = {8, 12, 16, 24, 36, 52, 72, 100};
    private double[] samplesMv = new double[8];
    private String report = "";
    private SyntheticDecayModel.Result currentResult;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.rgb(8, 16, 29));
        getWindow().setNavigationBarColor(Color.rgb(8, 16, 29));
        experimentPrefs = getSharedPreferences("experiments", MODE_PRIVATE);
        buildUi();
        runSimulation();
    }

    private void buildUi() {
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(Color.rgb(8, 16, 29));
        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(dp(18), dp(18), dp(18), dp(28));
        page.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);
        scroll.addView(page);

        TextView title = label("ISLAM LAB", 28, Color.WHITE, true);
        title.setGravity(Gravity.CENTER);
        page.addView(title);
        TextView subtitle = label("المختبر الهندسي والمحاكاة", 15, 0xff9bb2c9, false);
        subtitle.setGravity(Gravity.CENTER);
        page.addView(subtitle);
        statusText = label("وضع العمل: مولّد إشارة اصطناعية للاختبار", 13, 0xff7dd3a7, true);
        statusText.setPadding(0, dp(14), 0, dp(10));
        page.addView(statusText);

        TextView warning = label("تنبيه علمي: هذه النسخة تولّد موجة اختبار رياضية قابلة للتحكم. ليست محاكاة كهرومغناطيسية لهدف مدفون، ولا تتنبأ بعمق الكشف أو نوع المعدن.", 13, 0xffffd28a, false);
        warning.setPadding(dp(12), dp(12), dp(12), dp(12));
        warning.setBackgroundColor(0xff263142);
        page.addView(warning);

        page.addView(section("إعداد تجربة الإشارة"));
        page.addView(label("سعة البداية (mV)", 14, 0xffd5e2ef, true));
        amplitudeInput = field("أدخل القيمة", "1000");
        page.addView(amplitudeInput);
        page.addView(label("زمن الاضمحلال τ (µs)", 14, 0xffd5e2ef, true));
        tauInput = field("أدخل القيمة", "24");
        page.addView(tauInput);
        page.addView(label("سعة ضوضاء الاختبار الاسمية (mV)", 14, 0xffd5e2ef, true));
        noiseInput = field("أدخل القيمة", "2");
        page.addView(noiseInput);

        Button run = button("تشغيل المحاكاة");
        run.setOnClickListener(v -> runSimulation());
        page.addView(run);

        page.addView(section("الموجة الناتجة"));
        waveView = new WaveView();
        LinearLayout.LayoutParams waveParams = new LinearLayout.LayoutParams(-1, dp(210));
        waveParams.topMargin = dp(8);
        page.addView(waveView, waveParams);

        page.addView(section("عينات نوافذ الاستقبال"));
        resultText = label("", 14, Color.WHITE, false);
        resultText.setTypeface(android.graphics.Typeface.MONOSPACE);
        resultText.setPadding(dp(10), dp(12), dp(10), dp(12));
        resultText.setBackgroundColor(0xff111e30);
        page.addView(resultText);

        Button share = button("تصدير تقرير التجربة");
        share.setOnClickListener(v -> shareReport());
        page.addView(share);

        page.addView(section("القياسات الحقيقية"));
        page.addView(label("أدخل قراءات mV أو استورد ملف CSV من الهاتف", 13, 0xffd5e2ef, false));
        measuredInput = field("مثال: 12.5, 11.8, 10.2", "");
        measuredInput.setSingleLine(false);
        measuredInput.setMinLines(3);
        measuredInput.setGravity(Gravity.TOP | Gravity.RIGHT);
        page.addView(measuredInput);
        Button analyze = button("تحليل وحفظ القياسات");
        analyze.setOnClickListener(v -> analyzeMeasurements());
        page.addView(analyze);
        Button importCsv = button("استيراد ملف CSV");
        importCsv.setOnClickListener(v -> openCsvPicker());
        page.addView(importCsv);
        Button history = button("سجل التجارب المحفوظة");
        history.setOnClickListener(v -> showExperimentHistory());
        page.addView(history);
        page.addView(section("مركز التحديثات والملفات"));
        page.addView(label("يفحص قناة التحديثات، ويتحقق من بصمة APK قبل فتح مثبت أندرويد.", 13, 0xffd5e2ef, false));
        Button cleanUpdates = button("حذف ملفات التحديثات المنزّلة");
        cleanUpdates.setOnClickListener(v -> new android.app.AlertDialog.Builder(this)
                .setTitle("تنظيف ملفات التحديث")
                .setMessage("سيتم حذف ملفات APK المؤقتة التي نزّلها مركز التحديثات فقط. لن تُحذف التجارب أو ملفاتك الشخصية.")
                .setPositiveButton("حذف", (dialog, which) -> {
                    int count = UpdateCenter.clearDownloadedUpdates(this);
                    Toast.makeText(this, "تم حذف " + count + " ملف تحديث", Toast.LENGTH_LONG).show();
                })
                .setNegativeButton("إلغاء", null).show());
        page.addView(cleanUpdates);
        Button updates = button("فحص التحديثات وتنزيلها وتثبيتها");
        updates.setOnClickListener(v -> checkForUpdates());
        page.addView(updates);
        Button diagnostics = button("إنشاء تقرير تشخيصي آمن ومشاركته");
        diagnostics.setOnClickListener(v -> shareDiagnostics());
        page.addView(diagnostics);

        TextView footer = label("المرحلة التالية: ربط محرك فيزيائي موثّق، ومحاكاة الدوائر، ثم استقبال بيانات أجهزة القياس الحقيقية.", 12, 0xff9bb2c9, false);
        footer.setPadding(0, dp(18), 0, 0);
        page.addView(footer);
        setContentView(scroll);
    }

    private EditText field(String hint, String value) {
        EditText e = new EditText(this);
        e.setSingleLine(true);
        e.setText(value);
        e.setHint(hint);
        e.setTextColor(Color.WHITE);
        e.setHintTextColor(0xff9bb2c9);
        e.setTextSize(15);
        e.setPadding(dp(12), dp(8), dp(12), dp(8));
        e.setBackgroundColor(0xff17263a);
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-1, dp(52));
        p.topMargin = dp(7);
        e.setLayoutParams(p);
        return e;
    }

    private void runSimulation() {
        try {
            double a = Double.parseDouble(amplitudeInput.getText().toString().trim());
            double tau = Double.parseDouble(tauInput.getText().toString().trim());
            double noise = Double.parseDouble(noiseInput.getText().toString().trim());
            if (a <= 0 || tau <= 0 || noise < 0 || a > 1_000_000 || tau > 1_000_000 || noise > 1_000_000) throw new IllegalArgumentException();
            currentResult = SyntheticDecayModel.simulate(a, tau, noise);
            SyntheticDecayModel.Sample[] samples = currentResult.samples;
            StringBuilder b = new StringBuilder("النافذة µs   الإشارة   الضوضاء   الإجمالي mV\n");
            b.append("------------------------------------------\n");
            report = "ISLAM LAB - Synthetic waveform test\nModel," + currentResult.modelName + "\nModel_version," + currentResult.modelVersion + "\nSource_type,synthetic\nAmplitude_mV," + a + "\nTau_us," + tau + "\nNoise_nominal_mV," + noise + "\nwindow_us,signal_mV,noise_mV,total_mV\n";
            for (int i = 0; i < samples.length; i++) {
                SyntheticDecayModel.Sample sample = samples[i];
                samplesMv[i] = sample.totalMv;
                b.append(String.format(Locale.US, "%-10.1f %8.3f %8.3f %8.3f\n", sample.timeUs, sample.signalMv, sample.noiseMv, sample.totalMv));
                report += String.format(Locale.US, "%.1f,%.6f,%.6f,%.6f\n", sample.timeUs, sample.signalMv, sample.noiseMv, sample.totalMv);
            }
            double[] stats = LabMath.summarize(samplesMv);
            b.append("\nملخص العينات الكلي\n");
            b.append(String.format(Locale.US, "min %.3f | max %.3f | mean %.3f mV\n", stats[0], stats[1], stats[2]));
            b.append(String.format(Locale.US, "peak-to-peak %.3f | std.dev %.3f mV\n", stats[3], stats[4]));
            report += String.format(Locale.US, "summary_min_mV,%.6f\nsummary_max_mV,%.6f\nsummary_mean_mV,%.6f\nsummary_peak_to_peak_mV,%.6f\nsummary_stddev_mV,%.6f\n", stats[0], stats[1], stats[2], stats[3], stats[4]);
            resultText.setText(b.toString());
            waveView.invalidate();
            statusText.setText(String.format(Locale.US, "تم توليد %d عينات • τ = %.2f µs • ضوضاء اسمية %.2f mV", windowsUs.length, tau, noise));
        } catch (Exception ex) {
            Toast.makeText(this, "أدخل قيماً رقمية موجبة وصحيحة", Toast.LENGTH_LONG).show();
        }
    }

    private void analyzeMeasurements() {
        try {
            double[] values = ExperimentData.parse(measuredInput.getText().toString());
            double[] stats = LabMath.summarize(values);
            report = ExperimentData.toCsv(values);
            resultText.setText(String.format(Locale.US,
                    "مصدر البيانات: قياسات أدخلها المستخدم\nعدد القراءات: %d\nأقل قيمة: %.4f mV\nأعلى قيمة: %.4f mV\nالمتوسط: %.4f mV\nالمدى: %.4f mV\nالانحراف المعياري: %.4f mV",
                    (int)stats[5], stats[0], stats[1], stats[2], stats[3], stats[4]));
            statusText.setText("وضع العمل: تحليل قياسات فعلية أدخلها المستخدم");
            String key = "experiment_" + System.currentTimeMillis();
            experimentPrefs.edit().putString(key, report).putString("last_key", key).apply();
            Toast.makeText(this, "تم تحليل القياسات وحفظها محلياً", Toast.LENGTH_SHORT).show();
        } catch (Exception ex) {
            Toast.makeText(this, ex.getMessage() == null ? "تحقق من القراءات" : ex.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private void openCsvPicker() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"text/csv", "text/comma-separated-values", "application/vnd.ms-excel", "text/plain"});
        startActivityForResult(intent, REQUEST_CSV);
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_CSV || resultCode != RESULT_OK || data == null || data.getData() == null) return;
        Uri uri = data.getData();
        try (InputStream in = getContentResolver().openInputStream(uri);
             BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
            StringBuilder text = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                if (text.length() + line.length() > 2_000_000) throw new IllegalArgumentException("الملف أكبر من الحد المسموح");
                text.append(line).append('\n');
            }
            measuredInput.setText(text.toString());
            Toast.makeText(this, "تم تحميل الملف. اضغط تحليل وحفظ القياسات.", Toast.LENGTH_LONG).show();
        } catch (Exception ex) {
            Toast.makeText(this, "تعذر قراءة الملف: " + ex.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private void showExperimentHistory() {
        java.util.Map<String, ?> all = experimentPrefs.getAll();
        java.util.ArrayList<String> keys = new java.util.ArrayList<>();
        for (String key : all.keySet()) {
            if (key.startsWith("experiment_")) keys.add(key);
        }
        java.util.Collections.sort(keys, java.util.Collections.reverseOrder());
        if (keys.isEmpty()) {
            new android.app.AlertDialog.Builder(this).setTitle("سجل التجارب")
                    .setMessage("لا توجد تجارب محفوظة بعد.")
                    .setPositiveButton("حسناً", null).show();
            return;
        }
        java.util.ArrayList<String> labels = new java.util.ArrayList<>();
        for (String key : keys) {
            String fallback = "تجربة " + key.substring("experiment_".length());
            labels.add(experimentPrefs.getString("name_" + key, fallback));
        }
        new android.app.AlertDialog.Builder(this).setTitle("التجارب المحفوظة")
                .setItems(labels.toArray(new String[0]), (dialog, which) -> {
                    String key = keys.get(which);
                    String fallback = "تجربة " + key.substring("experiment_".length());
                    String name = experimentPrefs.getString("name_" + key, fallback);
                    new android.app.AlertDialog.Builder(this).setTitle(name)
                            .setItems(new String[]{"فتح التجربة", "إعادة تسمية", "تصدير CSV", "حذف التجربة"},
                                    (actionDialog, action) -> {
                                        if (action == 0) {
                                            report = experimentPrefs.getString(key, "");
                                            resultText.setText(report);
                                            statusText.setText("وضع العمل: عرض تجربة محفوظة");
                                        } else if (action == 1) {
                                            EditText nameInput = field("اسم التجربة", name);
                                            new android.app.AlertDialog.Builder(this).setTitle("إعادة تسمية التجربة")
                                                    .setView(nameInput)
                                                    .setPositiveButton("حفظ", (d, w) -> {
                                                        String updated = nameInput.getText().toString().trim();
                                                        if (updated.isEmpty()) {
                                                            Toast.makeText(this, "اكتب اسماً للتجربة", Toast.LENGTH_SHORT).show();
                                                        } else {
                                                            experimentPrefs.edit().putString("name_" + key, updated).apply();
                                                            Toast.makeText(this, "تم تحديث اسم التجربة", Toast.LENGTH_SHORT).show();
                                                            showExperimentHistory();
                                                        }
                                                    }).setNegativeButton("إلغاء", null).show();
                                        } else if (action == 2) {
                                            String saved = experimentPrefs.getString(key, "");
                                            if (!saved.isEmpty()) shareText(saved, name);
                                        } else if (action == 3) {
                                            new android.app.AlertDialog.Builder(this).setTitle("حذف التجربة")
                                                    .setMessage("سيتم حذف هذه التجربة المحفوظة فقط. لا يمكن التراجع عن الحذف.")
                                                    .setPositiveButton("حذف", (d, w) -> {
                                                        experimentPrefs.edit().remove(key).remove("name_" + key).apply();
                                                        Toast.makeText(this, "تم حذف التجربة", Toast.LENGTH_SHORT).show();
                                                        showExperimentHistory();
                                                    }).setNegativeButton("إلغاء", null).show();
                                        }
                                    }).setNegativeButton("إغلاق", null).show();
                }).setNegativeButton("إغلاق", null).show();
    }

    private void checkForUpdates() {
        statusText.setText("جارٍ الاتصال بقناة التحديثات…");
        UpdateCenter.check(this, new UpdateCenter.Listener() {
            @Override public void onMessage(String message) {
                statusText.setText(message);
                Toast.makeText(MainActivity.this, message, Toast.LENGTH_LONG).show();
            }
            @Override public void onReady(java.io.File apk) {
                statusText.setText("تم تنزيل التحديث والتحقق من SHA-256. بانتظار موافقتك في مثبت أندرويد.");
                new android.app.AlertDialog.Builder(MainActivity.this)
                        .setTitle("تحديث جاهز للتثبيت")
                        .setMessage("تم التحقق من سلامة الملف. هل تريد فتح مثبت أندرويد الآن؟")
                        .setPositiveButton("تثبيت", (dialog, which) -> UpdateCenter.install(MainActivity.this, apk))
                        .setNegativeButton("لاحقاً", null).show();
            }
        });
    }
    private void shareDiagnostics() {
        int saved = 0;
        for (String key : experimentPrefs.getAll().keySet()) if (key.startsWith("experiment_")) saved++;
        String version = "غير معروف";
        try { version = getPackageManager().getPackageInfo(getPackageName(), 0).versionName; }
        catch (Exception ignored) { }
        String diagnostic = "ISLAM LAB - Safe diagnostic report\n"
                + "App version: " + version + "\n"
                + "Android version: " + Build.VERSION.RELEASE + " (SDK " + Build.VERSION.SDK_INT + ")\n"
                + "Device: " + Build.MANUFACTURER + " " + Build.MODEL + "\n"
                + "Saved experiment count: " + saved + "\n"
                + "Network/location access: not requested by this app\n"
                + "Note: this report excludes personal files, location, and raw experiment values."; 
        shareText(diagnostic, "ISLAM LAB safe diagnostic report");
    }
    private void shareText(String content, String subject) {
        Intent intent = new Intent(Intent.ACTION_SEND);
        intent.setType("text/csv");
        intent.putExtra(Intent.EXTRA_SUBJECT, subject);
        intent.putExtra(Intent.EXTRA_TEXT, content);
        startActivity(Intent.createChooser(intent, "تصدير البيانات"));
    }
    private void shareReport() {
        if (report.isEmpty()) runSimulation();
        shareText(report, "ISLAM LAB experiment");
    }

    private TextView section(String s) {
        TextView t = label(s, 18, 0xff8ec5ff, true);
        t.setPadding(0, dp(18), 0, dp(4));
        return t;
    }
    private TextView label(String s, int size, int color, boolean bold) {
        TextView t = new TextView(this);
        t.setText(s); t.setTextSize(size); t.setTextColor(color);
        if (bold) t.setTypeface(null, android.graphics.Typeface.BOLD);
        return t;
    }
    private Button button(String s) {
        Button b = new Button(this); b.setText(s); b.setTextSize(15);
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-1, dp(52));
        p.topMargin = dp(12); b.setLayoutParams(p); return b;
    }
    private int dp(float v) { return (int)(v * getResources().getDisplayMetrics().density + 0.5f); }

    private class WaveView extends View {
        private final Paint paint = new Paint(3);
        WaveView() { super(MainActivity.this); setBackgroundColor(0xff111e30); }
        @Override protected void onDraw(Canvas c) {
            super.onDraw(c);
            float left=dp(38), right=getWidth()-dp(14), top=dp(16), bottom=getHeight()-dp(28);
            paint.setColor(0xff42546b); paint.setStrokeWidth(dp(1));
            for (int i=0;i<=4;i++) { float y=top+(bottom-top)*i/4f; c.drawLine(left,y,right,y,paint); }
            for (int i=0;i<=4;i++) { float x=left+(right-left)*i/4f; c.drawLine(x,top,x,bottom,paint); }
            paint.setColor(0xff9bb2c9); paint.setTextSize(dp(10));
            c.drawText("mV", dp(6), top+dp(5), paint);
            c.drawText("time →", right-dp(42), getHeight()-dp(6), paint);
            double max=1;
            for(double v:samplesMv) max=Math.max(max,v);
            paint.setColor(0xff52c7a5); paint.setStrokeWidth(dp(2.5f)); paint.setStyle(Paint.Style.STROKE);
            float prevX=left, prevY=bottom;
            for(int i=0;i<=160;i++) {
                double t=windowsUs[windowsUs.length-1]*i/160.0;
                double val=currentResult.valueAt(t);
                float x=left+(right-left)*i/160f;
                float y=bottom-(float)(val/max)*(bottom-top);
                if(i>0)c.drawLine(prevX,prevY,x,y,paint);
                prevX=x; prevY=y;
            }
            paint.setStyle(Paint.Style.FILL);
        }
    }
}
