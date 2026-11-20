package com.islamfreeagent.app;

import android.app.Activity;
import android.app.AlertDialog;
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

import java.util.List;

public class MainActivity extends Activity {
    private static final int BG = Color.rgb(8, 16, 29);
    private static final int PANEL = Color.rgb(19, 33, 51);
    private static final int MUTED = Color.rgb(157, 177, 199);
    private static final int GREEN = Color.rgb(34, 145, 116);
    private AgentTaskStore store;
    private LinearLayout taskList;
    private TextView countText;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        store = new AgentTaskStore(this);
        buildScreen();
        renderTasks();
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
        TextView noticeTitle = text("نسخة أولية — تعمل محلياً", 16, Color.rgb(255, 205, 120), true);
        notice.addView(noticeTitle, matchWrap());
        TextView noticeBody = text("إدارة المهام وحفظها على الهاتف جاهزان. محرك الذكاء الاصطناعي Ollama والاتصال بالمستودع لم يُربطا بعد؛ لن ندّعي أن المساعد ينفذ التحليلات تلقائياً.", 13, MUTED, false);
        LinearLayout.LayoutParams nb = matchWrap(); nb.topMargin = dp(8);
        notice.addView(noticeBody, nb);
        addPanel(page, notice, 18);

        LinearLayout status = panel();
        status.addView(text("حالة المدير", 16, Color.WHITE, true), matchWrap());
        TextView state = text("واجهة الهاتف: تعمل دون إنترنت", 14, Color.rgb(130, 220, 185), true);
        LinearLayout.LayoutParams st = matchWrap(); st.topMargin = dp(8);
        status.addView(state, st);
        TextView engine = text("محرك Ollama: غير مربوط", 13, MUTED, false);
        LinearLayout.LayoutParams en = matchWrap(); en.topMargin = dp(5);
        status.addView(engine, en);
        addPanel(page, status, 12);

        LinearLayout heading = new LinearLayout(this);
        heading.setGravity(Gravity.CENTER_VERTICAL);
        heading.setOrientation(LinearLayout.HORIZONTAL);
        TextView queueTitle = text("قائمة المهام", 19, Color.WHITE, true);
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

        TextView footer = text("البيانات تُحفظ محلياً على الهاتف. لا تُرسل أي مهمة إلى GitHub أو إلى نموذج ذكاء اصطناعي في هذه النسخة.", 12, MUTED, false);
        LinearLayout.LayoutParams fp = matchWrap(); fp.topMargin = dp(20);
        page.addView(footer, fp);
        setContentView(scroll);
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
