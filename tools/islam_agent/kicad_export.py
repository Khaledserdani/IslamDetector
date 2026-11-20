"""Generate editable KiCad schematic files from circuit schema v2.

Symbols are generated from the validated logical-pin model. Physical package
pin numbers are carried into KiCad pins; all net labels are placed on exact
pin endpoints. This first renderer uses conventional passive symbols and
generic labelled blocks for multi-pin devices pending a curated symbol cache.
"""
from __future__ import annotations

import re
import uuid

from circuit_components import COMPONENT_LIBRARY, validate_circuit_v2


FORMAT_VERSION = 20250114
GRID = 2.54


def _uid():
    return str(uuid.uuid4())


def _q(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def _num(value):
    return f"{float(value):.4f}".rstrip("0").rstrip(".")


def _balanced_sexpr(source):
    depth, quoted, escaped = 0, False, False
    for char in source:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0 and not quoted


def _pin_layout(kind, definition):
    pins = definition["pins"]
    if kind in {"resistor", "capacitor", "inductor", "dc_voltage_source", "dc_current_source"}:
        return {
            pins[0][0]: (-10.16, 0.0, 0.0),
            pins[1][0]: (10.16, 0.0, 180.0),
        }, (-5.08, -3.81, 5.08, 3.81)
    left, right, top, bottom = [], [], [], []
    for pin in pins:
        key, name, role = pin
        if role == "input":
            left.append(key)
        elif role == "output":
            right.append(key)
        elif role == "power_in":
            (top if len(top) <= len(bottom) else bottom).append(key)
        else:
            (left if len(left) <= len(right) else right).append(key)
    max_side = max(len(left), len(right), 1)
    height = max(12.7, (max_side + 1) * 3.81)
    layout = {}
    for side, values in (("left", left), ("right", right)):
        for index, key in enumerate(values):
            y = (index - (len(values)-1)/2) * 3.81
            layout[key] = (-15.24 if side == "left" else 15.24, y, 0.0 if side == "left" else 180.0)
    for side, values in (("top", top), ("bottom", bottom)):
        for index, key in enumerate(values):
            x = (index - (len(values)-1)/2) * 3.81
            layout[key] = (x, -height/2-5.08 if side == "top" else height/2+5.08,
                           90.0 if side == "top" else 270.0)
    return layout, (-10.16, -height/2, 10.16, height/2)


def _symbol_graphics(kind, bounds):
    x1, y1, x2, y2 = bounds
    stroke = '(stroke (width 0.254) (type default))'
    fill = '(fill (type background))'
    if kind == "resistor":
        return f'(rectangle (start {_num(x1)} {_num(y1)}) (end {_num(x2)} {_num(y2)}) {stroke} (fill (type none)))'
    if kind == "capacitor":
        return (
            f'(polyline (pts (xy -1.27 -3.81) (xy -1.27 3.81)) {stroke} (fill (type none)))'
            f'(polyline (pts (xy 1.27 -3.81) (xy 1.27 3.81)) {stroke} (fill (type none)))'
            f'(polyline (pts (xy -10.16 0) (xy -1.27 0)) {stroke} (fill (type none)))'
            f'(polyline (pts (xy 1.27 0) (xy 10.16 0)) {stroke} (fill (type none)))'
        )
    if kind == "inductor":
        pts = " ".join(f"(xy {x} {y})" for x,y in [(-5.08,0),(-3.81,-2.54),(-2.54,2.54),(-1.27,-2.54),(0,2.54),(1.27,-2.54),(2.54,2.54),(3.81,-2.54),(5.08,0)])
        return f'(polyline (pts {pts}) {stroke} (fill (type none)))'
    if kind in {"dc_voltage_source", "dc_current_source"}:
        return (
            f'(circle (center 0 0) (radius 3.81) {stroke} (fill (type none)))'
            f'(text "+" (at 0 -1.27 0) (effects (font (size 1.27 1.27))))'
            f'(text "-" (at 0 1.27 0) (effects (font (size 1.27 1.27))))'
        )
    return f'(rectangle (start {_num(x1)} {_num(y1)}) (end {_num(x2)} {_num(y2)}) {stroke} {fill})'


def _lib_symbol(part, definition, layout, bounds):
    ref, kind = part["ref"], part["type"]
    symbol_name = f"ISLAM_{ref}"
    graphics = _symbol_graphics(kind, bounds)
    pin_lines = []
    for key, pin_name, electrical_type in definition["pins"]:
        x, y, angle = layout[key]
        physical = part["pin_numbers"][key]
        pin_lines.append(
            f'(pin {electrical_type} line (at {_num(x)} {_num(y)} {_num(angle)}) (length 5.08)'
            f'(name {_q(pin_name)} (effects (font (size 1.0 1.0))))'
            f'(number {_q(physical)} (effects (font (size 1.0 1.0)))))'
        )
    in_bom = "no" if kind in {"ground", "test_point"} else "yes"
    on_board = "no" if kind == "ground" else "yes"
    return (
        f'(symbol {_q("ISLAM:"+symbol_name)} (pin_names (offset 1.016)) (in_bom {in_bom}) (on_board {on_board})'
        f'(property "Reference" {_q(ref)} (id 0) (at 0 -14 0) (effects (font (size 1.27 1.27))))'
        f'(property "Value" {_q(part.get("value", kind))} (id 1) (at 0 14 0) (effects (font (size 1.27 1.27))))'
        f'(property "Footprint" {_q(part.get("footprint", ""))} (id 2) (at 0 0 0) (effects (font (size 1 1)) hide))'
        f'(property "Datasheet" {_q(part.get("pinout_source", ""))} (id 3) (at 0 0 0) (effects (font (size 1 1)) hide))'
        f'(symbol {_q(symbol_name+"_0_1")} {graphics})'
        f'(symbol {_q(symbol_name+"_1_1")} {"".join(pin_lines)})'
        ')'
    )


def _placed_symbol(part, definition, layout, x, y, root_uuid, project_name):
    ref, kind = part["ref"], part["type"]
    symbol_uuid = _uid()
    pin_uuids = {}
    for key, _, _ in definition["pins"]:
        pin_uuids[part["pin_numbers"][key]] = _uid()
    value = str(part.get("value", kind))
    footprint = str(part.get("footprint", ""))
    in_bom = "no" if kind in {"ground", "test_point"} else "yes"
    on_board = "no" if kind == "ground" else "yes"
    props = (
        f'(property "Reference" {_q(ref)} (id 0) (at {_num(x)} {_num(y-12)} 0) (effects (font (size 1.27 1.27))))'
        f'(property "Value" {_q(value)} (id 1) (at {_num(x)} {_num(y+12)} 0) (effects (font (size 1.27 1.27))))'
        f'(property "Footprint" {_q(footprint)} (id 2) (at {_num(x)} {_num(y)} 0) (effects (font (size 1 1)) hide))'
        f'(property "Datasheet" {_q(part.get("pinout_source", ""))} (id 3) (at {_num(x)} {_num(y)} 0) (effects (font (size 1 1)) hide))'
        f'(property "ISLAM_Package" {_q(part.get("package", ""))} (id 4) (at {_num(x)} {_num(y)} 0) (effects (font (size 1 1)) hide))'
        f'(property "Manufacturer_Part" {_q(part.get("manufacturer_part", ""))} (id 5) (at {_num(x)} {_num(y)} 0) (effects (font (size 1 1)) hide))'
        f'(property "Simulation_Model_ID" {_q(part.get("model_id", ""))} (id 6) (at {_num(x)} {_num(y)} 0) (effects (font (size 1 1)) hide))'
        f'(property "Simulation_Model_Source" {_q(part.get("model_source", ""))} (id 7) (at {_num(x)} {_num(y)} 0) (effects (font (size 1 1)) hide))'
    )
    pins = "".join(f'(pin {_q(number)} (uuid {_q(pin_uuid)}))' for number,pin_uuid in pin_uuids.items())
    instance = (
        f'(symbol (lib_id {_q("ISLAM:ISLAM_"+ref)}) (at {_num(x)} {_num(y)} 0) (unit 1)'
        f'(in_bom {in_bom}) (on_board {on_board}) (uuid {_q(symbol_uuid)}) {props} {pins}'
        f'(instances (project {_q(project_name)} (path {_q("/"+root_uuid)} (reference {_q(ref)}) (unit 1))))'
        ')'
    )
    labels = []
    for key, _, _ in definition["pins"]:
        lx, ly, _ = layout[key]
        labels.append(
            f'(label {_q(part["pins"][key])} (at {_num(x+lx)} {_num(y+ly)} 0)'
            f'(effects (font (size 1.0 1.0)) (justify left bottom)) (uuid {_q(_uid())}))'
        )
    return instance, labels


def compile_kicad_schematic(spec, project_name="ISLAM"):
    design = validate_circuit_v2(spec)
    if not isinstance(project_name, str) or not re.fullmatch(r"[A-Za-z0-9 _-]{1,64}", project_name):
        raise ValueError("project_name must be a simple 1..64 character label")
    root_uuid = _uid()
    library, placed, labels = [], [], []
    columns = 4 if len(design["components"]) <= 24 else 6
    for index, part in enumerate(design["components"]):
        definition = COMPONENT_LIBRARY[part["type"]]
        layout, bounds = _pin_layout(part["type"], definition)
        library.append(_lib_symbol(part, definition, layout, bounds))
        col, row = index % columns, index // columns
        x, y = 45.72 + col*55.88, 40.64 + row*45.72
        instance, net_labels = _placed_symbol(part, definition, layout, x, y, root_uuid, project_name)
        placed.append(instance)
        labels.extend(net_labels)
    rows = (len(design["components"])+columns-1)//columns
    paper = "A3" if rows <= 4 else "A2" if rows <= 8 else "A1" if rows <= 16 else "A0"
    source = (
        f'(kicad_sch (version {FORMAT_VERSION}) (generator "islam-free-agent") (generator_version "0.2")'
        f'(uuid {_q(root_uuid)}) (paper "{paper}")'
        f'(title_block (title {_q(design["name"])}) (rev "prototype"))'
        f'(lib_symbols {"".join(library)})'
        + "".join(labels)
        + "".join(placed)
        + f'(sheet_instances (path "/" (page "1")))'
        + ')'
    )
    if not _balanced_sexpr(source):
        raise ValueError("generated KiCad schematic failed S-expression balance validation")
    pin_count = sum(len(COMPONENT_LIBRARY[p["type"]]["pins"]) for p in design["components"])
    label_count = len(labels)
    if pin_count != label_count:
        raise ValueError("not every logical pin received exactly one net label")
    bom_groups = {}
    for part in design["components"]:
        if part["type"] in {"ground", "test_point"}:
            continue
        rating = tuple(sorted((part.get("rating") or {}).items()))
        key = (part["type"], part.get("value"), part.get("unit"), part.get("package"),
               part.get("footprint"), part.get("manufacturer_part"), rating)
        if key not in bom_groups:
            bom_groups[key] = {"quantity": 0, "references": [], "type": part["type"],
                               "value": part.get("value"), "unit": part.get("unit"),
                               "package": part.get("package"), "footprint": part.get("footprint"),
                               "manufacturer_part": part.get("manufacturer_part"), "rating": dict(rating)}
        bom_groups[key]["quantity"] += 1
        bom_groups[key]["references"].append(part["ref"])
    bom = sorted(bom_groups.values(), key=lambda row: (row["type"], str(row["value"]), str(row["manufacturer_part"])))
    return {
        "filename": project_name.replace(" ", "_") + ".kicad_sch",
        "kicad_sch": source,
        "component_count": len(design["components"]),
        "pin_count": pin_count,
        "net_label_count": label_count,
        "bom": bom,
        "electrical_warnings": design["electrical_warnings"],
        "missing_bom_identity": design["missing_bom_identity"],
        "format_version": FORMAT_VERSION,
        "parser_check": "balanced S-expression",
        "kicad_cli_validation": "requires the dedicated KiCad CLI integration check",
        "build_ready": False,
    }
