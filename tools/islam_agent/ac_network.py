"""Multi-node AC phasor MNA solver for linear RLC networks.

Uses RMS phasors, ideal independent voltage sources, and ideal lumped R/L/C.
This is a bounded deterministic solver, not a full SPICE implementation.
"""
from __future__ import annotations

import cmath
import math

MAX_NODES = 32
MAX_BRANCHES = 64
MAX_SOURCES = 16
MAX_VALUE = 1e9


class ACNetworkError(ValueError):
    pass


def _finite_number(value, name, low, high, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ACNetworkError(name + " must be a finite number")
    if value < low or value > high or (positive and value <= 0):
        raise ACNetworkError(name + " is outside allowed limits")
    return float(value)


def validate_ac_network(spec):
    required = {"ground", "frequency_hz", "resistors", "capacitors", "inductors", "voltage_sources"}
    if not isinstance(spec, dict) or set(spec) != required:
        raise ACNetworkError("network must contain exactly ground, frequency_hz, R, C, L and voltage_sources")
    ground = spec["ground"]
    if not isinstance(ground, str) or not ground:
        raise ACNetworkError("ground must be a non-empty node name")
    frequency = _finite_number(spec["frequency_hz"], "frequency_hz", 0, 1e7, positive=True)
    collections = {}
    nodes = {ground}
    total = 0
    for key in ("resistors", "capacitors", "inductors"):
        items = spec[key]
        if not isinstance(items, list):
            raise ACNetworkError(key + " must be a list")
        collections[key] = items
        total += len(items)
        for item in items:
            if not isinstance(item, dict) or set(item) != {"a", "b", "value"}:
                raise ACNetworkError(key + " entries require exactly a, b, value")
            if not all(isinstance(item[n], str) and item[n] for n in ("a", "b")) or item["a"] == item["b"]:
                raise ACNetworkError("branch node names must be distinct non-empty strings")
            _finite_number(item["value"], key + ".value", 0, MAX_VALUE, positive=True)
            nodes.update((item["a"], item["b"]))
    sources = spec["voltage_sources"]
    if not isinstance(sources, list) or len(sources) > MAX_SOURCES:
        raise ACNetworkError("voltage_sources must be a list within the source limit")
    total += len(sources)
    for item in sources:
        if not isinstance(item, dict) or set(item) != {"positive", "negative", "voltage_rms_v"}:
            raise ACNetworkError("voltage sources require positive, negative, voltage_rms_v")
        if not all(isinstance(item[n], str) and item[n] for n in ("positive", "negative")) or item["positive"] == item["negative"]:
            raise ACNetworkError("source nodes must be distinct non-empty strings")
        _finite_number(item["voltage_rms_v"], "voltage_rms_v", -10000, 10000)
        nodes.update((item["positive"], item["negative"]))
    if total < 1 or total > MAX_BRANCHES:
        raise ACNetworkError("network branch count outside limits")
    if len(nodes) > MAX_NODES:
        raise ACNetworkError("network exceeds node limit")
    return ground, frequency, collections, sources, nodes


def _solve_complex(matrix, vector):
    n = len(vector)
    a = [list(row) + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(a[row][col]))
        if abs(a[pivot][col]) < 1e-14:
            raise ACNetworkError("AC network is singular or has no unique solution")
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


def simulate_ac_network(spec):
    ground, frequency, collections, sources, nodes = validate_ac_network(spec)
    omega = 2 * math.pi * frequency
    ordered = sorted(nodes - {ground})
    index = {name: i for i, name in enumerate(ordered)}
    n, m = len(ordered), len(sources)
    size = n + m
    matrix = [[0j] * size for _ in range(size)]
    rhs = [0j] * size

    def idx(node):
        return None if node == ground else index[node]

    def stamp_admittance(a_name, b_name, y):
        a, b = idx(a_name), idx(b_name)
        if a is not None: matrix[a][a] += y
        if b is not None: matrix[b][b] += y
        if a is not None and b is not None:
            matrix[a][b] -= y
            matrix[b][a] -= y

    for item in collections["resistors"]:
        stamp_admittance(item["a"], item["b"], 1.0 / item["value"])
    for item in collections["capacitors"]:
        stamp_admittance(item["a"], item["b"], 1j * omega * item["value"])
    for item in collections["inductors"]:
        stamp_admittance(item["a"], item["b"], 1.0 / (1j * omega * item["value"]))

    for k, source in enumerate(sources):
        row = n + k
        p, q = idx(source["positive"]), idx(source["negative"])
        if p is not None:
            matrix[p][row] += 1
            matrix[row][p] += 1
        if q is not None:
            matrix[q][row] -= 1
            matrix[row][q] -= 1
        rhs[row] = complex(source["voltage_rms_v"], 0)

    solution = _solve_complex(matrix, rhs)
    voltages = {ground: 0j}
    voltages.update({node: solution[i] for node, i in index.items()})
    branch_results = []
    kcl = {node: 0j for node in nodes}
    total_real_power = 0.0
    for kind, key in (("resistor", "resistors"), ("capacitor", "capacitors"), ("inductor", "inductors")):
        for item in collections[key]:
            va, vb = voltages[item["a"]], voltages[item["b"]]
            v = va - vb
            if kind == "resistor":
                current = v / item["value"]
                power = (abs(current) ** 2) * item["value"]
                total_real_power += power
            elif kind == "capacitor":
                current = 1j * omega * item["value"] * v
                power = 0.0
            else:
                current = v / (1j * omega * item["value"])
                power = 0.0
            kcl[item["a"]] += current
            kcl[item["b"]] -= current
            branch_results.append({
                "type": kind, "a": item["a"], "b": item["b"],
                "voltage_rms": {"real": v.real, "imag": v.imag},
                "current_rms": {"real": current.real, "imag": current.imag},
                "current_magnitude_a": abs(current),
                "current_phase_deg": math.degrees(cmath.phase(current)),
                "real_power_w": power,
            })
    source_results = []
    for k, item in enumerate(sources):
        current = solution[n + k]
        kcl[item["positive"]] += current
        kcl[item["negative"]] -= current
        source_results.append({
            "positive": item["positive"], "negative": item["negative"],
            "current_rms": {"real": current.real, "imag": current.imag},
            "current_magnitude_a": abs(current),
        })
    residual = max((abs(v) for node, v in kcl.items() if node != ground), default=0.0)
    node_output = {
        name: {"real": value.real, "imag": value.imag,
               "magnitude_v": abs(value), "phase_deg": math.degrees(cmath.phase(value))}
        for name, value in voltages.items()
    }
    return {
        "laboratory": "linear_ac_network_mna",
        "model": "ideal linear RLC branches and ideal RMS voltage sources",
        "frequency_hz": frequency, "omega_rad_s": omega,
        "node_voltages_rms": node_output, "branches": branch_results,
        "sources": source_results, "max_kcl_residual_a": residual,
        "total_resistor_power_w": total_real_power,
        "verified_numerically": residual < 1e-8,
        "limitations": ["لا يحاكي أشباه الموصلات أو العناصر غير الخطية أو التوافقيات أو الاقتران أو الطفيليات أو تغير الحرارة."],
    }
