package com.islamfreeagent.app;

import android.content.Context;

import androidx.annotation.NonNull;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Calendar;
import java.util.TimeZone;
import java.util.ArrayList;

public final class AgentLabWorker extends Worker {
    public AgentLabWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    @NonNull @Override public Result doWork() {
        Calendar algiersTime = Calendar.getInstance(TimeZone.getTimeZone("Africa/Algiers"));
        int minuteOfDay = algiersTime.get(Calendar.HOUR_OF_DAY) * 60
                + algiersTime.get(Calendar.MINUTE);
        if (!AgentWorkWindow.isOpen(minuteOfDay,
                AgentWorkWindow.DEFAULT_START, AgentWorkWindow.DEFAULT_END)) {
            return Result.success();
        }
        JSONObject job = AgentLabQueue.nextPending(getApplicationContext());
        if (job == null) return Result.success();
        String id = job.optString("id", "");
        try {
            AgentLabQueue.validateJob(job);
            JSONArray rows = job.getJSONArray("resistors");
            ArrayList<AgentDcLab.Resistor> resistors = new ArrayList<>();
            for (int i = 0; i < rows.length(); i++) {
                JSONObject row = rows.getJSONObject(i);
                resistors.add(new AgentDcLab.Resistor(
                        row.getString("a"), row.getString("b"), row.getDouble("ohms")));
            }
            AgentDcLab.Result solved = AgentDcLab.solve(
                    "0", "vcc", job.getDouble("volts"), resistors);
            JSONObject output = new JSONObject();
            JSONObject voltages = new JSONObject();
            for (java.util.Map.Entry<String, Double> entry : solved.nodeVoltages.entrySet()) {
                voltages.put(entry.getKey(), entry.getValue());
            }
            output.put("node_voltages_v", voltages);
            output.put("source_current_a", solved.sourceCurrentAmps);
            output.put("max_kcl_residual_a", solved.maximumKclResidualAmps);
            boolean numericallyVerified = solved.maximumKclResidualAmps <= 1.0e-8;
            JSONObject inputs = new JSONObject();
            inputs.put("lab_id", AgentLabRunner.DC_LAB_ID);
            inputs.put("ground", "0");
            inputs.put("source_node", "vcc");
            inputs.put("source_voltage_v", job.getDouble("volts"));
            inputs.put("resistors", rows);
            String verification = "فحص KCL؛ أقصى متبقي تيار = "
                    + String.format(java.util.Locale.US, "%.6e A", solved.maximumKclResidualAmps);
            String runId = AgentLabRunStore.record(getApplicationContext(),
                    AgentLabRunner.DC_LAB_ID, AgentLabRunner.DC_ENGINE_VERSION,
                    "scheduled_worker", inputs, output, numericallyVerified, verification);
            output.put("run_id", runId);
            AgentLabQueue.finish(getApplicationContext(), id, output, null);
            return Result.success();
        } catch (Exception error) {
            AgentLabQueue.finish(getApplicationContext(), id, null,
                    error.getMessage() == null ? error.getClass().getSimpleName() : error.getMessage());
            return Result.success();
        }
    }
}
