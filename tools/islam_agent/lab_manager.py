"""Deterministic DC resistive-network laboratory (no physical measurement claims)."""
from __future__ import annotations

MAX_BRANCHES = 64
MAX_NODES = 32


class LabInputError(ValueError):
    pass


def _solve(matrix, vector):
    n = len(vector)
    a = [list(map(float, row)) + [float(vector[i])] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(a[row][col]))
        if abs(a[pivot][col]) < 1e-12:
            raise LabInputError("network is singular or has no unique DC solution")
        a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        for j in range(col, n + 1):
            a[col][j] /= scale
        for row in range(n):
            if row == col:
                continue
            factor = a[row][col]
            for j in range(col, n + 1):
                a[row][j] -= factor * a[col][j]
    return [a[i][n] for i in range(n)]


def validate_circuit(spec):
    if not isinstance(spec, dict) or set(spec) != {"ground", "resistors", "voltage_sources"}:
        raise LabInputError("circuit requires exactly ground, resistors, voltage_sources")
    ground, resistors, sources = spec["ground"], spec["resistors"], spec["voltage_sources"]
    if not isinstance(ground, str) or not ground or not isinstance(resistors, list) or not isinstance(sources, list):
        raise LabInputError("invalid ground or branch lists")
    if not 1 <= len(resistors) <= MAX_BRANCHES or len(sources) > 16:
        raise LabInputError("branch count outside laboratory limits")
    nodes = {ground}
    for item in resistors:
        if not isinstance(item, dict) or set(item) != {"a", "b", "ohms"}:
            raise LabInputError("each resistor requires a, b, ohms")
        if not all(isinstance(item[k], str) and item[k] for k in ("a", "b")):
            raise LabInputError("resistor nodes must be non-empty strings")
        value = item["ohms"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 1e-6 <= value <= 1e9:
            raise LabInputError("resistance must be between 1 micro-ohm and 1 giga-ohm")
        nodes.update((item["a"], item["b"]))
    for item in sources:
        if not isinstance(item, dict) or set(item) != {"positive", "negative", "volts"}:
            raise LabInputError("each source requires positive, negative, volts")
        if not all(isinstance(item[k], str) and item[k] for k in ("positive", "negative")):
            raise LabInputError("source nodes must be non-empty strings")
        value = item["volts"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or abs(value) > 10000:
            raise LabInputError("source voltage must be within +/-10000 V")
        nodes.update((item["positive"], item["negative"]))
    if len(nodes) > MAX_NODES:
        raise LabInputError("network exceeds the 32-node limit")
    return ground, resistors, sources, nodes


def simulate_dc_resistive_network(spec):
    """Solve ideal DC sources and resistors with modified nodal analysis."""
    ground, resistors, sources, nodes = validate_circuit(spec)
    ordered = sorted(nodes - {ground})
    node_index = {name: i for i, name in enumerate(ordered)}
    n, m = len(ordered), len(sources)
    size = n + m
    if size == 0:
        raise LabInputError("circuit has no solvable nodes")
    matrix = [[0.0] * size for _ in range(size)]
    rhs = [0.0] * size

    def idx(node):
        return None if node == ground else node_index[node]

    for item in resistors:
        a, b, g = idx(item["a"]), idx(item["b"]), 1.0 / float(item["ohms"])
        if a is not None:
            matrix[a][a] += g
        if b is not None:
            matrix[b][b] += g
        if a is not None and b is not None:
            matrix[a][b] -= g
            matrix[b][a] -= g

    for k, source in enumerate(sources):
        row = n + k
        p, q = idx(source["positive"]), idx(source["negative"])
        if p is not None:
            matrix[p][row] += 1.0
            matrix[row][p] += 1.0
        if q is not None:
            matrix[q][row] -= 1.0
            matrix[row][q] -= 1.0
        rhs[row] = float(source["volts"])

    solution = _solve(matrix, rhs)
    voltages = {ground: 0.0}
    voltages.update({name: solution[i] for name, i in node_index.items()})
    branches = []
    for index, item in enumerate(resistors):
        current = (voltages[item["a"]] - voltages[item["b"]]) / float(item["ohms"])
        branches.append({
            "type": "resistor", "index": index, "current_a": current,
            "voltage_v": voltages[item["a"]] - voltages[item["b"]],
            "power_w": current * current * float(item["ohms"]),
        })
    source_results = []
    for index, item in enumerate(sources):
        current = solution[n + index]
        source_results.append({
            "type": "ideal_voltage_source", "index": index,
            "current_a": current, "voltage_v": float(item["volts"]),
            "power_delivered_w": float(item["volts"]) * current,
        })
    kcl = {node: 0.0 for node in nodes}
    for item, result in zip(resistors, branches):
        kcl[item["a"]] += result["current_a"]
        kcl[item["b"]] -= result["current_a"]
    for item, result in zip(sources, source_results):
        kcl[item["positive"]] += result["current_a"]
        kcl[item["negative"]] -= result["current_a"]
    residual = max(abs(value) for node, value in kcl.items() if node != ground) if n else 0.0
    return {
        "laboratory": "dc_resistive_network_mna",
        "model": "ideal resistors and ideal DC voltage sources",
        "node_voltages_v": voltages,
        "branches": branches,
        "sources": source_results,
        "max_kcl_residual_a": residual,
        "verified_numerically": residual < 1e-8,
        "limitations": ["لا يحاكي الحرارة أو المحاثة أو السعة أو التبديل أو ضوضاء المكونات أو تأثيرات PCB."],
    }
