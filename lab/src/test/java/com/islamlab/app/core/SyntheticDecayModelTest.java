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
}
