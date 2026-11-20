package com.islamfreeagent.app;

import android.content.Context;

import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;

import java.util.concurrent.TimeUnit;

/** Best-effort recurring worker; Android may defer execution for power management. */
final class AgentLabScheduler {
    private static final String UNIQUE_WORK = "islam_free_agent_night_lab";
    private AgentLabScheduler() {}

    static void enable(Context context) {
        PeriodicWorkRequest request = new PeriodicWorkRequest.Builder(
                AgentLabWorker.class, 15, TimeUnit.MINUTES).build();
        WorkManager.getInstance(context.getApplicationContext())
                .enqueueUniquePeriodicWork(UNIQUE_WORK, ExistingPeriodicWorkPolicy.KEEP, request);
    }

    static void disable(Context context) {
        WorkManager.getInstance(context.getApplicationContext()).cancelUniqueWork(UNIQUE_WORK);
    }
}
