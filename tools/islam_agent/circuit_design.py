"""Deterministic circuit-spec validator and schematic artifact compiler.

The first version intentionally supports two-terminal linear parts only.
It emits a SPICE-compatible netlist, a labelled SVG schematic, and a BOM.
It does not infer missing ratings or claim unsupported IC pin-level designs.
"""
from __future__ import annotations

import html
import math
import re
from collections import defaultdict

MAX_COMPONENTS = 64
MAX_NODES = 32
NODE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,23}$")
REF_RE = re.compile(r"^[RCLV][0-9]{1,3}$")

_COMPONENTS = {
    "resistor": {"prefix": "R", "unit": "ohm", "spice": "R"},
    "capacitor": {"prefix": "C", "unit": "F", "spice": "C"},
    "inductor": {"prefix": "L", "unit": "H", "spice": "L"},
    "dc_voltage_source": {"prefix": "V", "unit": "V", "spice": "V"},
}
_RANGES = {
    "resistor": (1e-6, 1e9),
    "capacitor": (1e-12, 1.0),
    "inductor": (1e-9, 1e3),
    "dc_voltage_source": (0.0, 10000.0),
}


class CircuitDesignError(ValueError):
    """Raised when a circuit specification is incomplete or unsafe."""


def validate_design(spec):
    if not isinstance(spec, dict) or set(spec) != {"name", "ground", "components"}:
        raise CircuitDesignError("design requires exactly name, ground, components")
    name, ground, components = spec["name"], spec["ground"], spec["components"]
    if not isinstance(name, str) or not name.strip() or len(name) > 80:
        raise CircuitDesignError("name must be 1..80 characters")
    if not isinstance(ground, str) or not NODE_RE.fullmatch(ground):
        raise CircuitDesignError("ground must be a valid node label")
    if not isinstance(components, list) or not 1 <= len(components) <= MAX_COMPONENTS:
        raise CircuitDesignError("component count must be between 1 and 64")

    refs, nodes = set(), {ground}
    normalized = []
    for part in components:
        if not isinstance(part, dict):
            raise CircuitDesignError("each component must be an object")
        kind = part.get("type")
        if kind not in _COMPONENTS:
            raise CircuitDesignError("unsupported component type")
        required = {"ref", "type", "pins", "value", "unit"}
        if kind == "resistor":
            required |= {"rating_power_w", "tolerance_pct"}
        elif kind == "capacitor":
            required |= {"rating_voltage_v", "tolerance_pct"}
        elif kind == "inductor":
            required |= {"rating_current_a", "tolerance_pct"}
        if set(part) != required:
            raise CircuitDesignError(f"{kind} fields do not match the required schema")
        ref = part["ref"]
        if not isinstance(ref, str) or not REF_RE.fullmatch(ref) or ref[0] != _COMPONENTS[kind]["prefix"]:
            raise CircuitDesignError("reference designator does not match component type")
        if ref in refs:
            raise CircuitDesignError("component references must be unique")
        refs.add(ref)
        if part["unit"] != _COMPONENTS[kind]["unit"]:
            raise CircuitDesignError("component unit does not match its type")
        pins = part["pins"]
        if not isinstance(pins, dict) or set(pins) != {"1", "2"}:
            raise CircuitDesignError("two-terminal parts require pins 1 and 2")
        if not all(isinstance(pins[p], str) and NODE_RE.fullmatch(pins[p]) for p in ("1", "2")):
            raise CircuitDesignError("pin nodes must be valid labels")
        if pins["1"] == pins["2"]:
            raise CircuitDesignError("both component pins cannot connect to the same node")
        nodes.update((pins["1"], pins["2"]))
        value = part["value"]
        low, high = _RANGES[kind]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise CircuitDesignError("component value is outside its supported finite range")
        clean = dict(part)
        if kind == "resistor":
            rating = part["rating_power_w"]
            if isinstance(rating, bool) or not isinstance(rating, (int, float)) or not math.isfinite(rating) or not 0 < rating <= 10000:
                raise CircuitDesignError("resistor power rating must be within (0, 10000] W")
        elif kind == "capacitor":
            rating = part["rating_voltage_v"]
            if isinstance(rating, bool) or not isinstance(rating, (int, float)) or not math.isfinite(rating) or not 0 < rating <= 100000:
                raise CircuitDesignError("capacitor voltage rating must be within (0, 100000] V")
        elif kind == "inductor":
            rating = part["rating_current_a"]
            if isinstance(rating, bool) or not isinstance(rating, (int, float)) or not math.isfinite(rating) or not 0 < rating <= 10000:
                raise CircuitDesignError("inductor current rating must be within (0, 10000] A")
        if kind != "dc_voltage_source":
            tolerance = part["tolerance_pct"]
            if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not math.isfinite(tolerance) or not 0 < tolerance <= 50:
                raise CircuitDesignError("tolerance_pct must be within (0, 50]")
        normalized.append(clean)
    if len(nodes) > MAX_NODES:
        raise CircuitDesignError("design exceeds the 32-node limit")
    return {"name": name.strip(), "ground": ground, "components": normalized, "nodes": sorted(nodes)}


def _spice_value(value):
    return format(float(value), ".12g")


def _svg_symbol(kind, x, y):
    if kind == "resistor":
        pts = [(x, y), (x+10, y), (x+17, y-8), (x+27, y+8),
               (x+37, y-8), (x+47, y+8), (x+54, y), (x+64, y)]
        return '<polyline points="' + " ".join(f"{a},{b}" for a,b in pts) + '" fill="none" stroke="#172b4d" stroke-width="2"/>'
    if kind == "capacitor":
        return (f'<line x1="{x}" y1="{y}" x2="{x+30}" y2="{y}" stroke="#172b4d" stroke-width="2"/>'
                f'<line x1="{x+30}" y1="{y-12}" x2="{x+30}" y2="{y+12}" stroke="#172b4d" stroke-width="2"/>'
                f'<line x1="{x+38}" y1="{y-12}" x2="{x+38}" y2="{y+12}" stroke="#172b4d" stroke-width="2"/>'
                f'<line x1="{x+38}" y1="{y}" x2="{x+64}" y2="{y}" stroke="#172b4d" stroke-width="2"/>')
    if kind == "inductor":
        return (f'<path d="M{x} {y} h8 c0 -16 16 -16 16 0 c0 -16 16 -16 16 0 c0 -16 16 -16 16 0 h8" '
                'fill="none" stroke="#172b4d" stroke-width="2"/>')
    return (f'<line x1="{x}" y1="{y}" x2="{x+21}" y2="{y}" stroke="#172b4d" stroke-width="2"/>'
            f'<circle cx="{x+34}" cy="{y}" r="13" fill="white" stroke="#172b4d" stroke-width="2"/>'
            f'<line x1="{x+47}" y1="{y}" x2="{x+64}" y2="{y}" stroke="#172b4d" stroke-width="2"/>'
            f'<text x="{x+34}" y="{y+5}" text-anchor="middle" font-size="14">+</text>')


def compile_circuit_design(spec):
    design = validate_design(spec)
    lines = ["* ISLAM FREE AGENT generated circuit", f"* {design['name']}", f".title {design['name']}"]
    bom = defaultdict(int)
    svg_rows = []
    width, row_h, top = 760, 78, 78
    for index, part in enumerate(design["components"]):
        kind = part["type"]
        a, b = part["pins"]["1"], part["pins"]["2"]
        lines.append(f"{part['ref']} {a} {b} {_spice_value(part['value'])}")
        key = (kind, float(part["value"]), part["unit"], part.get("rating_power_w"),
               part.get("rating_voltage_v"), part.get("rating_current_a"), part.get("tolerance_pct"))
        bom[key] += 1
        y = top + index * row_h
        svg_rows.append(
            f'<text x="24" y="{y+5}" font-size="13" font-weight="bold">{html.escape(part["ref"])}</text>'
            f'<text x="118" y="{y+5}" font-size="12">{html.escape(a)}</text>'
            f'<line x1="145" y1="{y}" x2="250" y2="{y}" stroke="#172b4d" stroke-width="2"/>'
            f'{_svg_symbol(kind, 250, y)}'
            f'<line x1="314" y1="{y}" x2="430" y2="{y}" stroke="#172b4d" stroke-width="2"/>'
            f'<text x="440" y="{y+5}" font-size="12">{html.escape(b)}</text>'
            f'<text x="540" y="{y+5}" font-size="12">{_spice_value(part["value"])} {part["unit"]}</text>'
            f'<text x="650" y="{y+5}" font-size="11" fill="#52647a">pins 1 → 2</text>'
        )
    lines.extend([".op", ".end"])
    bom_rows = []
    for key, quantity in sorted(bom.items(), key=lambda item: (item[0][0], item[0][1])):
        kind, value, unit, pwr, volt, current, tolerance = key
        ratings = []
        if pwr is not None: ratings.append(f"{pwr:g} W")
        if volt is not None: ratings.append(f"{volt:g} V")
        if current is not None: ratings.append(f"{current:g} A")
        if tolerance is not None: ratings.append(f"±{tolerance:g}%")
        bom_rows.append({
            "quantity": quantity, "type": kind, "value": _spice_value(value),
            "unit": unit, "ratings": ", ".join(ratings) or "source model",
        })
    height = top + len(design["components"]) * row_h + 30
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" fill="white"/>'
        f'<text x="24" y="32" font-size="18" font-weight="bold">{html.escape(design["name"])}</text>'
        '<text x="24" y="54" font-size="11" fill="#52647a">Two-terminal schematic view • identical node labels denote electrical connection</text>'
        + "".join(svg_rows) + '</svg>'
    )
    return {
        "design_name": design["name"],
        "node_labels": design["nodes"],
        "component_count": len(design["components"]),
        "bom": bom_rows,
        "spice_netlist": "\n".join(lines) + "\n",
        "schematic_svg": svg,
        "pin_convention": "All supported components are two-terminal: pin 1 is the first net, pin 2 is the second net.",
        "scope": [
            "يدعم حالياً المقاومات والمكثفات والمحاثات ومصادر الجهد المستمر ذات الطرفين فقط.",
            "المخطط يربط الشبكات بتسميات العقد؛ يجب أن تتطابق التسميات حرفياً لتمثل اتصالاً كهربائياً.",
            "لا يدعم بعد الدارات المتكاملة أو الترانزستورات أو الدايودات أو PCB أو التوصيلات متعددة الأرجل.",
            "قيم التصنيف والتفاوت مطلوبة للمكونات السلبية، لكن فحص الإجهاد التفصيلي يحتاج محللات DC/AC/Transient المناسبة."
        ],
    }
