package com.islamfreeagent.app;

import android.content.Context;

import org.json.JSONObject;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;

import java.util.Arrays;

import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
public class AgentLabQueueTest {
    private Context context;

    @Before public void setUp() {
        context = RuntimeEnvironment.getApplication();
        context.getSharedPreferences("islam_free_agent_lab", Context.MODE_PRIVATE)
                .edit().clear().commit();
    }

    @Test public void queuedExperimentPersistsUntilWorkerMarksItComplete() throws Exception {
        String id = AgentLabQueue.enqueue(context, 10.0, Arrays.asList(
                new AgentDcLab.Resistor("vcc", "mid", 1000.0),
                new AgentDcLab.Resistor("mid", "0", 1000.0)));
        JSONObject pending = AgentLabQueue.nextPending(context);
        assertNotNull(pending);
        assertEquals(id, pending.getString("id"));
        assertEquals("pending", pending.getString("status"));

        JSONObject result = new JSONObject().put("mid_voltage_v", 5.0);
        AgentLabQueue.finish(context, id, result, null);
        assertNull(AgentLabQueue.nextPending(context));
        assertTrue(AgentLabQueue.summary(context).contains("مكتملة: 1"));
    }

    @Test public void failedExperimentIsRecordedAndNotRepeated() throws Exception {
        String id = AgentLabQueue.enqueue(context, 5.0, Arrays.asList(
                new AgentDcLab.Resistor("vcc", "0", 1000.0)));
        AgentLabQueue.finish(context, id, null, "simulated failure");
        assertNull(AgentLabQueue.nextPending(context));
        assertTrue(AgentLabQueue.summary(context).contains("فاشلة: 1"));
    }

    @Test public void invalidCircuitCannotEnterPersistentQueue() {
        try {
            AgentLabQueue.enqueue(context, 5.0, Arrays.asList(
                    new AgentDcLab.Resistor("vcc", "floating", 1000.0)));
            fail("singular circuit must be rejected");
        } catch (IllegalArgumentException expected) {
            assertTrue(AgentLabQueue.summary(context).contains("انتظار: 0"));
        }
    }
}
