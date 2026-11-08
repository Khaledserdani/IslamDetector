
package com.islamdetector.app;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Color;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Button;

public class MainActivity extends Activity {

    private LinearLayout layout;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setGravity(Gravity.CENTER);
        layout.setPadding(30, 40, 30, 40);
        layout.setBackgroundColor(Color.rgb(12, 20, 32));

        TextView title = new TextView(this);
        title.setText("ISLAM DETECTOR");
        title.setTextSize(28);
        title.setTextColor(Color.WHITE);
        title.setGravity(Gravity.CENTER);
        layout.addView(title);

        TextView status = new TextView(this);
        status.setText("المستكشف الذكي\n\nفي انتظار الاتصال بالجهاز");
        status.setTextSize(20);
        status.setTextColor(Color.LTGRAY);
        status.setGravity(Gravity.CENTER);
        layout.addView(status);

        Button connect = new Button(this);
        connect.setText("الاتصال بالجهاز");
        layout.addView(connect);

        Button detect = new Button(this);
        detect.setText("بدء الكشف");
        layout.addView(detect);

        Button settings = new Button(this);
        settings.setText("الإعدادات");
        layout.addView(settings);

        setContentView(layout);
    }
}
