package com.islamlab.app;

import org.junit.Test;
import java.util.ArrayList;
import java.util.List;
import static org.junit.Assert.*;

public class EvaluationPolicyEvaluatorTest {
    private EvaluationPolicyEvaluator.Policy policy(boolean perStratum) {
        return new EvaluationPolicyEvaluator.Policy(
                4, 2, 2, 0.05, 0.05, 0.05, 0.80, 0.20, perStratum);
    }

    private List<EvaluationPolicyEvaluator.Observation> balanced() {
        List<EvaluationPolicyEvaluator.Observation> rows = new ArrayList<>();
        rows.add(row("g1", true, true, true, "iron", "dry"));
        rows.add(row("g2", true, true, true, "iron", "dry"));
        rows.add(row("g3", false, false, false, "iron", "dry"));
        rows.add(row("g4", false, false, false, "iron", "dry"));
        return rows;
    }

    private EvaluationPolicyEvaluator.Observation row(String group, boolean truth,
            boolean champion, boolean candidate, String target, String soil) {
        return new EvaluationPolicyEvaluator.Observation(
                "test", group, target, soil, truth, champion, candidate);
    }

    @Test public void identicalCandidatePassesOnlyToHumanReview() {
        EvaluationPolicyEvaluator.Result r =
                EvaluationPolicyEvaluator.evaluate(balanced(), policy(false));
        assertEquals("ELIGIBLE_FOR_REVIEW", r.status);
        assertEquals(1.0, r.candidate.accuracy, 0.0);
        assertEquals(0.0, r.candidate.falsePositiveRate, 0.0);
    }

    @Test public void candidateWithRecallLossIsRejected() {
        List<EvaluationPolicyEvaluator.Observation> rows = balanced();
        rows.set(0, row("g1", true, true, false, "iron", "dry"));
        rows.set(1, row("g2", true, true, true, "iron", "dry"));
        EvaluationPolicyEvaluator.Result r =
                EvaluationPolicyEvaluator.evaluate(rows, policy(false));
        assertEquals("REJECTED", r.status);
    }

    @Test public void candidateWithNewFalsePositiveIsRejectedByAbsoluteLimit() {
        List<EvaluationPolicyEvaluator.Observation> rows = balanced();
        rows.set(2, row("g3", false, false, true, "iron", "dry"));
        EvaluationPolicyEvaluator.Result r =
                EvaluationPolicyEvaluator.evaluate(rows, policy(false));
        assertEquals("REJECTED", r.status);
    }

    @Test public void repeatedGroupCannotInflateEvidence() {
        List<EvaluationPolicyEvaluator.Observation> rows = balanced();
        rows.add(row("g1", true, true, true, "iron", "dry"));
        EvaluationPolicyEvaluator.Result r =
                EvaluationPolicyEvaluator.evaluate(rows, policy(false));
        assertEquals("REJECTED", r.status);
    }

    @Test public void insufficientIndependentCasesDoNotPass() {
        List<EvaluationPolicyEvaluator.Observation> rows = balanced().subList(0, 3);
        EvaluationPolicyEvaluator.Result r =
                EvaluationPolicyEvaluator.evaluate(rows, policy(false));
        assertEquals("INSUFFICIENT_EVIDENCE", r.status);
    }

    @Test public void missingPerStratumCoverageBlocksReviewEligibility() {
        List<EvaluationPolicyEvaluator.Observation> rows = balanced();
        rows.add(row("g5", true, true, true, "copper", "wet-clay"));
        EvaluationPolicyEvaluator.Result r =
                EvaluationPolicyEvaluator.evaluate(rows, policy(true));
        assertEquals("INSUFFICIENT_EVIDENCE", r.status);
        assertTrue(r.reason.contains("copper"));
    }

    @Test public void nonTestSplitIsRejected() {
        List<EvaluationPolicyEvaluator.Observation> rows = balanced();
        rows.set(0, new EvaluationPolicyEvaluator.Observation(
                "train", "g1", "iron", "dry", true, true, true));
        EvaluationPolicyEvaluator.Result r =
                EvaluationPolicyEvaluator.evaluate(rows, policy(false));
        assertEquals("REJECTED", r.status);
    }

    @Test(expected = IllegalArgumentException.class)
    public void policyRejectsInvalidThreshold() {
        new EvaluationPolicyEvaluator.Policy(4, 2, 2,
                1.2, 0.05, 0.05, 0.8, 0.2, false);
    }
}
