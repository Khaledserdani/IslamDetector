package com.islamfreeagent.app;

import android.content.Context;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;

import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
public class AgentLabRunnerTest {
    private Context context;

    @Before public void clearHistory() {
        context = RuntimeEnvironment.getApplication();
        context.getSharedPreferences("islam_free_agent_lab_history", Context.MODE_PRIVATE)
                .edit().clear().commit();
    }

    private JSONObject dividerPlan() throws Exception {
        return new JSONObject()
                .put("action", "simulate_lab")
                .put("lab_id", "dc_resistive_network")
                .put("ground", "0")
                .put("source_node", "vcc")
                .put("source_voltage_v", 10.0)
                .put("resistors", new JSONArray()
                        .put(new JSONObject().put("a", "vcc").put("b", "mid").put("ohms", 1000.0))
                        .put(new JSONObject().put("a", "mid").put("b", "0").put("ohms", 1000.0)));
    }

    @Test public void approvedAgentPlanRunsDcAndStoresProvenance() throws Exception {
        JSONObject plan = dividerPlan();
        AgentTaskToolRunner.validate(plan);
        JSONObject result = new AgentTaskToolRunner(context).execute(plan);
        assertTrue(result.getBoolean("verified"));
        assertEquals("dc_resistive_network", result.getString("lab_id"));
        assertEquals(5.0, result.getJSONObject("outputs")
                .getJSONObject("node_voltages_v").getDouble("mid"), 1e-9);
        assertEquals(0.005, result.getJSONObject("outputs")
                .getDouble("source_current_a"), 1e-9);

        JSONArray history = AgentLabRunStore.recent(context, 10);
        assertEquals(1, history.length());
        JSONObject run = history.getJSONObject(0);
        assertEquals(result.getString("run_id"), run.getString("run_id"));
        assertEquals(AgentLabRunner.DC_ENGINE_VERSION, run.getString("engine_version"));
        assertEquals("agent_confirmed", run.getString("source"));
        assertTrue(run.getBoolean("verified"));
        assertEquals("simulate_lab", run.getJSONObject("inputs").getString("action"));
    }

    @Test public void rejectsUnknownLabAndExtraFields() throws Exception {
        JSONObject unknown = dividerPlan();
        unknown.put("lab_id", "spice_general");
        try {
            AgentLabRunner.validate(unknown);
            fail("unimplemented laboratory must not run");
        } catch (IllegalArgumentException expected) {
            assertTrue(expected.getMessage().contains("غير منفذ"));
        }

        JSONObject extra = dividerPlan();
        extra.put("shell", "not allowed");
        try {
            AgentLabRunner.validate(extra);
            fail("extra plan fields must be rejected");
        } catch (IllegalArgumentException expected) {
            assertTrue(expected.getMessage().contains("حقول"));
        }
    }

    @Test public void queuedExperimentsUseTheSameStrictRunnerLimits() throws Exception {
        java.util.ArrayList<AgentDcLab.Resistor> tooMany = new java.util.ArrayList<>();
        for (int i = 0; i < 101; i++) {
            tooMany.add(new AgentDcLab.Resistor("vcc", "0", 1000.0));
        }
        try {
            AgentLabQueue.enqueue(context, 5.0, tooMany);
            fail("queue must reject more than 100 resistors");
        } catch (IllegalArgumentException expected) {
            assertTrue(expected.getMessage().contains("100"));
        }
        assertTrue(AgentLabQueue.summary(context).contains("انتظار: 0"));

        java.util.ArrayList<AgentDcLab.Resistor> valid = new java.util.ArrayList<>();
        valid.add(new AgentDcLab.Resistor("vcc", "0", 1000.0));
        try {
            AgentLabQueue.enqueue(context, 10001.0, valid);
            fail("queue must reject source voltage outside runner limits");
        } catch (IllegalArgumentException expected) {
            assertTrue(expected.getMessage().contains("جهد المصدر"));
        }
        assertTrue(AgentLabQueue.summary(context).contains("انتظار: 0"));
    }

    @Test public void completedQueueEntriesArePrunedBeforeRejectingNewWork() throws Exception {
        java.util.ArrayList<AgentDcLab.Resistor> one = new java.util.ArrayList<>();
        one.add(new AgentDcLab.Resistor("vcc", "0", 1000.0));
        String firstId = null;
        for (int i = 0; i < 100; i++) {
            String id = AgentLabQueue.enqueue(context, 5.0, one);
            if (i == 0) firstId = id;
        }
        assertTrue(AgentLabQueue.summary(context).contains("انتظار: 100"));
        AgentLabQueue.finish(context, firstId, new JSONObject().put("ok", true), null);
        AgentLabQueue.enqueue(context, 5.0, one);
        JSONArray queue = new JSONArray(context.getSharedPreferences(
                "islam_free_agent_lab", Context.MODE_PRIVATE).getString("dc_queue", "[]"));
        assertEquals(100, queue.length());
        assertTrue(AgentLabQueue.summary(context).contains("انتظار: 100"));
        for (int i = 0; i < queue.length(); i++) {
            assertNotEquals(firstId, queue.getJSONObject(i).getString("id"));
        }
    }

    @Test public void rejectsSingularNetworkBeforeExecution() throws Exception {
        JSONObject plan = new JSONObject()
                .put("action", "simulate_lab")
                .put("lab_id", "dc_resistive_network")
                .put("ground", "0")
                .put("source_node", "vcc")
                .put("source_voltage_v", 5.0)
                .put("resistors", new JSONArray()
                        .put(new JSONObject().put("a", "vcc").put("b", "floating").put("ohms", 1000.0)));
        try {
            AgentLabRunner.validate(plan);
            fail("floating network must not be accepted");
        } catch (IllegalArgumentException expected) {
            assertTrue(expected.getMessage().contains("singular"));
        }
        assertEquals(0, AgentLabRunStore.recent(context, 10).length());
    }
}
