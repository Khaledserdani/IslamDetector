package com.islamfreeagent.app;

import android.content.Context;

import androidx.annotation.NonNull;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalTime;
import java.time.ZoneId;
import java.util.ArrayList;

public final class AgentLabWorker extends Worker {
    public AgentLabWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    @NonNull @Override public Result doWork() {
        LocalTime algiersTime = LocalTime.now(ZoneId.of("Africa/Algiers"));
        if (!AgentWorkWindow.isOpen(algiersTime,
                AgentWorkWindow.DEFAULT_START, AgentWorkWindow.DEFAULT_END)) {
            return Result.success();
        }
        JSONObject job = AgentLabQueue.nextPending(getApplicationContext());
        if (job == null) return Result.success();
        String id = job.optString("id", "");
        try {
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
            AgentLabQueue.finish(getApplicationContext(), id, output, null);
            return Result.success();
        } catch (Exception error) {
            AgentLabQueue.finish(getApplicationContext(), id, null,
                    error.getMessage() == null ? error.getClass().getSimpleName() : error.getMessage());
            return Result.success();
        }
    }
}
