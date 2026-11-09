package com.islamdetector.aipro;

import android.app.Activity;
import android.os.*;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

public class MainActivity extends Activity {
 private final Handler ui=new Handler(Looper.getMainLooper());
 private final ExecutorService io=Executors.newSingleThreadExecutor();
 private EditText host; private TextView state,phys,ai,judge,depth,raw,cal;
 private Button connect,start,calibrate; private boolean connected=false,dead=false,running=false;
 private JSONObject latest;
 private final Runnable ticker= new Runnable(){public void run(){if(connected)poll();if(!dead)ui.postDelayed(this,2000);}};
 @Override public void onCreate(Bundle b){super.onCreate(b);getWindow().setStatusBarColor(0xff06101d);getWindow().setNavigationBarColor(0xff06101d);build();host.setText(getPreferences(0).getString("host","192.168.4.1"));ui.post(ticker);}
 private void build(){
  ScrollView sc=new ScrollView(this);sc.setBackgroundColor(0xff06101d);
  LinearLayout p=new LinearLayout(this);p.setOrientation(1);p.setPadding(dp(16),dp(18),dp(16),dp(28));p.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);sc.addView(p);
  TextView logo=t("ISLAM DETECTOR AI PRO",23,-1,true);logo.setGravity(17);p.addView(logo,lp());
  TextView sub=t("منظومة التحليل الثلاثي • PI",13,0xff91abc4,false);sub.setGravity(17);add(p,sub,4);
  LinearLayout statusCard=card();state=t("● غير متصل بلوحة ESP32",14,0xffffc477,true);statusCard.addView(state,lp());add(p,statusCard,14);
  LinearLayout row=new LinearLayout(this);host=new EditText(this);host.setSingleLine(true);host.setTextColor(-1);host.setHintTextColor(0xff9aadc0);host.setHint("192.168.4.1");host.setBackground(bg(0xff17283d));row.addView(host,new LinearLayout.LayoutParams(0,dp(48),1));
  connect=button("اتصال",0xff147b70);LinearLayout.LayoutParams rp=new LinearLayout.LayoutParams(dp(92),dp(48));rp.rightMargin=dp(7);row.addView(connect,rp);add(p,row,8);connect.setOnClickListener(v->connect());
  add(p,t("المحركات الثلاثة",19,-1,true),20);
  phys=engineCard(p,"1 • المحرك الفيزيائي والرياضي","ينتظر بيانات النوافذ الزمنية من ESP32");
  ai=engineCard(p,"2 • محرك الذكاء الاصطناعي LiteRT","محرك التشغيل جاهز للربط؛ النموذج المدرّب غير مدمج بعد");
  judge=engineCard(p,"3 • محرك المقارنة والتحكيم","ينتظر مخرجات المحركين وجودة القياس");
  add(p,t("النتيجة النهائية",18,-1,true),18);
  LinearLayout jc=card();TextView jt=t("لا توجد نتيجة بعد",17,0xffe7c98e,true);jt.setGravity(17);jc.addView(jt,lp());add(p,jc,7);
  add(p,t("العمق والمعايرة",18,-1,true),18);
  LinearLayout dc=card();depth=t("العمق: غير متاح — نحتاج قياسات معايرة ميدانية",14,-1,true);cal=t("المعايرة: لا توجد بيانات",13,0xff79d9c2,false);dc.addView(depth,lp());add(dc,cal,8);add(p,dc,7);
  start=button("بدء الكشف",0xff138a68);start.setEnabled(false);add(p,start,10);start.setOnClickListener(v->command(running?"stop":"start"));
  calibrate=button("معايرة التربة",0xff315b91);calibrate.setEnabled(false);add(p,calibrate,8);calibrate.setOnClickListener(v->command("calibrate"));
  add(p,t("بيانات ESP32 الخام",16,-1,true),18);LinearLayout rc=card();raw=t("بانتظار /status",11,0xffb8c9d9,false);raw.setTextIsSelectable(true);rc.addView(raw,lp());add(p,rc,7);
  add(p,t("تأكيد المستخدم بعد التحقق الميداني",16,-1,true),18);
  TextView note=t("التأكيد يحفظ العينة لتحسين المحركات لاحقاً بعد مراجعة وتدريب واختبار مستقل؛ لا يحدث النموذج مباشرة.",12,0xffb8c9d9,false);add(p,note,5);
  LinearLayout fb=new LinearLayout(this);Button yes=button("هدف مؤكد",0xff236c54),no=button("لا يوجد",0xff795044),unk=button("غير حاسم",0xff53657a);for(Button b:new Button[]{yes,no,unk})fb.addView(b,new LinearLayout.LayoutParams(0,dp(48),1));add(p,fb,8);
  yes.setOnClickListener(v->feedback("confirmed"));no.setOnClickListener(v->feedback("no_target"));unk.setOnClickListener(v->feedback("inconclusive"));
  TextView foot=t("تطبيق مستقل • الإصدار 1.0.0 • APK قابل للاستخراج من Actions",10,0xff7189a2,false);foot.setGravity(17);add(p,foot,20);setContentView(sc);
 }
 private TextView engineCard(LinearLayout p,String title,String initial){LinearLayout c=card();TextView h=t(title,15,0xff8dd9d0,true);c.addView(h,lp());TextView body=t(initial,12,0xffd2deeb,false);add(c,body,7);add(p,c,9);return body;}
 private void connect(){String h=base();getPreferences(0).edit().putString("host",h).apply();connect.setEnabled(false);state.setText("جارٍ الاتصال...");io.execute(()->{try{JSONObject j=request(h+"/status","GET",null);ui.post(()->{connected=true;connect.setEnabled(true);state.setText("● متصل بلوحة ESP32");state.setTextColor(0xff69dfad);start.setEnabled(true);calibrate.setEnabled(true);apply(j);});}catch(Exception e){ui.post(()->{connected=false;connect.setEnabled(true);state.setText("● تعذر الاتصال — تحقق من شبكة ESP32");});}});}
 private String base(){String h=host.getText().toString().trim();if(h.isEmpty())h="192.168.4.1";if(!h.startsWith("http://")&&!h.startsWith("https://"))h="http://"+h;while(h.endsWith("/"))h=h.substring(0,h.length()-1);return h;}
 private void poll(){io.execute(()->{try{JSONObject j=request(base()+"/status","GET",null);ui.post(()->apply(j));}catch(Exception e){ui.post(()->{connected=false;state.setText("● انقطع الاتصال");start.setEnabled(false);calibrate.setEnabled(false);});}});}
 private JSONObject request(String url,String method,JSONObject body)throws Exception{HttpURLConnection c=(HttpURLConnection)new URL(url).openConnection();try{c.setRequestMethod(method);c.setConnectTimeout(3000);c.setReadTimeout(3000);if(body!=null){c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");try(OutputStream o=c.getOutputStream()){o.write(body.toString().getBytes(StandardCharsets.UTF_8));}}int code=c.getResponseCode();InputStream in=code>=200&&code<300?c.getInputStream():c.getErrorStream();String s;try(InputStream x=in;ByteArrayOutputStream b=new ByteArrayOutputStream()){byte[] z=new byte[2048];int n;while((n=x.read(z))!=-1)b.write(z,0,n);s=b.toString("UTF-8");}if(code<200||code>=300)throw new IOException("HTTP "+code);return new JSONObject(s);}finally{c.disconnect();}}
 private JSONObject data(JSONObject j){JSONObject d=j.optJSONObject("data");return d==null?j:d;}
 private void apply(JSONObject j){latest=j;JSONObject d=data(j);JSONArray w=d.optJSONArray("windows");double[] values=windowValues(w);double score=physicsScore(values);boolean enough=values.length>=3;
  phys.setText(enough?"تم تحليل "+values.length+" نوافذ. مؤشر انتظام/تغير الإشارة: "+(Double.isNaN(score)?"غير متاح":String.format(Locale.US,"%.1f%%",score)):"بيانات غير كافية: نحتاج 3 نوافذ زمنية أو أكثر.");
  ai.setText("LiteRT: لم يُحمّل نموذج مدرّب بعد. لا يوجد تصنيف آلي أو احتمال موثوق في هذه النسخة.");
  judge.setText(enough?"التحكيم: ينتظر نموذج LiteRT. لن يصدر حكماً نهائياً اعتماداً على محرك واحد.":"التحكيم: غير حاسم — نحتاج بيانات متعددة النوافذ ونموذجاً مختبراً.");
  depth.setText(d.has("depth_cm")&&!d.isNull("depth_cm")?"العمق المرسل من ESP32: "+d.optDouble("depth_cm")+" سم (غير متحقق ميدانياً)":"العمق: غير متاح؛ يلزم نموذج معايرة بأهداف معلومة الأعماق.");
  cal.setText("المعايرة: "+(d.optBoolean("calibrated",false)?"مكتملة حسب ESP32":"غير مؤكدة")+" • "+(d.has("calibration_percent")?d.optString("calibration_percent")+"%":"لا توجد نسبة"));
  String s=j.toString();raw.setText(s.length()>2400?s.substring(0,2400)+"…":s);
 }
 private double[] windowValues(JSONArray a){if(a==null)return new double[0];double[] x=new double[a.length()];int n=0;for(int i=0;i<a.length();i++){Object o=a.opt(i);double v=Double.NaN;if(o instanceof Number)v=((Number)o).doubleValue();else if(o instanceof JSONObject){JSONObject q=(JSONObject)o;String[] keys={"value","amplitude","signal","sample"};for(String k:keys)if(q.has(k)&&q.opt(k) instanceof Number){v=q.optDouble(k);break;}}if(!Double.isNaN(v))x[n++]=v;}return Arrays.copyOf(x,n);}
 private double physicsScore(double[] x){if(x.length<3)return Double.NaN;double mean=0;for(double v:x)mean+=v;mean/=x.length;double var=0;for(double v:x)var+=(v-mean)*(v-mean);double cv=Math.sqrt(var/x.length)/(Math.abs(mean)+1e-9);return 100.0/(1.0+cv);}
 private void command(String c){if(!connected)return;try{JSONObject b=new JSONObject();b.put("command",c);io.execute(()->{try{request(base()+"/control","POST",b);}catch(Exception e){ui.post(()->Toast.makeText(this,"تعذر إرسال الأمر",Toast.LENGTH_SHORT).show());}});}catch(Exception ignored){}}
 private void feedback(String label){if(latest==null){Toast.makeText(this,"لا توجد قراءة لتأكيدها بعد",Toast.LENGTH_SHORT).show();return;}getPreferences(0).edit().putString("last_feedback",label).putString("last_feedback_json",latest.toString()).apply();Toast.makeText(this,"حُفظ التأكيد محلياً؛ يحتاج مراجعة قبل تدريب أي نموذج",Toast.LENGTH_LONG).show();}
 private int dp(float n){return (int)(n*getResources().getDisplayMetrics().density+.5f);}private LinearLayout.LayoutParams lp(){return new LinearLayout.LayoutParams(-1,-2);}private void add(LinearLayout p,View v,int top){LinearLayout.LayoutParams a=lp();a.topMargin=dp(top);p.addView(v,a);}
 private GradientDrawable bg(int c){GradientDrawable d=new GradientDrawable();d.setColor(c);d.setCornerRadius(dp(14));d.setStroke(dp(1),0xff2b435e);return d;}
 private LinearLayout card(){LinearLayout l=new LinearLayout(this);l.setOrientation(1);l.setPadding(dp(13),dp(12),dp(13),dp(12));l.setBackground(bg(0xff122238));return l;}
 private TextView t(String s,int z,int c,boolean b){TextView v=new TextView(this);v.setText(s);v.setTextSize(z);v.setTextColor(c);if(b)v.setTypeface(Typeface.DEFAULT,Typeface.BOLD);return v;}
 private Button button(String s,int c){Button b=new Button(this);b.setText(s);b.setTextColor(-1);b.setAllCaps(false);b.setTextSize(12);b.setBackground(bg(c));return b;}
 @Override protected void onDestroy(){dead=true;ui.removeCallbacksAndMessages(null);io.shutdownNow();super.onDestroy();}
}
