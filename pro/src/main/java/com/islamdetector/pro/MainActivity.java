package com.islamdetector.pro;

import android.app.Activity;
import android.os.*;
import android.content.*;
import android.database.*;
import android.database.sqlite.*;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

public class MainActivity extends Activity {
 private final Handler ui=new Handler(Looper.getMainLooper());
 private final ExecutorService net=Executors.newSingleThreadExecutor();
 private final AtomicBoolean busy=new AtomicBoolean(false);
 private EditText address;
 private TextView status,signal,confidence,depth,cal,analysis,raw,history,feedback;
 private Button connect,start,calibrate;
 private Store db; private boolean linked=false,running=false,dead=false;
 private long latest=-1,lastSaved=0;
 private final Runnable ticker=new Runnable(){public void run(){if(linked)poll();if(!dead)ui.postDelayed(this,2000);}};
 @Override public void onCreate(Bundle b){super.onCreate(b);getWindow().setStatusBarColor(0xff06101d);getWindow().setNavigationBarColor(0xff06101d);db=new Store(this);build();address.setText(getPreferences(0).getString("host","192.168.4.1"));history();ui.post(ticker);}
 private void build(){
  ScrollView sc=new ScrollView(this);sc.setBackgroundColor(0xff06101d);LinearLayout p=new LinearLayout(this);p.setOrientation(1);p.setPadding(dp(16),dp(18),dp(16),dp(26));p.setLayoutDirection(View.LAYOUT_DIRECTION_RTL);sc.addView(p);
  TextView logo=t("ISLAM DETECTOR PRO",24,Color.WHITE,true);logo.setGravity(17);p.addView(logo,lp());
  TextView sub=t("المستكشف الذكي • منصة PI المتقدمة",13,0xff91abc4,false);sub.setGravity(17);add(p,sub,4);
  LinearLayout c=card();status=t("● غير متصل بلوحة ESP32",15,0xffffbd70,true);c.addView(status,lp());add(p,c,16);
  address=new EditText(this);address.setSingleLine(true);address.setTextColor(-1);address.setHint("192.168.4.1");address.setHintTextColor(0xff9aadc0);address.setBackground(bg(0xff17283d));LinearLayout row=new LinearLayout(this);row.addView(address,new LinearLayout.LayoutParams(0,dp(48),1));connect=button("اتصال",0xff147b70);LinearLayout.LayoutParams q=new LinearLayout.LayoutParams(dp(95),dp(48));q.rightMargin=dp(8);row.addView(connect,q);add(p,row,8);connect.setOnClickListener(v->connect());
  add(p,t("القياسات الواردة من ESP32",17,-1,true),20);LinearLayout m=new LinearLayout(this);signal=metric(m,"الإشارة");confidence=metric(m,"الثقة المرسلة");depth=metric(m,"العمق المرسل");p.addView(m,lp());
  LinearLayout cc=card();cal=t("المعايرة: لا توجد بيانات",14,0xff75d8c1,true);cc.addView(cal,lp());add(p,cc,10);
  start=button("بدء الكشف",0xff138a68);add(p,start,10);start.setEnabled(false);start.setOnClickListener(v->command(running?"stop":"start"));
  calibrate=button("معايرة التربة",0xff315b91);add(p,calibrate,8);calibrate.setEnabled(false);calibrate.setOnClickListener(v->command("calibrate"));
  add(p,t("التحليل الذكي المحلي",17,-1,true),20);LinearLayout ai=card();analysis=t("التشغيل المحلي جاهز. لم يدمج نموذج مدرّب بعد؛ لن نخترع تصنيفاً أو عمقاً.",13,0xffd2deeb,false);ai.addView(analysis,lp());add(p,ai,8);
  add(p,t("بيانات ESP32 الخام",16,-1,true),18);LinearLayout rc=card();raw=t("بانتظار /status",11,0xffb8c9d9,false);raw.setTextIsSelectable(true);rc.addView(raw,lp());add(p,rc,8);
  add(p,t("تأكيد نتيجة التجربة بعد التحقق الميداني",15,-1,true),18);feedback=t("اختر النتيجة بعد الحفر أو التحقق، لا قبل ذلك.",12,0xffb8c9d9,false);add(p,feedback,5);
  LinearLayout f=new LinearLayout(this);Button yes=button("هدف مؤكد",0xff236c54),no=button("لا يوجد",0xff795044),unk=button("غير حاسم",0xff53657a);f.addView(yes,new LinearLayout.LayoutParams(0,dp(46),1));f.addView(no,new LinearLayout.LayoutParams(0,dp(46),1));f.addView(unk,new LinearLayout.LayoutParams(0,dp(46),1));p.addView(f,lp());yes.setOnClickListener(v->label("confirmed"));no.setOnClickListener(v->label("no_target"));unk.setOnClickListener(v->label("inconclusive"));
  add(p,t("سجل التجارب المحفوظة",16,-1,true),20);LinearLayout h=card();history=t("لا توجد تجارب بعد",12,0xffd2deeb,false);h.addView(history,lp());add(p,h,8);Button ex=button("تصدير قاعدة التجارب CSV",0xff40536b);add(p,ex,8);ex.setOnClickListener(v->export());
  TextView foot=t("نسخة مستقلة عن التطبيق الأول • 1.0.0",10,0xff7189a2,false);foot.setGravity(17);add(p,foot,18);setContentView(sc);
 }
 private TextView metric(LinearLayout row,String title){LinearLayout c=card();c.setGravity(17);TextView v=t("--",22,-1,true);v.setGravity(17);c.addView(v,lp());TextView x=t(title,10,0xff9db3c9,false);x.setGravity(17);c.addView(x,lp());LinearLayout.LayoutParams a=new LinearLayout.LayoutParams(0,dp(82),1);a.setMargins(dp(3),0,dp(3),0);row.addView(c,a);return v;}
 private void connect(){String h=host();getPreferences(0).edit().putString("host",h).apply();connect.setEnabled(false);status.setText("● جارٍ الاتصال...");net.execute(()->{try{JSONObject j=request(h+"/status","GET",null);ui.post(()->{linked=true;connect.setEnabled(true);status.setText("● متصل باللوحة");status.setTextColor(0xff69dfad);start.setEnabled(true);calibrate.setEnabled(true);apply(j);});}catch(Exception e){ui.post(()->{linked=false;connect.setEnabled(true);status.setText("● فشل الاتصال — تحقق من Wi‑Fi");});}});}
 private String host(){String h=address.getText().toString().trim();if(h.isEmpty())h="192.168.4.1";if(!h.startsWith("http://")&&!h.startsWith("https://"))h="http://"+h;while(h.endsWith("/"))h=h.substring(0,h.length()-1);return h;}
 private void poll(){if(!busy.compareAndSet(false,true))return;net.execute(()->{try{JSONObject j=request(host()+"/status","GET",null);ui.post(()->{linked=true;apply(j);});}catch(Exception e){ui.post(()->{linked=false;status.setText("● انقطع الاتصال");start.setEnabled(false);calibrate.setEnabled(false);});}finally{busy.set(false);}});}
 private JSONObject request(String u,String method,JSONObject body)throws Exception{HttpURLConnection c=(HttpURLConnection)new URL(u).openConnection();try{c.setRequestMethod(method);c.setConnectTimeout(3000);c.setReadTimeout(3000);c.setRequestProperty("Accept","application/json");if(body!=null){c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json; charset=utf-8");try(OutputStream o=c.getOutputStream()){o.write(body.toString().getBytes(StandardCharsets.UTF_8));}}int code=c.getResponseCode();InputStream in=code>=200&&code<300?c.getInputStream():c.getErrorStream();String s=read(in);if(code<200||code>=300)throw new IOException("HTTP "+code);return new JSONObject(s);}finally{c.disconnect();}}
 private String read(InputStream in)throws Exception{if(in==null)return "{}";try(InputStream x=in;ByteArrayOutputStream b=new ByteArrayOutputStream()){byte[] z=new byte[2048];int n;while((n=x.read(z))!=-1)b.write(z,0,n);return b.toString("UTF-8");}}
 private JSONObject data(JSONObject r){JSONObject d=r.optJSONObject("data");return d==null?r:d;}
 private double num(JSONObject o,String...keys){for(String k:keys)if(o.has(k)&&!o.isNull(k)){Object v=o.opt(k);if(v instanceof Number)return ((Number)v).doubleValue();try{return Double.parseDouble(""+v);}catch(Exception e){}}return Double.NaN;}
 private String fmt(double n){return Double.isNaN(n)?"--":String.format(Locale.getDefault(),"%.2f",n);}
 private void apply(JSONObject r){JSONObject d=data(r);double s=num(d,"signal","raw","amplitude"),c=num(d,"confidence","confidence_percent"),z=num(d,"depth_cm","depth"),cp=num(d,"calibration_percent","calibration");if(!Double.isNaN(s))signal.setText(fmt(s));if(!Double.isNaN(c))confidence.setText(fmt(c)+"%");if(!Double.isNaN(z))depth.setText(fmt(z)+" سم");cal.setText(Double.isNaN(cp)?(d.optBoolean("calibrated",false)?"المعايرة مكتملة حسب ESP32":"المعايرة غير مؤكدة"):"المعايرة: "+fmt(cp)+"%");String state=d.optString("state","");if(state.equalsIgnoreCase("detecting")||d.optBoolean("detecting",false)){running=true;start.setText("إيقاف الكشف");}else if(state.equalsIgnoreCase("idle")||state.equalsIgnoreCase("stopped")){running=false;start.setText("بدء الكشف");}String j=r.toString();raw.setText(j.length()>2800?j.substring(0,2800)+"…":j);JSONArray windows=d.optJSONArray("windows");analysis.setText(windows!=null&&windows.length()>1?"وصلت "+windows.length()+" نافذة خام. حُفظت للتقييم؛ لا يوجد مصنف معادن مثبت بعد.":"البيانات الحالية لا تحتوي نوافذ اضمحلال متعددة كافية لتصنيف علمي.");if(!Double.isNaN(s)&&System.currentTimeMillis()-lastSaved>1800){latest=db.add(System.currentTimeMillis(),s,c,z,d.optBoolean("calibrated",false)?1:0,j);lastSaved=System.currentTimeMillis();history();}}
 private void command(String cmd){if(!linked)return;start.setEnabled(false);calibrate.setEnabled(false);net.execute(()->{try{JSONObject b=new JSONObject();b.put("command",cmd);request(host()+"/control","POST",b);ui.post(()->{if(cmd.equals("start"))running=true;if(cmd.equals("stop"))running=false;start.setText(running?"إيقاف الكشف":"بدء الكشف");start.setEnabled(true);calibrate.setEnabled(true);});}catch(Exception e){ui.post(()->{start.setEnabled(true);calibrate.setEnabled(true);Toast.makeText(this,"لم يقبل ESP32 الأمر",0).show();});}});}
 private void label(String value){if(latest<0){feedback.setText("لا توجد قراءة محفوظة بعد.");return;}db.feedback(latest,value);feedback.setText("سُجلت نتيجة آخر قراءة: "+value);history();}
 private void history(){if(history==null)return;StringBuilder b=new StringBuilder();try(Cursor c=db.latest()){while(c.moveToNext())b.append(new SimpleDateFormat("MM-dd HH:mm:ss",Locale.getDefault()).format(new Date(c.getLong(1)))).append(" | ").append(fmt(c.getDouble(2))).append(" | ").append(c.isNull(5)?"غير مؤكدة":c.getString(5)).append("\n");}history.setText(b.length()==0?"لا توجد تجارب بعد":b.toString());}
 private void export(){String s=db.csv();if(s.length()<40)return;Intent i=new Intent(Intent.ACTION_SEND);i.setType("text/csv");i.putExtra(Intent.EXTRA_SUBJECT,"Islam Detector Pro dataset");i.putExtra(Intent.EXTRA_TEXT,s);startActivity(Intent.createChooser(i,"تصدير قاعدة التجارب"));}
 private int dp(float n){return (int)(n*getResources().getDisplayMetrics().density+.5f);}private LinearLayout.LayoutParams lp(){return new LinearLayout.LayoutParams(-1,-2);}private void add(LinearLayout p,View v,int top){LinearLayout.LayoutParams a=lp();a.topMargin=dp(top);p.addView(v,a);}
 private GradientDrawable bg(int c){GradientDrawable d=new GradientDrawable();d.setColor(c);d.setCornerRadius(dp(13));d.setStroke(dp(1),0xff2b435e);return d;}
 private LinearLayout card(){LinearLayout l=new LinearLayout(this);l.setOrientation(1);l.setPadding(dp(12),dp(12),dp(12),dp(12));l.setBackground(bg(0xff122238));return l;}
 private TextView t(String s,int size,int color,boolean bold){TextView v=new TextView(this);v.setText(s);v.setTextSize(size);v.setTextColor(color);if(bold)v.setTypeface(Typeface.DEFAULT,1);return v;}
 private Button button(String s,int c){Button b=new Button(this);b.setText(s);b.setTextColor(-1);b.setAllCaps(false);b.setTextSize(13);b.setBackground(bg(c));return b;}
 @Override protected void onDestroy(){dead=true;ui.removeCallbacksAndMessages(null);net.shutdownNow();db.close();super.onDestroy();}
 private static class Store extends SQLiteOpenHelper{
  Store(Context c){super(c,"islam_detector_pro.db",null,1);}public void onCreate(SQLiteDatabase d){d.execSQL("CREATE TABLE samples(id INTEGER PRIMARY KEY AUTOINCREMENT,ts INTEGER,signal REAL,confidence REAL,depth REAL,feedback TEXT,raw TEXT)");}
  public void onUpgrade(SQLiteDatabase d,int a,int b){}
  long add(long ts,double s,double c,double z,int cal,String raw){ContentValues v=new ContentValues();v.put("ts",ts);v.put("signal",s);if(!Double.isNaN(c))v.put("confidence",c);if(!Double.isNaN(z))v.put("depth",z);v.put("raw",raw);return getWritableDatabase().insert("samples",null,v);}
  void feedback(long id,String f){ContentValues v=new ContentValues();v.put("feedback",f);getWritableDatabase().update("samples",v,"id=?",new String[]{""+id});}
  Cursor latest(){return getReadableDatabase().rawQuery("SELECT id,ts,signal,confidence,depth,feedback FROM samples ORDER BY ts DESC LIMIT 8",null);}
  String csv(){StringBuilder b=new StringBuilder("id,timestamp,signal,confidence,depth,feedback,raw_json\n");try(Cursor c=getReadableDatabase().rawQuery("SELECT id,ts,signal,confidence,depth,feedback,raw FROM samples ORDER BY ts",null)){while(c.moveToNext()){for(int i=0;i<7;i++){if(i>0)b.append(',');String x=c.isNull(i)?"":c.getString(i).replace("\"","\"\"");b.append('"').append(x).append('"');}b.append('\n');}}return b.toString();}
 }
}