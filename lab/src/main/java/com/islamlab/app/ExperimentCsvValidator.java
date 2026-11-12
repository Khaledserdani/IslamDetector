package com.islamlab.app;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Structural and provenance checks for ISLAM LAB experiment CSV.
 * Legacy 1.1 exports remain readable; schema 1.0.0 receives strict checks.
 */
public final class ExperimentCsvValidator {
    private ExperimentCsvValidator() {}

    public static final class Report {
        public final boolean valid;
        public final String schemaVersion;
        public final String sourceType;
        public final int sampleCount;
        public final String message;

        private Report(boolean valid, String version, String source, int count, String message) {
            this.valid = valid;
            this.schemaVersion = version;
            this.sourceType = source;
            this.sampleCount = count;
            this.message = message;
        }
    }

    public static Report validate(String csv) {
        try {
            if (csv == null || csv.trim().isEmpty())
                throw new IllegalArgumentException("ملف التجربة فارغ");
            if (csv.length() > 2_000_000)
                throw new IllegalArgumentException("حجم التجربة يتجاوز الحد المسموح");

            String[] lines = csv.replace("\r", "").split("\n");
            Map<String, String> metadata = new LinkedHashMap<>();
            int headerLine = -1;
            String[] columns = null;
            for (int i = 0; i < lines.length; i++) {
                String row = lines[i].trim();
                if (row.isEmpty()) continue;
                String[] cells = row.split(",", -1);
                if (isSampleHeader(cells)) {
                    headerLine = i;
                    columns = cells;
                    break;
                }
                if (cells.length >= 2) metadata.put(cells[0].trim(), cells[1].trim());
            }

            String version = metadata.getOrDefault("schema_version", "unknown");
            boolean strict = "1.0.0".equals(version);
            String source = metadata.get("source.type");
            if (source == null) source = metadata.getOrDefault("source_type", "unknown");

            if (strict) {
                require(metadata, "experiment_id");
                require(metadata, "title");
                require(metadata, "created_at_utc");
                if (!oneOf(source, "synthetic", "user_provided", "instrument", "islam_detector"))
                    throw new IllegalArgumentException("نوع مصدر البيانات غير معتمد");
                require(metadata, "source.origin");
                String verification = require(metadata, "verification.status");
                if (!oneOf(verification, "unverified", "reviewed", "ground_truth_confirmed",
                        "rejected", "inconclusive", "not_excavated"))
                    throw new IllegalArgumentException("حالة التحقق غير معروفة");
                if ("synthetic".equals(source) && "ground_truth_confirmed".equals(verification))
                    throw new IllegalArgumentException("لا يمكن وسم بيانات اصطناعية كحقيقة أرضية مؤكدة");
                if ("islam_detector".equals(source)) {
                    require(metadata, "source.device_id");
                    require(metadata, "source.firmware_version");
                }
                require(metadata, "measurement.quantity");
                require(metadata, "measurement.unit");
                require(metadata, "measurement.sample_origin");
            }

            if (headerLine < 0 || columns == null)
                throw new IllegalArgumentException("لم يتم العثور على رأس جدول العينات");

            int valueColumn = indexOf(columns, "value");
            int timeColumn = indexOf(columns, "time_us");
            int indexColumn = indexOf(columns, "sample_index");
            if (indexColumn < 0) indexColumn = indexOf(columns, "index");
            if (valueColumn < 0) throw new IllegalArgumentException("عمود value مفقود");
            if (timeColumn >= 0 && indexColumn < 0)
                throw new IllegalArgumentException("عمود sample_index مطلوب مع time_us");

            int count = 0;
            double firstIndex = Double.NaN;
            double previousTime = Double.NEGATIVE_INFINITY;
            for (int i = headerLine + 1; i < lines.length; i++) {
                String row = lines[i].trim();
                if (row.isEmpty()) {
                    if (count > 0) break;
                    continue;
                }
                String[] cells = row.split(",", -1);
                int needed = Math.max(valueColumn, Math.max(timeColumn, indexColumn));
                if (cells.length <= needed)
                    throw new IllegalArgumentException("صف عينة ناقص عند السطر " + (i + 1));

                double value = number(cells[valueColumn], i + 1);
                if (!Double.isFinite(value))
                    throw new IllegalArgumentException("قيمة غير محدودة عند السطر " + (i + 1));

                if (timeColumn >= 0) {
                    double time = number(cells[timeColumn], i + 1);
                    if (!Double.isFinite(time) || time < 0 || time <= previousTime)
                        throw new IllegalArgumentException("أزمنة العينات يجب أن تكون متزايدة عند السطر " + (i + 1));
                    previousTime = time;
                }

                if (indexColumn >= 0) {
                    double index = number(cells[indexColumn], i + 1);
                    if (count == 0) {
                        if (index != 0 && index != 1)
                            throw new IllegalArgumentException("يجب أن يبدأ ترقيم العينات من صفر أو واحد");
                        firstIndex = index;
                    } else if (index != firstIndex + count) {
                        throw new IllegalArgumentException("ترقيم العينات غير متسلسل عند السطر " + (i + 1));
                    }
                }
                count++;
                if (count > 100000)
                    throw new IllegalArgumentException("عدد العينات يتجاوز 100000");
            }

            if (count < 2) throw new IllegalArgumentException("يلزم وجود عينتين على الأقل");
            return new Report(true, version, source, count,
                    "سجل صالح بنيوياً؛ صحة القياس الفيزيائي لم تثبت بهذا الفحص");
        } catch (IllegalArgumentException ex) {
            return new Report(false, "unknown", "unknown", 0, ex.getMessage());
        }
    }

    private static boolean isSampleHeader(String[] cells) {
        return indexOf(cells, "value") >= 0
                && (indexOf(cells, "index") >= 0 || indexOf(cells, "sample_index") >= 0);
    }

    private static int indexOf(String[] cells, String wanted) {
        for (int i = 0; i < cells.length; i++)
            if (wanted.equalsIgnoreCase(cells[i].trim())) return i;
        return -1;
    }

    private static String require(Map<String, String> map, String key) {
        String value = map.get(key);
        if (value == null || value.trim().isEmpty())
            throw new IllegalArgumentException("حقل إلزامي مفقود: " + key);
        return value.trim();
    }

    private static boolean oneOf(String value, String... allowed) {
        for (String candidate : allowed) if (candidate.equals(value)) return true;
        return false;
    }

    private static double number(String raw, int line) {
        try { return Double.parseDouble(raw.trim()); }
        catch (Exception ex) {
            throw new IllegalArgumentException("قيمة رقمية غير صالحة عند السطر " + line);
        }
    }
}
