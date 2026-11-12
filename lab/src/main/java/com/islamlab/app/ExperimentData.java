package com.islamlab.app;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Validates plain numeric samples and the app's explicit index,value CSV format. */
public final class ExperimentData {
    private ExperimentData() {}

    public static double[] parse(String raw) {
        if (raw == null || raw.trim().isEmpty()) throw new IllegalArgumentException("لا توجد بيانات");
        String[] lines = raw.trim().split("\\r?\n");
        int header = -1;
        for (int i = 0; i < lines.length; i++) {
            String row = lines[i].trim();
            if (isSampleHeader(row)) {
                header = i;
                break;
            }
        }

        List<Double> values = new ArrayList<>();
        if (header >= 0) {
            for (int i = header + 1; i < lines.length; i++) {
                String row = lines[i].trim();
                if (row.isEmpty()) break;
                String[] cells = row.split("[,;\\t]", -1);
                if (cells.length < 2 || cells[cells.length - 1].trim().isEmpty()) {
                    throw new IllegalArgumentException("صف CSV غير مكتمل عند السطر " + (i + 1));
                }
                addRequiredNumeric(cells[cells.length - 1].trim(), values, i + 1);
                enforceLimit(values);
            }
        } else {
            String[] tokens = raw.trim().split("[,;\\t\\s]+");
            for (int i = 0; i < tokens.length; i++) {
                addRequiredNumeric(tokens[i].trim(), values, i + 1);
                enforceLimit(values);
            }
        }

        if (values.size() < 2) throw new IllegalArgumentException("يلزم إدخال قراءتين على الأقل");
        double[] result = new double[values.size()];
        for (int i = 0; i < result.length; i++) result[i] = values.get(i);
        return result;
    }

    private static boolean isSampleHeader(String row) {
        String[] cells = row.split("[,;\\\\t]", -1);
        return valueColumn(row) >= 0 && (row.toLowerCase(Locale.ROOT).contains("index")
                || row.toLowerCase(Locale.ROOT).contains("sample_index"));
    }

    private static int valueColumn(String row) {
        String[] cells = row.split("[,;\\\\t]", -1);
        for (int i = 0; i < cells.length; i++)
            if ("value".equalsIgnoreCase(cells[i].trim())) return i;
        return -1;
    }

    private static void addRequiredNumeric(String token, List<Double> values, int row) {
        final double value;
        try { value = Double.parseDouble(token); }
        catch (NumberFormatException ex) {
            throw new IllegalArgumentException("قيمة غير رقمية في السطر " + row + ": " + token);
        }
        if (!Double.isFinite(value)) throw new IllegalArgumentException("قراءة غير صالحة في السطر " + row);
        values.add(value);
    }

    private static void enforceLimit(List<Double> values) {
        if (values.size() > 100000) throw new IllegalArgumentException("عدد القراءات يتجاوز 100000");
    }

    public static String toCsv(double[] values) {
        return toCsv(values, System.currentTimeMillis());
    }

    public static String toCsv(double[] values, long createdEpochMs) {
        if (values == null || values.length < 2) throw new IllegalArgumentException("يلزم إدخال قراءتين على الأقل");
        double[] stats = LabMath.summarize(values);
        StringBuilder out = new StringBuilder();
        out.append("schema_version,1.1\n");
        out.append("source_type,user_provided\n");
        out.append("acquisition_origin,user_entry_or_file_import\n");
        out.append("measurement_status,not_verified_as_device_measurement\n");
        out.append("measurement_device,not_recorded\n");
        out.append("unit,mV\n");
        out.append("created_epoch_ms,").append(createdEpochMs).append("\n");
        out.append("index,value\n");
        for (int i = 0; i < values.length; i++) {
            out.append(i + 1).append(',').append(String.format(Locale.US, "%.8f", values[i])).append('\n');
        }
        out.append((char) 10).append(String.format(Locale.US,
                "count,%d\nmin,%.8f\nmax,%.8f\nmean,%.8f\nrange,%.8f\nstddev,%.8f\n",
                (int) stats[5], stats[0], stats[1], stats[2], stats[3], stats[4]));
        return out.toString();
    }
}
