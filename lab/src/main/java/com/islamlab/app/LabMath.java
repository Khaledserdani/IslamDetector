package com.islamlab.app;

import java.util.ArrayList;
import java.util.List;

public final class LabMath {
    private LabMath() {}

    public static double[] parseSamples(String raw) {
        if (raw == null || raw.trim().isEmpty()) return new double[0];
        String[] parts = raw.trim().split("[,;\\s]+");
        List<Double> values = new ArrayList<>();
        for (String part : parts) {
            if (part.isEmpty()) continue;
            double value = Double.parseDouble(part);
            if (Double.isNaN(value) || Double.isInfinite(value)) {
                throw new IllegalArgumentException("العينة تحتوي قيمة غير صالحة");
            }
            values.add(value);
        }
        double[] result = new double[values.size()];
        for (int i = 0; i < values.size(); i++) result[i] = values.get(i);
        return result;
    }

    public static double[] summarize(double[] samples) {
        if (samples == null || samples.length == 0) {
            throw new IllegalArgumentException("أدخل عينة واحدة على الأقل");
        }
        double min = samples[0], max = samples[0], sum = 0;
        for (double v : samples) {
            if (Double.isNaN(v) || Double.isInfinite(v)) {
                throw new IllegalArgumentException("العينة تحتوي قيمة غير صالحة");
            }
            min = Math.min(min, v);
            max = Math.max(max, v);
            sum += v;
        }
        double mean = sum / samples.length;
        double variance = 0;
        for (double v : samples) variance += (v - mean) * (v - mean);
        variance /= samples.length;
        return new double[]{min, max, mean, max - min, Math.sqrt(variance), samples.length};
    }

    public static long totalWindowMicros(int blankingUs, int sampleDelayUs, int sampleCount, int intervalUs) {
        if (blankingUs < 0 || sampleDelayUs < 0 || sampleCount < 1 || intervalUs < 1) {
            throw new IllegalArgumentException("تحقق من قيم التوقيت");
        }
        return (long) blankingUs + sampleDelayUs + (long) sampleCount * intervalUs;
    }
}
