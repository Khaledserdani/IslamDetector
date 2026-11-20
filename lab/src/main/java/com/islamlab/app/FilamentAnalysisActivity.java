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

/** Phone-first viewer for geometry-driven 3D TX/RX filament calculations. */
public class FilamentAnalysisActivity extends Activity {
    private static final int REQUEST_GEOMETRY = 811;
    private TextView resultView;
    private String lastReport = "";

    @Override protected void onCreate(Bundle state) {
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

        TextView title=label("تحليل الملف ثلاثي الأبعاد",24,Color.WHITE,true);
        title.setGravity(Gravity.CENTER);
        page.addView(title);
        TextView intro=label("استورد مسارات TX وRX من ملف هندسي JSON. يحسب المختبر المجال في نقاط الرصد والاقتران المتبادل وطول مسار اللفة.",14,0xffb8c8d9,false);
        intro.setPadding(0,dp(10),0,dp(14));
        page.addView(intro);

        TextView warning=label("حدود الحساب: نموذج سلك رفيع ساكن. لا يحاكي نبضة PI أو الهدف المعدني أو التربة أو دائرة الاستقبال. لا يستخرج عمق كشف.",13,0xffffd28a,false);
        warning.setPadding(dp(12),dp(12),dp(12),dp(12));
        warning.setBackgroundColor(0xff263142);
        page.addView(warning);

        Button open=button("استيراد هندسة الملف (JSON)");
        open.setOnClickListener(v->openGeometryPicker());
        page.addView(open);

        resultView=label("لم يتم تحميل هندسة بعد.",14,Color.WHITE,false);
        resultView.setTypeface(android.graphics.Typeface.MONOSPACE);
        resultView.setPadding(dp(12),dp(14),dp(12),dp(14));
        resultView.setBackgroundColor(0xff111e30);
        LinearLayout.LayoutParams rp=new LinearLayout.LayoutParams(-1,-2);
        rp.topMargin=dp(14);
        page.addView(resultView,rp);

        Button share=button("مشاركة تقرير الحساب");
        share.setOnClickListener(v->shareReport());
        page.addView(share);

        Button back=button("العودة إلى المختبر");
        back.setOnClickListener(v->finish());
        page.addView(back);
        setContentView(scroll);
    }

    private void openGeometryPicker(){
        Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("application/json");
        startActivityForResult(intent,REQUEST_GEOMETRY);
    }

    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data){
        super.onActivityResult(requestCode,resultCode,data);
        if(requestCode!=REQUEST_GEOMETRY || resultCode!=RESULT_OK || data==null) return;
        Uri uri=data.getData();
        if(uri==null) return;
        try(InputStream in=getContentResolver().openInputStream(uri)){
            if(in==null) throw new IllegalStateException("تعذر فتح ملف الهندسة");
            ByteArrayOutputStream out=new ByteArrayOutputStream();
            byte[] buffer=new byte[8192];
            int n; long total=0;
            while((n=in.read(buffer))!=-1){
                total+=n;
                if(total>5L*1024L*1024L) throw new IllegalArgumentException("حجم ملف الهندسة يتجاوز 5 ميغابايت");
                out.write(buffer,0,n);
            }
            FilamentGeometryInput input=FilamentGeometryInput.parse(out.toString("UTF-8"));
            lastReport=calculate(input);
            resultView.setText(lastReport);
            Toast.makeText(this,"اكتمل الحساب الهندسي",Toast.LENGTH_SHORT).show();
        }catch(Exception e){
            lastReport="";
            resultView.setText("تعذر تحليل الملف:\n"+(e.getMessage()==null?e.getClass().getSimpleName():e.getMessage()));
            Toast.makeText(this,"ملف الهندسة غير صالح",Toast.LENGTH_LONG).show();
        }
    }

    private String calculate(FilamentGeometryInput g){
        double txLength=FilamentPhysics.pathLengthMetres(g.txPath);
        double rxLength=FilamentPhysics.pathLengthMetres(g.rxPath);
        double mutual=FilamentPhysics.mutualInductanceHenries(g.txPath,g.rxPath,g.txTurns,g.rxTurns);
        double[][] field=FilamentPhysics.fieldAtPoints(g.txPath,g.observationPoints,g.txCurrentAmps,g.txTurns);
        StringBuilder b=new StringBuilder();
        b.append("نتائج النواة الهندسية ثلاثية الأبعاد\n");
        b.append("--------------------------------\n");
        b.append(String.format(Locale.US,"TX: %d لفة | طول مسار اللفة %.6f m\n",g.txTurns,txLength));
        b.append(String.format(Locale.US,"RX: %d لفة | طول مسار اللفة %.6f m\n",g.rxTurns,rxLength));
        b.append(String.format(Locale.US,"تيار TX المستخدم: %.6f A\n",g.txCurrentAmps));
        b.append(String.format(Locale.US,"المحاثة المتبادلة الموقعة M: %.6f µH\n",mutual*1e6));
        if(g.txWireLengthMetres!=null){
            double avg=g.txWireLengthMetres/g.txTurns;
            b.append(String.format(Locale.US,"TX متوسط النحاس/لفة: %.6f m | نسبة المسار/المتوسط: %.4f\n",avg,txLength/avg));
        }
        if(g.rxWireLengthMetres!=null){
            double avg=g.rxWireLengthMetres/g.rxTurns;
            b.append(String.format(Locale.US,"RX متوسط النحاس/لفة: %.6f m | نسبة المسار/المتوسط: %.4f\n",avg,rxLength/avg));
        }
        b.append("\nالمجال عند نقاط الرصد:\n");
        for(int i=0;i<field.length;i++){
            double mag=Math.sqrt(field[i][0]*field[i][0]+field[i][1]*field[i][1]+field[i][2]*field[i][2]);
            b.append(String.format(Locale.US,"P%d: Bx %.4f | By %.4f | Bz %.4f | |B| %.4f µT\n",
                    i+1,field[i][0]*1e6,field[i][1]*1e6,field[i][2]*1e6,mag*1e6));
        }
        b.append("\nمصدر الهندسة: ملف JSON مستورد من المستخدم.\n");
        b.append("نوع الحساب: Biot–Savart + Neumann، تقريب سلك رفيع ونقاط منتصف.\n");
        b.append("لا توجد تربة أو أهداف موصلة أو نبضة زمنية أو AFE في هذا الحساب.");
        return b.toString();
    }

    private void shareReport(){
        if(lastReport.isEmpty()){
            Toast.makeText(this,"أنجز حساباً أولاً",Toast.LENGTH_SHORT).show();
            return;
        }
        Intent send=new Intent(Intent.ACTION_SEND);
        send.setType("text/plain");
        send.putExtra(Intent.EXTRA_SUBJECT,"ISLAM LAB — 3D coil report");
        send.putExtra(Intent.EXTRA_TEXT,lastReport);
        startActivity(Intent.createChooser(send,"مشاركة التقرير"));
    }

    private TextView label(String text,int size,int color,boolean bold){
        TextView v=new TextView(this);
        v.setText(text); v.setTextSize(size); v.setTextColor(color);
        if(bold) v.setTypeface(android.graphics.Typeface.DEFAULT,android.graphics.Typeface.BOLD);
        return v;
    }
    private Button button(String text){
        Button b=new Button(this); b.setText(text); b.setTextColor(Color.WHITE);
        b.setBackgroundColor(0xff174b72);
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,dp(52));
        p.topMargin=dp(10); b.setLayoutParams(p); return b;
    }
    private int dp(float value){return (int)(value*getResources().getDisplayMetrics().density+0.5f);}
}
