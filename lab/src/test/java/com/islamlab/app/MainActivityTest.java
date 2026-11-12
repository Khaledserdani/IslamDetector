package com.islamlab.app;

import android.app.Activity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.android.controller.ActivityController;

import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
public class MainActivityTest {
    @Test public void activityLaunchesAndShowsSyntheticLabMode() {
        ActivityController<MainActivity> controller = Robolectric.buildActivity(MainActivity.class)
                .create().start().resume();
        try {
            Activity activity = controller.get();
            assertNotNull(activity);
            View content = activity.findViewById(android.R.id.content);
            assertNotNull(content);
            assertTrue(content instanceof ViewGroup);
            assertTrue(((ViewGroup) content).getChildCount() > 0);
            assertTrue(containsText((ViewGroup) content, "مولّد إشارة اصطناعية"));
        } finally {
            controller.pause().stop().destroy();
        }
    }

    private static boolean containsText(ViewGroup parent, String expected) {
        for (int i = 0; i < parent.getChildCount(); i++) {
            View child = parent.getChildAt(i);
            if (child instanceof TextView
                    && ((TextView) child).getText().toString().contains(expected)) return true;
            if (child instanceof ViewGroup && containsText((ViewGroup) child, expected)) return true;
        }
        return false;
    }
}
