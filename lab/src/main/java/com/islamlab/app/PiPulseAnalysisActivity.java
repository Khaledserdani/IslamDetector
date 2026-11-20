package com.islamlab.app;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.Locale;

/** Phone-first UI for the coupled PI pulse transient engine. */
public class PiPulseAnalysisActivity extends Activity {
    private static final int REQUEST_PULSE_JSON=812;
    private static final int REQUEST_AFE_JSON=813;
    private TextView resultView;
    private Button runButton,afeButton;
    private String lastReport="";
    private PiPulseInput pulseInput;
    private PiPulseEngine.Result lastPulseResult;
    private PiAfeInput afeInput=PiAfeInput.defaults();

    @Override protected void onCreate(Bundle state){
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.rgb(8,16,29));
        getWindow().setNavigationBarColor(Color.rgb(8,16,29));
        ScrollView scroll=new ScrollView(this);
        scroll.setBackgroundColor(Color.rgb(8,16,29));
        LinearLayout page=new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(dp(18),dp(18),dp(18),dp(28));
        page.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);
        scroll.addView(page);

        TextView title=label("محرك نبضة PI",24,Color.WHITE,true);
        title.setGravity(Gravity.CENTER);
        page.addView(title);
        TextView intro=label("يحل زمنياً اقتران دائرة TX مع حلقة تيارات دوامية مكافئة للهدف، ثم يفصل جهد RX المستحث إلى تسريب TX المباشر واستجابة الهدف.",14,0xffb8c8d9,false);
        intro.setPadding(0,dp(10),0,dp(14));
        page.addView(intro);

        TextView warning=label("مرحلة النبضة تحسب RX كمصدر مستحث مفتوح الدائرة، ثم يحمّله محرك AFE بشبكة R/L والحماية والتخميد. الهدف ما زال حلقة مكافئة واحدة؛ لا يوجد بعد توزيع حجمي ثلاثي الأبعاد أو تربة أو مضخم OPA365 أو ADC. القيم الافتراضية للمقارنة فقط.",13,0xffffd28a,false);
        warning.setPadding(dp(12),dp(12),dp(12),dp(12));
        warning.setBackgroundColor(0xff263142);
        page.addView(warning);

        Button importButton=button("استيراد إعداد النبضة والهندسة (JSON)");
        importButton.setOnClickListener(v->openPicker());
        page.addView(importButton);
        Button sampleButton=button("تشغيل المثال المرجعي المدمج");
        sampleButton.setOnClickListener(v->loadSamplePulse());
        page.addView(sampleButton);

        runButton=button("تشغيل محرك النبضة");
        runButton.setEnabled(false);
        runButton.setOnClickListener(v->runPulseAgain());
        page.addView(runButton);
        Button importAfe=button("استيراد إعداد حماية RX / AFE (JSON)");
        importAfe.setOnClickListener(v->openAfePicker());
        page.addView(importAfe);
        afeButton=button("تحليل الاستقبال والحماية AFE");
        afeButton.setEnabled(false);
        afeButton.setOnClickListener(v->runAfeAnalysis());
        page.addView(afeButton);

        resultView=label("لم يتم تحميل إعداد النبضة بعد.",14,Color.WHITE,false);
        resultView.setTypeface(android.graphics.Typeface.MONOSPACE);
        resultView.setPadding(dp(12),dp(14),dp(12),dp(14));
        resultView.setBackgroundColor(0xff111e30);
        LinearLayout.LayoutParams rp=new LinearLayout.LayoutParams(-1,-2);
        rp.topMargin=dp(14);
        page.addView(resultView,rp);

        Button share=button("مشاركة تقرير محاكاة النبضة");
        share.setOnClickListener(v->shareReport());
        page.addView(share);
        Button back=button("العودة إلى المختبر");
        back.setOnClickListener(v->finish());
        page.addView(back);
        setContentView(scroll);
    }

    private void openPicker(){
        Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("application/json");
        startActivityForResult(intent,REQUEST_PULSE_JSON);
    }

    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data){
        super.onActivityResult(requestCode,resultCode,data);
        if(resultCode!=RESULT_OK||data==null)return;
        if(requestCode==REQUEST_AFE_JSON){
            Uri afeUri=data.getData();if(afeUri==null)return;
            try(InputStream in=getContentResolver().openInputStream(afeUri)){
                if(in==null)throw new IllegalStateException("تعذر فتح إعداد AFE");
                ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buf=new byte[4096];int n;long size=0;
                while((n=in.read(buf))!=-1){size+=n;if(size>1024*1024)throw new IllegalArgumentException("ملف AFE أكبر من 1 ميغابايت");out.write(buf,0,n);}
                afeInput=PiAfeInput.parse(out.toString("UTF-8"));
                Toast.makeText(this,"تم تحميل إعداد حماية RX/AFE",Toast.LENGTH_LONG).show();
            }catch(Exception e){Toast.makeText(this,"إعداد AFE غير صالح: "+e.getMessage(),Toast.LENGTH_LONG).show();}
            return;
        }
        if(requestCode!=REQUEST_PULSE_JSON)return;
        Uri uri=data.getData();
        if(uri==null)return;
        try(InputStream in=getContentResolver().openInputStream(uri)){
            if(in==null)throw new IllegalStateException("تعذر فتح ملف الإعداد");
            ByteArrayOutputStream out=new ByteArrayOutputStream();
            byte[] buffer=new byte[8192]; int n; long total=0;
            while((n=in.read(buffer))!=-1){
                total+=n;
                if(total>5L*1024L*1024L)throw new IllegalArgumentException("حجم الملف يتجاوز 5 ميغابايت");
                out.write(buffer,0,n);
            }
            final PiPulseInput input=PiPulseInput.parse(out.toString("UTF-8"));
            pulseInput=input;
            executePulse(input);
        }catch(Exception e){
            lastReport="";
            resultView.setText("تعذر قراءة إعداد النبضة:\n"+(e.getMessage()==null?e.getClass().getSimpleName():e.getMessage()));
            Toast.makeText(this,"ملف إعداد النبضة غير صالح",Toast.LENGTH_LONG).show();
        }
    }


    private void openAfePicker(){
        Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("application/json");
        startActivityForResult(intent,REQUEST_AFE_JSON);
    }

    private String readStream(InputStream in)throws Exception{
        ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buffer=new byte[8192];int n;long total=0;
        while((n=in.read(buffer))!=-1){total+=n;if(total>5L*1024L*1024L)throw new IllegalArgumentException("حجم الإعداد يتجاوز 5 ميغابايت");out.write(buffer,0,n);}
        return out.toString("UTF-8");
    }

    private void loadSamplePulse(){
        try(InputStream pulse=getAssets().open("sample_pulse_config.json");
            InputStream afe=getAssets().open("sample_afe_config.json")){
            pulseInput=PiPulseInput.parse(readStream(pulse));
            afeInput=PiAfeInput.parse(readStream(afe));
            executePulse(pulseInput);
        }catch(Exception e){
            Toast.makeText(this,"تعذر تحميل المثال المدمج: "+e.getMessage(),Toast.LENGTH_LONG).show();
        }
    }

    private void executePulse(PiPulseInput input){
        runButton.setEnabled(false);afeButton.setEnabled(false);
        resultView.setText("جارٍ حساب النبضة والاستجابة المستحثة...");
        new Thread(()->{
            try{
                PiPulseEngine.Result result=PiPulseEngine.simulate(input);
                String report=makeReport(result,input);
                runOnUiThread(()->{
                    lastPulseResult=result;lastReport=report;resultView.setText(report);
                    runButton.setEnabled(true);afeButton.setEnabled(true);
                    Toast.makeText(this,"اكتمل حساب النبضة",Toast.LENGTH_SHORT).show();
                });
            }catch(Exception e){
                runOnUiThread(()->{
                    lastReport="";lastPulseResult=null;afeButton.setEnabled(false);
                    resultView.setText("فشل الحساب: "+e.getMessage());runButton.setEnabled(true);
                });
            }
        }).start();
    }

    private void runPulseAgain(){
        if(pulseInput==null){Toast.makeText(this,"استورد إعداد النبضة أولاً",Toast.LENGTH_SHORT).show();return;}
        executePulse(pulseInput);
    }

    private void runAfeAnalysis(){
        if(lastPulseResult==null){Toast.makeText(this,"شغّل محرك النبضة أولاً",Toast.LENGTH_SHORT).show();return;}
        afeButton.setEnabled(false);
        resultView.setText("جارٍ تحميل RX وحساب الحماية وميزانية الطاقة...");
        new Thread(()->{
            try{
                PiAfeEngine.Result result=PiAfeEngine.simulate(lastPulseResult.time,lastPulseResult.rxTotal,afeInput);
                String report=makeAfeReport(result,afeInput);
                runOnUiThread(()->{
                    lastReport=makeReport(lastPulseResult,pulseInput)+"\n\n"+report;
                    resultView.setText(report);
                    afeButton.setEnabled(true);
                    Toast.makeText(this,"اكتمل تحليل RX وAFE",Toast.LENGTH_SHORT).show();
                });
            }catch(Exception e){
                runOnUiThread(()->{resultView.setText("تعذر تحليل AFE: "+e.getMessage());afeButton.setEnabled(true);});
            }
        }).start();
    }

    private String makeAfeReport(PiAfeEngine.Result r,PiAfeInput p){
        StringBuilder b=new StringBuilder("ISLAM LAB — تقرير RX / AFE\n");
        b.append("--------------------------------\n");
        b.append(String.format(Locale.US,"ملف RX: R=%.3f Ω | L=%.3f µH\n",p.rxResistance,p.rxInductance*1e6));
        b.append(String.format(Locale.US,"تخميد متوازٍ: %.1f Ω | حماية متسلسلة: %.1f Ω\n",p.dampingResistance,p.seriesResistance));
        b.append(String.format(Locale.US,"سعة المدخل: %.3f nF | انحياز: %.0f kΩ\n",p.inputCapacitance*1e9,p.biasResistance/1e3));
        b.append(String.format(Locale.US,"قمة القوة المستحثة: %.6f V\n",r.peakInducedEmf));
        b.append(String.format(Locale.US,"قمة جهد طرف RX بعد التحميل: %.6f V\n",r.peakCoilTerminal));
        b.append(String.format(Locale.US,"قمة جهد مدخل AFE: %.6f V\n",r.peakInputVoltage));
        b.append(String.format(Locale.US,"قمة تيار ملف RX: %.6f A\n",r.peakCoilCurrent));
        b.append(String.format(Locale.US,"قمة تيار المحدد: %.6f A\n",r.peakClampCurrent));
        b.append(String.format(Locale.US,"طاقة TVS الملف: %.6f µJ\n",r.coilTvsEnergy*1e6));
        b.append(String.format(Locale.US,"طاقة محدد المدخل: %.6f µJ\n",r.inputClampEnergy*1e6));
        b.append(String.format(Locale.US,"فقد وصلة Schottky: %.6f µJ\\n",r.inputClampDiodeLoss*1e6));
        b.append(String.format(Locale.US,"الطاقة المتبادلة مع سكة التغذية: %.6f µJ\\n",r.inputClampRailEnergy*1e6));
        b.append(String.format(Locale.US,"خرج OPA365 السلوكي: %.6f .. %.6f V\n",r.minOpampOutput,r.peakOpampOutput));
        b.append(String.format(Locale.US,"عينات حد معدل التغير: %d | عينات قص الخرج: %d\n",r.slewLimitedSamples,r.outputSaturationSamples));
        b.append(String.format(Locale.US,"خطأ اتزان الطاقة: %.6f %%\n",r.energyRelativeError*100));
        b.append("\nهذه شبكة AFE مختزلة؛ لا يوجد بعد نموذج المضخم OPA365 أو ADC أو طفيليات اللوحة. قيم TVS والمحدد افتراضية للمقارنة وليست توصية شراء.");
        return b.toString();
    }

    private String makeReport(PiPulseEngine.Result r,PiPulseInput p){
        StringBuilder b=new StringBuilder();
        b.append("ISLAM LAB — تقرير محرك نبضة PI\n");
        b.append("--------------------------------\n");
        b.append(String.format(Locale.US,"تغذية المقارنة: %.3f V | عرض النبضة: %.3f µs\n",p.busVoltage,p.pulseWidth*1e6));
        b.append(String.format(Locale.US,"TX: R=%.4f Ω | L=%.3f µH | %d لفة\n",p.txResistance,p.txInductance*1e6,p.txTurns));
        b.append(String.format(Locale.US,"RX: L=%.3f µH | %d لفة (مفتوح الدائرة)\n",p.rxInductance*1e6,p.rxTurns));
        b.append(String.format(Locale.US,"الهدف المكافئ: R=%.5f Ω | L=%.3f µH\n",p.targetResistance,p.targetInductance*1e6));
        b.append(String.format(Locale.US,"تثبيت الإطفاء: %.3f V | خطوة: %.3f µs\n",p.clampVoltage,p.timeStep*1e6));
        b.append("\nاقتران المحاثة الموقّع:\n");
        b.append(String.format(Locale.US,"M(TX,هدف)=%.6f µH\n",r.mTxTarget*1e6));
        b.append(String.format(Locale.US,"M(TX,RX)=%.6f µH\n",r.mTxRx*1e6));
        b.append(String.format(Locale.US,"M(RX,هدف)=%.6f µH\n",r.mRxTarget*1e6));
        b.append("\nاستجابة الزمن:\n");
        b.append(String.format(Locale.US,"أقصى تيار TX: %.6f A\n",r.peakTxCurrent));
        b.append(String.format(Locale.US,"تيار TX عند الإطفاء: %.6f A\n",r.txCurrentAtTurnoff));
        b.append(String.format(Locale.US,"أقصى تيار في حلقة الهدف: %.6f A\n",r.peakTargetCurrent));
        b.append(String.format(Locale.US,"أقصى جهد RX الكلي: %.6f mV\n",r.peakRxVoltage*1e3));
        b.append(String.format(Locale.US,"أقصى RX بعد الإطفاء: %.6f mV\n",r.peakRxAfterTurnoff*1e3));
        b.append(String.format(Locale.US,"مكوّن TX المباشر: %.6f mV\n",r.peakRxDirect*1e3));
        b.append(String.format(Locale.US,"مكوّن الهدف: %.6f mV\n",r.peakRxTarget*1e3));
        b.append("\nاستعادة RX بعد الإطفاء:\n");
        b.append(String.format(Locale.US,"بعد 1 µs — مباشر %.6f mV | هدف %.6f mV | كلي %.6f mV\n",r.rxDirectAfter1us*1e3,r.rxTargetAfter1us*1e3,r.rxTotalAfter1us*1e3));
        b.append(String.format(Locale.US,"بعد 5 µs — مباشر %.6f mV | هدف %.6f mV | كلي %.6f mV\n",r.rxDirectAfter5us*1e3,r.rxTargetAfter5us*1e3,r.rxTotalAfter5us*1e3));
        b.append(String.format(Locale.US,"بعد 10 µs — مباشر %.6f mV | هدف %.6f mV | كلي %.6f mV\n",r.rxDirectAfter10us*1e3,r.rxTargetAfter10us*1e3,r.rxTotalAfter10us*1e3));
        b.append(String.format(Locale.US,"جهد الهدف عند الإطفاء: %.6f mV | تيار الهدف: %.6f A\n",r.rxTargetAtTurnoff*1e3,r.targetCurrentAtTurnoff));
        b.append("\nميزانية الطاقة العددية:\n");
        b.append(String.format(Locale.US,"طاقة المصدر: %.6f mJ\n",r.sourceEnergy*1e3));
        b.append(String.format(Locale.US,"فقد النحاس TX: %.6f mJ\n",r.txLossEnergy*1e3));
        b.append(String.format(Locale.US,"فقد الهدف: %.6f mJ\n",r.targetLossEnergy*1e3));
        b.append(String.format(Locale.US,"طاقة التثبيت: %.6f mJ\n",r.clampEnergy*1e3));
        b.append(String.format(Locale.US,"خطأ اتزان الطاقة النسبي: %.4f %%\n",r.energyRelativeError*100));
        b.append("\nالحالة: نموذج دائرة مقترنة مختزل بحلقة هدف مكافئة واحدة، وRX مفتوح الدائرة. ليس FEM ثلاثي الأبعاد للهدف ولا قياساً عتادياً. لا يستنتج عمق كشف.");
        return b.toString();
    }

    private void shareReport(){
        if(lastReport.isEmpty()){
            Toast.makeText(this,"شغّل المحاكاة أولاً",Toast.LENGTH_SHORT).show();
            return;
        }
        Intent send=new Intent(Intent.ACTION_SEND);
        send.setType("text/plain");
        send.putExtra(Intent.EXTRA_SUBJECT,"ISLAM LAB — PI pulse report");
        send.putExtra(Intent.EXTRA_TEXT,lastReport);
        startActivity(Intent.createChooser(send,"مشاركة التقرير"));
    }
    private TextView label(String text,int size,int color,boolean bold){
        TextView v=new TextView(this);v.setText(text);v.setTextSize(size);v.setTextColor(color);
        if(bold)v.setTypeface(android.graphics.Typeface.DEFAULT,android.graphics.Typeface.BOLD);
        return v;
    }
    private Button button(String text){
        Button b=new Button(this);b.setText(text);b.setTextColor(Color.WHITE);b.setBackgroundColor(0xff174b72);
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,dp(52));p.topMargin=dp(10);b.setLayoutParams(p);return b;
    }
    private int dp(float value){return (int)(value*getResources().getDisplayMetrics().density+0.5f);}
}
