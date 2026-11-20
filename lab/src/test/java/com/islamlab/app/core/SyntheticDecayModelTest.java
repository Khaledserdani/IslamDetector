package com.islamlab.app.core;

import org.junit.Test;
import static org.junit.Assert.*;

public class SyntheticDecayModelTest {
    @Test public void createsAllEightConfiguredWindows() {
        SyntheticDecayModel.Result r = SyntheticDecayModel.simulate(1000, 24, 0);
        assertEquals(8, r.samples.length);
        assertEquals(8.0, r.samples[0].timeUs, 0.0);
        assertEquals(100.0, r.samples[7].timeUs, 0.0);
    }

    @Test public void matchesExponentialReferenceWhenNoiseIsZero() {
        SyntheticDecayModel.Result r = SyntheticDecayModel.simulate(1000, 24, 0);
        assertEquals(1000.0 * Math.exp(-8.0 / 24.0), r.samples[0].signalMv, 1e-9);
        assertEquals(r.samples[0].signalMv, r.samples[0].totalMv, 0.0);
    }

    @Test public void isDeterministicForRepeatableExperiments() {
        SyntheticDecayModel.Result a = SyntheticDecayModel.simulate(900, 30, 2);
        SyntheticDecayModel.Result b = SyntheticDecayModel.simulate(900, 30, 2);
        for (int i = 0; i < a.samples.length; i++) {
            assertEquals(a.samples[i].totalMv, b.samples[i].totalMv, 0.0);
        }
    }

    @Test(expected = IllegalArgumentException.class)
    public void rejectsNonPhysicalTestParameters() {
        SyntheticDecayModel.simulate(100, 0, 1);
    }

    @Test public void matchesRecordedTau72Noise10Experiment() {
        SyntheticDecayModel.Result r = SyntheticDecayModel.simulate(1000, 72, 10);
        double[] expectedTotals = {
                895.255, 853.105, 787.190, 718.011,
                603.315, 472.684, 373.170, 243.052
        };
        for (int i = 0; i < expectedTotals.length; i++) {
            assertEquals(expectedTotals[i], r.samples[i].totalMv, 0.0006);
        }
    }

    @Test public void matchesRecordedTau72Noise20Experiment() {
        SyntheticDecayModel.Result r = SyntheticDecayModel.simulate(1000, 72, 20);
        double[] expectedTotals = {
                895.671, 859.729, 773.644, 719.490,
                600.100, 459.696, 378.461, 236.753
        };
        for (int i = 0; i < expectedTotals.length; i++) {
            assertEquals(expectedTotals[i], r.samples[i].totalMv, 0.0006);
        }
        double[] totals = new double[r.samples.length];
        for (int i = 0; i < r.samples.length; i++) totals[i] = r.samples[i].totalMv;
        double[] stats = com.islamlab.app.LabMath.summarize(totals);
        assertEquals(236.75266470270705, stats[0], 1e-9);
        assertEquals(895.6710341154962, stats[1], 1e-9);
        assertEquals(615.4429622039262, stats[2], 1e-9);
        assertEquals(658.9183694127892, stats[3], 1e-9);
        assertEquals(223.0795823632406, stats[4], 1e-9);
    }

}
