package com.islamlab.app.core;

/**
 * Reproducible synthetic waveform fixture.
 * This is a software test signal, not a physical PI target/soil model.
 */
public final class SyntheticDecayModel {
    public static final String MODEL_NAME = "exponential-decay-fixture";
    public static final String MODEL_VERSION = "0.2.0";
    public static final double[] WINDOWS_US = {8, 12, 16, 24, 36, 52, 72, 100};

    private SyntheticDecayModel() {}

    public static Result simulate(double amplitudeMv, double tauUs, double nominalNoiseMv) {
        if (!Double.isFinite(amplitudeMv) || !Double.isFinite(tauUs) ||
                !Double.isFinite(nominalNoiseMv) || amplitudeMv <= 0 ||
                tauUs <= 0 || nominalNoiseMv < 0 ||
                amplitudeMv > 1_000_000 || tauUs > 1_000_000 ||
                nominalNoiseMv > 1_000_000) {
            throw new IllegalArgumentException("Invalid synthetic waveform parameters");
        }
        Sample[] samples = new Sample[WINDOWS_US.length];
        for (int i = 0; i < WINDOWS_US.length; i++) {
            double t = WINDOWS_US[i];
            double signal = amplitudeMv * Math.exp(-t / tauUs);
            double noise = noiseAt(t, nominalNoiseMv);
            samples[i] = new Sample(t, signal, noise, signal + noise);
        }
        return new Result(amplitudeMv, tauUs, nominalNoiseMv, samples);
    }

    private static double noiseAt(double t, double nominalNoiseMv) {
        // Deterministic multi-tone test disturbance: repeatable, not stochastic noise.
        return nominalRmsMv * (Math.sin(0.73 * t) + Math.sin(1.17 * t) +
                Math.sin(1.91 * t)) / Math.sqrt(1.5);
    }

    public static final class Sample {
        public final double timeUs;
        public final double signalMv;
        public final double noiseMv;
        public final double totalMv;

        Sample(double timeUs, double signalMv, double noiseMv, double totalMv) {
            this.timeUs = timeUs;
            this.signalMv = signalMv;
            this.noiseMv = noiseMv;
            this.totalMv = totalMv;
        }
    }

    public static final class Result {
        public final double amplitudeMv;
        public final double tauUs;
        public final double nominalNoiseMv;
        public final String modelName = MODEL_NAME;
        public final String modelVersion = MODEL_VERSION;
        public final String sourceType = "synthetic";
        public final Sample[] samples;

        Result(double amplitudeMv, double tauUs, double nominalNoiseMv, Sample[] samples) {
            this.amplitudeMv = amplitudeMv;
            this.tauUs = tauUs;
            this.nominalNoiseMv = nominalNoiseMv;
            this.samples = samples.clone();
        }

        public double valueAt(double timeUs) {
            double signal = amplitudeMv * Math.exp(-timeUs / tauUs);
            return signal + noiseAt(timeUs, nominalNoiseMv);
        }
    }
}
