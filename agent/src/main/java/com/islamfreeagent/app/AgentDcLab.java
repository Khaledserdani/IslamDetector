package com.islamfreeagent.app;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Bounded, deterministic DC resistive-network solver for the Android laboratory.
 * The reference node is ground and exactly one ideal voltage source is applied
 * between a named node and ground. All other nodes are solved by nodal analysis.
 */
final class AgentDcLab {
    private AgentDcLab() {}

    static final class Resistor {
        final String a;
        final String b;
        final double ohms;

        Resistor(String a, String b, double ohms) {
            this.a = a;
            this.b = b;
            this.ohms = ohms;
        }
    }

    static final class Result {
        final Map<String, Double> nodeVoltages;
        final double sourceCurrentAmps;
        final double maximumKclResidualAmps;

        Result(Map<String, Double> nodeVoltages, double sourceCurrentAmps,
               double maximumKclResidualAmps) {
            this.nodeVoltages = Collections.unmodifiableMap(
                    new LinkedHashMap<>(nodeVoltages));
            this.sourceCurrentAmps = sourceCurrentAmps;
            this.maximumKclResidualAmps = maximumKclResidualAmps;
        }
    }

    static Result solve(String ground, String sourceNode, double sourceVolts,
                        List<Resistor> resistors) {
        requireName(ground, "ground");
        requireName(sourceNode, "source node");
        if (ground.equals(sourceNode)) throw new IllegalArgumentException("source node cannot be ground");
        if (!Double.isFinite(sourceVolts)) throw new IllegalArgumentException("source voltage must be finite");
        if (resistors == null || resistors.isEmpty() || resistors.size() > 500) {
            throw new IllegalArgumentException("resistor count must be between 1 and 500");
        }

        LinkedHashMap<String, Integer> indexes = new LinkedHashMap<>();
        for (Resistor r : resistors) {
            if (r == null) throw new IllegalArgumentException("resistor cannot be null");
            requireName(r.a, "resistor node");
            requireName(r.b, "resistor node");
            if (r.a.equals(r.b)) throw new IllegalArgumentException("resistor endpoints must differ");
            if (!Double.isFinite(r.ohms) || r.ohms <= 0.0 || r.ohms > 1.0e12) {
                throw new IllegalArgumentException("resistance must be finite and in (0, 1e12]");
            }
            if (!r.a.equals(ground) && !r.a.equals(sourceNode)) indexes.putIfAbsent(r.a, indexes.size());
            if (!r.b.equals(ground) && !r.b.equals(sourceNode)) indexes.putIfAbsent(r.b, indexes.size());
        }
        if (!touchesSource(resistors, sourceNode)) {
            throw new IllegalArgumentException("source node is not connected to the resistor network");
        }

        int n = indexes.size();
        double[][] matrix = new double[n][n];
        double[] rhs = new double[n];
        double gSource = 0.0;
        for (Resistor r : resistors) {
            double g = 1.0 / r.ohms;
            boolean aUnknown = indexes.containsKey(r.a);
            boolean bUnknown = indexes.containsKey(r.b);
            if (aUnknown) {
                int i = indexes.get(r.a);
                matrix[i][i] += g;
                if (bUnknown) matrix[i][indexes.get(r.b)] -= g;
                else if (r.b.equals(sourceNode)) rhs[i] += g * sourceVolts;
            }
            if (bUnknown) {
                int i = indexes.get(r.b);
                matrix[i][i] += g;
                if (aUnknown) matrix[i][indexes.get(r.a)] -= g;
                else if (r.a.equals(sourceNode)) rhs[i] += g * sourceVolts;
            }
            if (r.a.equals(sourceNode) || r.b.equals(sourceNode)) gSource += g;
        }

        double[] solution = gaussianSolve(matrix, rhs);
        LinkedHashMap<String, Double> voltages = new LinkedHashMap<>();
        voltages.put(ground, 0.0);
        voltages.put(sourceNode, sourceVolts);
        for (Map.Entry<String, Integer> e : indexes.entrySet()) {
            voltages.put(e.getKey(), solution[e.getValue()]);
        }

        double sourceCurrent = 0.0;
        LinkedHashMap<String, Double> kcl = new LinkedHashMap<>();
        for (String node : voltages.keySet()) kcl.put(node, 0.0);
        for (Resistor r : resistors) {
            double current = (voltages.get(r.a) - voltages.get(r.b)) / r.ohms;
            kcl.put(r.a, kcl.get(r.a) + current);
            kcl.put(r.b, kcl.get(r.b) - current);
        }
        sourceCurrent = kcl.get(sourceNode);
        double maxResidual = 0.0;
        for (String node : indexes.keySet()) maxResidual = Math.max(maxResidual, Math.abs(kcl.get(node)));
        if (!Double.isFinite(sourceCurrent) || !Double.isFinite(maxResidual)) {
            throw new ArithmeticException("non-finite result");
        }
        return new Result(voltages, sourceCurrent, maxResidual);
    }

    private static boolean touchesSource(List<Resistor> resistors, String source) {
        for (Resistor r : resistors) if (r.a.equals(source) || r.b.equals(source)) return true;
        return false;
    }

    private static void requireName(String value, String label) {
        if (value == null || value.trim().isEmpty() || value.length() > 64) {
            throw new IllegalArgumentException(label + " name is invalid");
        }
    }

    private static double[] gaussianSolve(double[][] input, double[] values) {
        int n = values.length;
        if (n == 0) return new double[0];
        double[][] a = new double[n][n];
        double[] b = values.clone();
        for (int i = 0; i < n; i++) a[i] = input[i].clone();
        for (int col = 0; col < n; col++) {
            int pivot = col;
            for (int row = col + 1; row < n; row++) {
                if (Math.abs(a[row][col]) > Math.abs(a[pivot][col])) pivot = row;
            }
            if (Math.abs(a[pivot][col]) < 1.0e-15) {
                throw new IllegalArgumentException("network is floating or singular");
            }
            double[] swap = a[col]; a[col] = a[pivot]; a[pivot] = swap;
            double temp = b[col]; b[col] = b[pivot]; b[pivot] = temp;
            double divisor = a[col][col];
            for (int j = col; j < n; j++) a[col][j] /= divisor;
            b[col] /= divisor;
            for (int row = 0; row < n; row++) {
                if (row == col) continue;
                double factor = a[row][col];
                if (factor == 0.0) continue;
                for (int j = col; j < n; j++) a[row][j] -= factor * a[col][j];
                b[row] -= factor * b[col];
            }
        }
        for (double value : b) if (!Double.isFinite(value)) throw new ArithmeticException("non-finite solution");
        return b;
    }
}
