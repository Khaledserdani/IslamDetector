package com.islamfreeagent.app;

import android.content.Context;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.Set;

/** Strict allowlisted router for deterministic on-device laboratory engines. */
final class AgentLabRunner {
    static final String DC_LAB_ID = "dc_resistive_network";
    static final String DC_ENGINE_VERSION = "android-dc-mna-1.0.0";
    private static final int MAX_RESISTORS = 100;
    private static final int MAX_NODES = 32;

    private AgentLabRunner() {}

    static void validate(JSONObject plan) throws Exception {
        if (plan == null) throw new IllegalArgumentException("خطة المختبر فارغة");
        requireKeys(plan, "action", "lab_id", "ground", "source_node", "source_voltage_v", "resistors");
        if (!"simulate_lab".equals(plan.getString("action"))) {
            throw new IllegalArgumentException("إجراء المختبر غير مسموح");
        }
        if (!DC_LAB_ID.equals(plan.getString("lab_id"))) {
            throw new IllegalArgumentException("هذا المختبر غير منفذ على الهاتف حالياً");
        }
        String ground = validNode(plan.getString("ground"));
        String source = validNode(plan.getString("source_node"));
        if (ground.equals(source)) throw new IllegalArgumentException("عقدة المصدر لا يمكن أن تكون الأرضي");
        double volts = finite(plan.getDouble("source_voltage_v"), "جهد المصدر");
        if (Math.abs(volts) > 10000.0) throw new IllegalArgumentException("جهد المصدر خارج الحد الآمن للمحاكاة");
        JSONArray rows = plan.getJSONArray("resistors");
        if (rows.length() < 1 || rows.length() > MAX_RESISTORS) {
            throw new IllegalArgumentException("يسمح من مقاومة واحدة إلى 100 مقاومة");
        }
        Set<String> nodes = new HashSet<>();
        nodes.add(ground); nodes.add(source);
        ArrayList<AgentDcLab.Resistor> resistors = new ArrayList<>();
        for (int i = 0; i < rows.length(); i++) {
            JSONObject row = rows.getJSONObject(i);
            requireKeys(row, "a", "b", "ohms");
            String a = validNode(row.getString("a"));
            String b = validNode(row.getString("b"));
            if (a.equals(b)) throw new IllegalArgumentException("طرفا المقاومة يجب أن يكونا عقدتين مختلفتين");
            double ohms = finite(row.getDouble("ohms"), "المقاومة");
            if (ohms <= 0.0 || ohms > 1.0e12) throw new IllegalArgumentException("قيمة المقاومة خارج الحدود");
            nodes.add(a); nodes.add(b);
            resistors.add(new AgentDcLab.Resistor(a, b, ohms));
        }
        if (nodes.size() > MAX_NODES) throw new IllegalArgumentException("تجاوزت الدارة حد 32 عقدة");
        // Validate topology and solvability before the user sees the confirmation.
        AgentDcLab.solve(ground, source, volts, resistors);
    }

    static JSONObject execute(Context context, JSONObject plan) throws Exception {
        validate(plan);
        String ground = plan.getString("ground");
        String source = plan.getString("source_node");
        double volts = plan.getDouble("source_voltage_v");
        JSONArray rows = plan.getJSONArray("resistors");
        ArrayList<AgentDcLab.Resistor> resistors = new ArrayList<>();
        for (int i = 0; i < rows.length(); i++) {
            JSONObject row = rows.getJSONObject(i);
            resistors.add(new AgentDcLab.Resistor(
                    row.getString("a"), row.getString("b"), row.getDouble("ohms")));
        }
        AgentDcLab.Result solved = AgentDcLab.solve(ground, source, volts, resistors);
        JSONObject voltages = new JSONObject();
        for (java.util.Map.Entry<String, Double> entry : solved.nodeVoltages.entrySet()) {
            voltages.put(entry.getKey(), entry.getValue());
        }
        boolean verified = solved.maximumKclResidualAmps <= 1.0e-8;
        JSONObject inputs = new JSONObject(plan.toString());
        JSONObject outputs = new JSONObject();
        outputs.put("node_voltages_v", voltages);
        outputs.put("source_current_a", solved.sourceCurrentAmps);
        outputs.put("max_kcl_residual_a", solved.maximumKclResidualAmps);
        outputs.put("verified_numerically", verified);
        String verification = "فحص KCL؛ أقصى متبقي تيار = "
                + String.format(java.util.Locale.US, "%.6e A", solved.maximumKclResidualAmps);
        String runId = AgentLabRunStore.record(context, DC_LAB_ID, DC_ENGINE_VERSION,
                "agent_confirmed", inputs, outputs, verified, verification);
        JSONObject result = new JSONObject();
        result.put("action", "simulate_lab");
        result.put("lab_id", DC_LAB_ID);
        result.put("run_id", runId);
        result.put("engine_version", DC_ENGINE_VERSION);
        result.put("verified", verified);
        result.put("verification", verification);
        result.put("outputs", outputs);
        return result;
    }

    private static String validNode(String value) {
        if (value == null || !value.matches("[A-Za-z0-9_][A-Za-z0-9_.-]{0,31}")) {
            throw new IllegalArgumentException("اسم العقدة غير صالح؛ استخدم حروفاً وأرقاماً ورموزاً بسيطة");
        }
        return value;
    }

    private static double finite(double value, String name) {
        if (Double.isNaN(value) || Double.isInfinite(value)) {
            throw new IllegalArgumentException(name + " يجب أن يكون رقماً محدوداً");
        }
        return value;
    }

    private static void requireKeys(JSONObject object, String... expected) {
        Set<String> keys = new HashSet<>();
        java.util.Iterator<String> iterator = object.keys();
        while (iterator.hasNext()) keys.add(iterator.next());
        Set<String> required = new HashSet<>(java.util.Arrays.asList(expected));
        if (!keys.equals(required)) throw new IllegalArgumentException("حقول خطة المختبر غير مطابقة");
    }
}
