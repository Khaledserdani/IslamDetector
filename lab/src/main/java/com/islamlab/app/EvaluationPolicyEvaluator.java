package com.islamlab.app;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.LinkedHashSet;
import java.util.Set;

/**
 * Deterministic release-gate calculation for binary metal-presence detection.
 *
 * This class does not train, deploy, or persist anything. The caller must supply
 * observations parsed from the immutable, independently held-out TEST split.
 * One observation represents one independent field case/group, not one repeated
 * pulse or window from the same target.
 */
public final class EvaluationPolicyEvaluator {
    private EvaluationPolicyEvaluator() {}

    public static final class Observation {
        public final String split;
        public final String groupKey;
        public final String targetClass;
        public final String soilClass;
        public final boolean groundTruthPositive;
        public final boolean championDetected;
        public final boolean candidateDetected;

        public Observation(String split, String groupKey, String targetClass, String soilClass,
                           boolean groundTruthPositive, boolean championDetected,
                           boolean candidateDetected) {
            this.split = split;
            this.groupKey = groupKey;
            this.targetClass = targetClass;
            this.soilClass = soilClass;
            this.groundTruthPositive = groundTruthPositive;
            this.championDetected = championDetected;
            this.candidateDetected = candidateDetected;
        }
    }

    /** All limits are explicit inputs; there are intentionally no permissive defaults. */
    public static final class Policy {
        public final int minTestCases;
        public final int minPositiveCases;
        public final int minNegativeCases;
        public final double maxAccuracyDrop;
        public final double maxRecallDrop;
        public final double maxFalsePositiveRateIncrease;
        public final double minCandidateRecall;
        public final double maxCandidateFalsePositiveRate;
        public final Set<String> requiredStrata;

        public Policy(int minTestCases, int minPositiveCases, int minNegativeCases,
                      double maxAccuracyDrop, double maxRecallDrop,
                      double maxFalsePositiveRateIncrease, double minCandidateRecall,
                      double maxCandidateFalsePositiveRate, List<String> requiredStrata) {
            if (minTestCases < 1 || minPositiveCases < 1 || minNegativeCases < 1)
                throw new IllegalArgumentException("حدود حجم الاختبار يجب أن تكون موجبة");
            checkRate(maxAccuracyDrop, "maxAccuracyDrop");
            checkRate(maxRecallDrop, "maxRecallDrop");
            checkRate(maxFalsePositiveRateIncrease, "maxFalsePositiveRateIncrease");
            checkRate(minCandidateRecall, "minCandidateRecall");
            checkRate(maxCandidateFalsePositiveRate, "maxCandidateFalsePositiveRate");
            this.minTestCases = minTestCases;
            this.minPositiveCases = minPositiveCases;
            this.minNegativeCases = minNegativeCases;
            this.maxAccuracyDrop = maxAccuracyDrop;
            this.maxRecallDrop = maxRecallDrop;
            this.maxFalsePositiveRateIncrease = maxFalsePositiveRateIncrease;
            this.minCandidateRecall = minCandidateRecall;
            this.maxCandidateFalsePositiveRate = maxCandidateFalsePositiveRate;
            Set<String> required = new LinkedHashSet<>();
            if (requiredStrata != null) {
                for (String key : requiredStrata) {
                    if (blank(key) || !key.contains("|") || !required.add(key))
                        throw new IllegalArgumentException("قائمة الفئات/التربة المطلوبة غير صالحة أو مكررة");
                }
            }
            this.requiredStrata = Collections.unmodifiableSet(required);
        }
    }

    public static final class Metrics {
        public final int cases, positives, negatives, truePositive, falsePositive,
                trueNegative, falseNegative;
        public final double accuracy, recall, falsePositiveRate;

        private Metrics(int cases, int positives, int negatives, int tp, int fp, int tn, int fn) {
            this.cases=cases; this.positives=positives; this.negatives=negatives;
            this.truePositive=tp; this.falsePositive=fp; this.trueNegative=tn; this.falseNegative=fn;
            this.accuracy = cases == 0 ? 0.0 : (double) (tp + tn) / cases;
            this.recall = positives == 0 ? 0.0 : (double) tp / positives;
            this.falsePositiveRate = negatives == 0 ? 0.0 : (double) fp / negatives;
        }
    }

    public static final class StratumResult {
        public final String targetClass, soilClass;
        public final Metrics champion, candidate;
        private StratumResult(String targetClass, String soilClass, Metrics champion, Metrics candidate) {
            this.targetClass=targetClass; this.soilClass=soilClass;
            this.champion=champion; this.candidate=candidate;
        }
    }

    public static final class Result {
        /** ELIGIBLE means only that this numeric gate passed; it is not deployment approval. */
        public final String status;
        public final String reason;
        public final Metrics champion, candidate;
        public final Map<String, StratumResult> strata;
        private Result(String status, String reason, Metrics champion, Metrics candidate,
                       Map<String, StratumResult> strata) {
            this.status=status; this.reason=reason; this.champion=champion; this.candidate=candidate;
            this.strata=Collections.unmodifiableMap(new LinkedHashMap<>(strata));
        }
    }

    private static final class Counts {
        int cases, positives, negatives, tp, fp, tn, fn;
        void add(Observation o) {
            cases++;
            if (o.groundTruthPositive) {
                positives++;
                if (o.candidateDetected) tp++; else fn++;
            } else {
                negatives++;
                if (o.candidateDetected) fp++; else tn++;
            }
        }
        Metrics metrics() { return new Metrics(cases, positives, negatives, tp, fp, tn, fn); }
    }

    private static final class PairCounts {
        final Counts champion = new Counts();
        final Counts candidate = new Counts();
        void add(Observation o) {
            champion.add(new Observation("test", o.groupKey, o.targetClass, o.soilClass,
                    o.groundTruthPositive, o.championDetected, o.championDetected));
            candidate.add(o);
        }
    }

    public static Result evaluate(List<Observation> observations, Policy policy) {
        if (policy == null) throw new IllegalArgumentException("سياسة التقييم مطلوبة");
        if (observations == null || observations.isEmpty())
            return result("INSUFFICIENT_EVIDENCE", "لا توجد حالات اختبار", null, null,
                    Collections.<String, StratumResult>emptyMap());

        Set<String> groups = new HashSet<>();
        PairCounts overall = new PairCounts();
        Map<String, PairCounts> grouped = new LinkedHashMap<>();
        for (Observation o : observations) {
            if (o == null || !"test".equals(o.split) || blank(o.groupKey)
                    || blank(o.targetClass) || blank(o.soilClass))
                return result("REJECTED", "توجد حالة ليست من TEST أو ينقصها تعريف المجموعة/الفئة/التربة",
                        null, null, Collections.<String, StratumResult>emptyMap());
            if (!groups.add(o.groupKey))
                return result("REJECTED", "تكررت المجموعة المستقلة؛ لا تُحسب النوافذ المتكررة كحالات مستقلة",
                        null, null, Collections.<String, StratumResult>emptyMap());
            overall.add(o);
            String key = o.targetClass + "|" + o.soilClass;
            PairCounts pair = grouped.get(key);
            if (pair == null) { pair = new PairCounts(); grouped.put(key, pair); }
            pair.add(o);
        }

        Metrics champion = overall.champion.metrics();
        Metrics candidate = overall.candidate.metrics();
        Map<String, StratumResult> strata = new LinkedHashMap<>();
        for (Map.Entry<String, PairCounts> entry : grouped.entrySet()) {
            String[] parts = entry.getKey().split("\\|", 2);
            PairCounts pair = entry.getValue();
            strata.put(entry.getKey(), new StratumResult(parts[0], parts[1],
                    pair.champion.metrics(), pair.candidate.metrics()));
        }

        if (candidate.cases < policy.minTestCases
                || candidate.positives < policy.minPositiveCases
                || candidate.negatives < policy.minNegativeCases)
            return result("INSUFFICIENT_EVIDENCE", "حجم TEST أو عدد الحالات الإيجابية/السلبية أقل من الحد المحدد",
                    champion, candidate, strata);

        if (!passes(champion, candidate, policy))
            return result("REJECTED", "تراجع إجمالي أو تجاوز حد الاستدعاء/الإنذارات الكاذبة",
                    champion, candidate, strata);

        for (String requiredKey : policy.requiredStrata) {
            if (!strata.containsKey(requiredKey))
                return result("INSUFFICIENT_EVIDENCE",
                        "مجموعة الاختبار لا تغطي الفئة/التربة المطلوبة: " + requiredKey,
                        champion, candidate, strata);
        }

        if (!policy.requiredStrata.isEmpty()) {
            for (StratumResult s : strata.values()) {
                if (s.candidate.cases < policy.minTestCases)
                    return result("INSUFFICIENT_EVIDENCE",
                            "عدد الحالات المستقلة غير كافٍ للفئة/التربة: " + s.targetClass + " / " + s.soilClass,
                            champion, candidate, strata);
                if (!passesStratum(s.champion, s.candidate, policy))
                    return result("REJECTED",
                            "تراجع في المقاييس القابلة للحساب للفئة/التربة: " + s.targetClass + " / " + s.soilClass,
                            champion, candidate, strata);
            }
        }
        return result("ELIGIBLE_FOR_REVIEW",
                "اجتاز المرشح الحدود الرقمية؛ ما زال يحتاج مراجعة بشرية مستقلة وقرار اعتماد منفصل",
                champion, candidate, strata);
    }

    private static boolean passes(Metrics oldM, Metrics newM, Policy p) {
        return newM.accuracy >= oldM.accuracy - p.maxAccuracyDrop
                && newM.recall >= oldM.recall - p.maxRecallDrop
                && newM.falsePositiveRate <= oldM.falsePositiveRate + p.maxFalsePositiveRateIncrease
                && newM.recall >= p.minCandidateRecall
                && newM.falsePositiveRate <= p.maxCandidateFalsePositiveRate;
    }

    /** Strata may be positive-only or negative-only; test only metrics with a real denominator. */
    private static boolean passesStratum(Metrics oldM, Metrics newM, Policy p) {
        if (newM.accuracy < oldM.accuracy - p.maxAccuracyDrop) return false;
        if (newM.positives > 0
                && (newM.recall < oldM.recall - p.maxRecallDrop
                    || newM.recall < p.minCandidateRecall)) return false;
        if (newM.negatives > 0
                && (newM.falsePositiveRate > oldM.falsePositiveRate + p.maxFalsePositiveRateIncrease
                    || newM.falsePositiveRate > p.maxCandidateFalsePositiveRate)) return false;
        return true;
    }

    private static Result result(String status, String reason, Metrics champion, Metrics candidate,
                                 Map<String, StratumResult> strata) {
        return new Result(status, reason, champion, candidate, strata);
    }

    private static void checkRate(double value, String name) {
        if (Double.isNaN(value) || Double.isInfinite(value) || value < 0.0 || value > 1.0)
            throw new IllegalArgumentException(name + " يجب أن تكون بين 0 و1");
    }

    private static boolean blank(String s) { return s == null || s.trim().isEmpty(); }
}
