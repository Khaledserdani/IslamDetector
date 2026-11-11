package com.islamlab.app;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Validates manually entered samples and simple two-column CSV measurement files. */
public final class ExperimentData {
    private ExperimentData() {}

    public static double[] parse(String raw) {
        if (raw == null || raw.trim().isEmpty()) throw new IllegalArgumentException("لا توجد بيانات");
        List<Double> values = new ArrayList<>();
        String[] lines = raw.trim().split("\\r?\\n");
        boolean csvTable = raw.contains("\n") || raw.contains("\r");
        boolean hasTableHeader = raw.toLowerCase(Locale.ROOT).contains("index,value") || raw.toLowerCase(Locale.ROOT).contains("index;value");
        boolean inData = !hasTableHeader;
        for (String line : lines) {
            String row = line.trim();
            if (row.isEmpty()) {
                if (csvTable && inData) break;
                continue;
            }
            if (row.equalsIgnoreCase("index,value") || row.equalsIgnoreCase("index;value")) {
                inData = true;
                continue;
            }
            if (hasTableHeader && !inData) continue;
            String[] cells = row.split("[,;\\t]");
            if (hasTableHeader && cells.length >= 2) {
                addIfNumeric(cells[cells.length - 1].trim(), values);
            } else {
                String[] tokens = row.split("[,;\\t ]+");
                for (String token : tokens) addIfNumeric(token.trim(), values);
            }
            if (values.size() > 100000) throw new IllegalArgumentException("عدد القراءات يتجاوز 100000");
        }
        if (values.size() < 2) throw new IllegalArgumentException("يلزم إدخال قراءتين على الأقل");
        double[] result = new double[values.size()];
        for (int i = 0; i < result.length; i++) result[i] = values.get(i);
        return result;
    }

    private static void addIfNumeric(String token, List<Double> values) {
        if (token.isEmpty()) return;
        final double value;
        try { value = Double.parseDouble(token); }
        catch (NumberFormatException ex) { return; }
        if (!Double.isFinite(value)) throw new IllegalArgumentException("توجد قراءة غير صالحة");
        values.add(value);
    }

    public static String toCsv(double[] values) {
        if (values == null || values.length < 2) throw new IllegalArgumentException("يلزم إدخال قراءتين على الأقل");
        double[] stats = LabMath.summarize(values);
        StringBuilder out = new StringBuilder("source_type,user_measurement\nunit,mV\nindex,value\n");
        for (int i = 0; i < values.length; i++) {
            out.append(i + 1).append(',').append(String.format(Locale.US, "%.8f", values[i])).append('\n');
        }
        out.append('\n').append(String.format(Locale.US,
                "count,%d\nmin,%.8f\nmax,%.8f\nmean,%.8f\nrange,%.8f\nstddev,%.8f\n",
                (int) stats[5], stats[0], stats[1], stats[2], stats[3], stats[4]));
        return out.toString();
    }
}