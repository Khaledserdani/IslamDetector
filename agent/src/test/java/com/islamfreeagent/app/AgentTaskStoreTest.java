package com.islamfreeagent.app;

import android.content.Context;

import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;

import java.util.List;

import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
public class AgentTaskStoreTest {
    private Context context;
    private AgentTaskStore store;

    @Before public void setUp() {
        context = RuntimeEnvironment.getApplication();
        context.getSharedPreferences("islam_free_agent", Context.MODE_PRIVATE)
                .edit().clear().commit();
        store = new AgentTaskStore(context);
    }

    @Test public void addsAndRestoresTaskFromLocalStorage() {
        AgentTaskStore.Task created = store.add("فحص تشغيل المدير");
        List<AgentTaskStore.Task> restored = new AgentTaskStore(context).all();
        assertEquals(1, restored.size());
        assertEquals(created.id, restored.get(0).id);
        assertEquals("فحص تشغيل المدير", restored.get(0).title);
        assertFalse(restored.get(0).done);
    }

    @Test public void completionAndDeletionArePersisted() {
        AgentTaskStore.Task task = store.add("اختبار الحفظ");
        assertTrue(store.setDone(task.id, true));
        assertTrue(new AgentTaskStore(context).all().get(0).done);
        assertTrue(store.delete(task.id));
        assertTrue(store.all().isEmpty());
    }

    @Test public void preservesLongTitleAndSeparateLongDescription() {
        String title = new String(new char[1200]).replace('\0', 'ع');
        String description = "تفاصيل المهمة: " + new String(new char[12000]).replace('\0', 'س');
        AgentTaskStore.Task task = store.add(title, description);
        AgentTaskStore.Task restored = new AgentTaskStore(context).all().get(0);
        assertEquals(title, restored.title);
        assertEquals(description, restored.description);
        assertEquals(task.id, restored.id);
    }

    @Test public void rejectsEmptyTitleAndDescription() {
        try { store.add("   "); fail("empty title should be rejected"); }
        catch (IllegalArgumentException expected) { assertEquals("عنوان المهمة فارغ", expected.getMessage()); }
        try { store.add("عنوان", "  "); fail("empty description should be rejected"); }
        catch (IllegalArgumentException expected) { assertEquals("وصف المهمة فارغ", expected.getMessage()); }
    }

    @Test public void rejectsOnlyBeyondDocumentedStorageLimit() {
        try {
            store.add(new String(new char[AgentTaskStore.MAX_TITLE_CHARS + 1]).replace('\0', 'x'));
            fail("title beyond safety bound should be rejected");
        } catch (IllegalArgumentException expected) { assertTrue(expected.getMessage().contains("8192")); }
    }

    @Test public void corruptStoredJsonDoesNotBecomeExecutableTasks() {
        context.getSharedPreferences("islam_free_agent", Context.MODE_PRIVATE)
                .edit().putString("tasks_json", "{broken").commit();
        assertTrue(store.all().isEmpty());
    }

    @Test public void taskQueueHasABoundedCapacity() {
        for (int i = 0; i < AgentTaskStore.MAX_TASKS; i++) {
            store.add("مهمة " + i);
        }
        try {
            store.add("مهمة إضافية");
            fail("task capacity should be enforced");
        } catch (IllegalStateException expected) {
            assertTrue(expected.getMessage().contains("500"));
        }
        assertEquals(AgentTaskStore.MAX_TASKS, store.all().size());
    }

}
