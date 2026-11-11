package com.islamlab.app;

import android.app.Activity;
import com.islamlab.app.core.SyntheticDecayModel;
import android.os.Bundle;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Color;
import android.view.Gravity;
import android.view.View;
import android.widget.*;
import android.content.Intent;
import java.util.Locale;

public class MainActivity extends Activity {
    private EditText amplitudeInput, tauInput, noiseInput;
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
            resultText.setText(b.toString());
            waveView.invalidate();
            statusText.setText(String.format(Locale.US, "تم توليد %d عينات • τ = %.2f µs • ضوضاء اسمية %.2f mV", windowsUs.length, tau, noise));
        } catch (Exception ex) {
            Toast.makeText(this, "أدخل قيماً رقمية موجبة وصحيحة", Toast.LENGTH_LONG).show();
        }
    }

    private void shareReport() {
        if (report.isEmpty()) runSimulation();
        Intent intent = new Intent(Intent.ACTION_SEND);
        intent.setType("text/csv");
        intent.putExtra(Intent.EXTRA_SUBJECT, "ISLAM LAB experiment");
        intent.putExtra(Intent.EXTRA_TEXT, report);
        startActivity(Intent.createChooser(intent, "تصدير بيانات التجربة"));
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
