package com.islamfreeagent.app;

import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.TextView;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.android.controller.ActivityController;

import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
public class MainActivitySmokeTest {
    @Test public void activityLaunchesAndShowsOfflineLabControls() {
        try (ActivityController<MainActivity> controller =
                     Robolectric.buildActivity(MainActivity.class).setup()) {
            MainActivity activity = controller.get();
            View root = activity.findViewById(android.R.id.content);
            assertNotNull(root);
            assertTrue(findText(root, "ISLAM FREE AGENT"));
            assertTrue(findText(root, "مختبر DC المحلي — يعمل دون كمبيوتر أو إنترنت"));
            assertTrue(findButton(root, "تشغيل محاكاة DC على الهاتف"));
            assertTrue(findButton(root, "حفظ التجربة لتعمل ليلاً"));
            assertTrue(findButton(root, "تفعيل الجدولة الليلية 20:00–06:00"));
            assertTrue(findButton(root, "إيقاف الجدولة الليلية"));
            assertTrue(findText(root, "الذكاء الاصطناعي المحلي — Qwen3 0.6B"));
            assertTrue(findButton(root, "تنزيل النموذج المجاني عبر الإنترنت"));
            assertTrue(findTextContaining(root, "يمكن تنزيله عبر Wi-Fi أو بيانات الهاتف"));
            assertTrue(findButton(root, "التحقق من النموذج وتشغيل الذكاء المحلي"));
            assertTrue(findText(root, "اكتب رسالتك أو سؤالك هنا"));
            assertTrue(findButton(root, "إرسال إلى الذكاء المحلي"));
            assertTrue(findButton(root, "تنفيذ"));
            assertFalse(findText(root, "ربط محرك الكمبيوتر"));
            assertFalse(findText(root, "اطلب اقتراحاً من Ollama"));
        }
    }

    private static boolean findText(View view, String expected) {
        if (view instanceof TextView
                && expected.contentEquals(((TextView) view).getText())) return true;
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                if (findText(group.getChildAt(i), expected)) return true;
            }
        }
        return false;
    }

    private static boolean findTextContaining(View view, String expected) {
        if (view instanceof TextView
                && ((TextView) view).getText().toString().contains(expected)) return true;
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                if (findTextContaining(group.getChildAt(i), expected)) return true;
            }
        }
        return false;
    }

    private static boolean findButton(View view, String expected) {
        if (view instanceof Button
                && expected.contentEquals(((Button) view).getText())) return true;
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                if (findButton(group.getChildAt(i), expected)) return true;
            }
        }
        return false;
    }
}
