package com.islamlab.app;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Utilities for validating and summarizing user-supplied measurement samples. */
public final class ExperimentData {
    private ExperimentData() {}

    public static double[] parse(String raw) {
        if (raw == null || raw.trim().isEmpty()) throw new IllegalArgumentException("لا توجد بيانات");
        String[] rows = raw.trim().split("[\\r\\n,;\\t ]+");
        List<Double> values = new ArrayList<>();
        for (String token : rows) {
            if (token.isEmpty()) continue;
            String normalized = token.replace(',', '.');
            final double value;
            try { value = Double.parseDouble(normalized); }
            catch (NumberFormatException ex) { continue; }
            if (!Double.isFinite(value)) throw new IllegalArgumentException("توجد قراءة غير صالحة");
            values.add(value);
            if (values.size() > 100000) throw new IllegalArgumentException("عدد القراءات يتجاوز 100000");
        }
        if (values.size() < 2) throw new IllegalArgumentException("يلزم إدخال قراءتين على الأقل");
        double[] result = new double[values.size()];
        for (int i = 0; i < result.length; i++) result[i] = values.get(i);
        return result;
    }

    public static String toCsv(double[] values) {
        double[] stats = LabMath.summarize(values);
        StringBuilder out = new StringBuilder("source_type,user_measurement\\nunit,mV\\nindex,value\\n");
        for (int i = 0; i < values.length; i++) out.append(i + 1).append(',').append(String.format(Locale.US, "%.8f", values[i])).append('\\n');
        out.append(String.format(Locale.US, "count,%d\\nmin,%.8f\\nmax,%.8f\\nmean,%.8f\\nrange,%.8f\\nstddev,%.8f\\n", (int)stats[5], stats[0], stats[1], stats[2], stats[3], stats[4]));
        return out.toString();
    }
}