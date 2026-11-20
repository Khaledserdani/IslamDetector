"""Versioned multi-pin component library and circuit-spec validator.

The catalogue describes electrical pin roles and required ratings/models.
It does not claim that every catalogue entry already has a simulator model.
"""
from __future__ import annotations

import math
import re

NODE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
REF_RE = re.compile(r"^([A-Z]{1,3})([0-9]{1,4})$")

# Pin order is explicit and stable; SPICE order is deliberately not inferred
# from symbol artwork. Each component has a documented pin-number sequence.
COMPONENT_LIBRARY = {
    "resistor": {"prefix":"R","pins":[("1","1","passive"),("2","2","passive")],"value_unit":"ohm","rating":"power_w","spice":"R","model_required":False},
    "capacitor": {"prefix":"C","pins":[("1","1","passive"),("2","2","passive")],"value_unit":"F","rating":"voltage_v","spice":"C","model_required":False},
    "inductor": {"prefix":"L","pins":[("1","1","passive"),("2","2","passive")],"value_unit":"H","rating":"current_a","spice":"L","model_required":False},
    "dc_voltage_source": {"prefix":"V","pins":[("1","+","passive"),("2","-","passive")],"value_unit":"V","spice":"V","model_required":False},
    "dc_current_source": {"prefix":"I","pins":[("1","+","passive"),("2","-","passive")],"value_unit":"A","spice":"I","model_required":False},
    "potentiometer": {"prefix":"RV","pins":[("1","A","passive"),("2","W","passive"),("3","B","passive")],"value_unit":"ohm","rating":"power_w","spice":"POT","model_required":False},
    "diode": {"prefix":"D","pins":[("1","A","passive"),("2","K","passive")],"value_unit":None,"spice":"D","model_required":True},
    "zener_diode": {"prefix":"DZ","pins":[("1","A","passive"),("2","K","passive")],"value_unit":None,"spice":"D","model_required":True},
    "schottky_diode": {"prefix":"D","pins":[("1","A","passive"),("2","K","passive")],"value_unit":None,"spice":"D","model_required":True},
    "led": {"prefix":"LED","pins":[("1","A","passive"),("2","K","passive")],"value_unit":None,"spice":"D","model_required":True},
    "bjt_npn": {"prefix":"Q","pins":[("1","B","input"),("2","C","passive"),("3","E","passive")],"value_unit":None,"spice":"Q","model_required":True},
    "bjt_pnp": {"prefix":"Q","pins":[("1","B","input"),("2","C","passive"),("3","E","passive")],"value_unit":None,"spice":"Q","model_required":True},
    "mosfet_n": {"prefix":"M","pins":[("1","G","input"),("2","D","passive"),("3","S","passive"),("4","B","passive")],"value_unit":None,"spice":"M","model_required":True},
    "mosfet_p": {"prefix":"M","pins":[("1","G","input"),("2","D","passive"),("3","S","passive"),("4","B","passive")],"value_unit":None,"spice":"M","model_required":True},
    "jfet_n": {"prefix":"J","pins":[("1","G","input"),("2","D","passive"),("3","S","passive")],"value_unit":None,"spice":"J","model_required":True},
    "jfet_p": {"prefix":"J","pins":[("1","G","input"),("2","D","passive"),("3","S","passive")],"value_unit":None,"spice":"J","model_required":True},
    "igbt_n": {"prefix":"Q","pins":[("1","G","input"),("2","C","passive"),("3","E","passive")],"value_unit":None,"spice":"X","model_required":True},
    "opamp": {"prefix":"U","pins":[("1","OUT","output"),("2","IN-","input"),("3","IN+","input"),("4","V-","power_in"),("5","V+","power_in")],"value_unit":None,"spice":"X","model_required":True},
    "comparator": {"prefix":"U","pins":[("1","OUT","output"),("2","IN-","input"),("3","IN+","input"),("4","V-","power_in"),("5","V+","power_in")],"value_unit":None,"spice":"X","model_required":True},
    "timer_555": {"prefix":"U","pins":[("1","GND","power_in"),("2","TRIG","input"),("3","OUT","output"),("4","RESET","input"),("5","CTRL","input"),("6","THRESH","input"),("7","DISCH","output"),("8","VCC","power_in")],"value_unit":None,"spice":"X","model_required":True},
    "logic_gate_2input": {"prefix":"U","pins":[("1","A","input"),("2","B","input"),("3","Y","output"),("4","VSS","power_in"),("5","VDD","power_in")],"value_unit":None,"spice":"X","model_required":True},
    "d_flip_flop": {"prefix":"U","pins":[("1","D","input"),("2","CLK","input"),("3","Q","output"),("4","Q_N","output"),("5","VSS","power_in"),("6","VDD","power_in")],"value_unit":None,"spice":"X","model_required":True},
    "switch_spst": {"prefix":"S","pins":[("1","A","passive"),("2","B","passive")],"value_unit":None,"spice":"S","model_required":True},
    "switch_spdt": {"prefix":"S","pins":[("1","COM","passive"),("2","NO","passive"),("3","NC","passive")],"value_unit":None,"spice":"S","model_required":True},
    "transformer_1p1s": {"prefix":"T","pins":[("1","P1","passive"),("2","P2","passive"),("3","S1","passive"),("4","S2","passive")],"value_unit":None,"spice":"K","model_required":True},
    "connector_2": {"prefix":"J","pins":[("1","1","passive"),("2","2","passive")],"value_unit":None,"spice":None,"model_required":False},
    "connector_3": {"prefix":"J","pins":[("1","1","passive"),("2","2","passive"),("3","3","passive")],"value_unit":None,"spice":None,"model_required":False},
    "connector_4": {"prefix":"J","pins":[("1","1","passive"),("2","2","passive"),("3","3","passive"),("4","4","passive")],"value_unit":None,"spice":None,"model_required":False},
    "test_point": {"prefix":"TP","pins":[("1","1","passive")],"value_unit":None,"spice":None,"model_required":False},
    "ground": {"prefix":"GND","pins":[("1","GND","passive")],"value_unit":None,"spice":None,"model_required":False},
}

class CircuitSchemaError(ValueError):
    """Raised when a multi-pin circuit specification is invalid."""


def component_catalog():
    return {
        name: {
            "reference_prefix": item["prefix"],
            "pins": [{"logical_key": p[0], "name": p[1], "electrical_type": p[2]} for p in item["pins"]],
            "value_unit": item["value_unit"],
            "required_rating": item.get("rating"),
            "spice_primitive": item["spice"],
            "simulation_model_required": item["model_required"],
            "pin_number_policy": "must be supplied from the selected package datasheet",
            "package_pin_map_required": True,
        }
        for name, item in COMPONENT_LIBRARY.items()
    }


def validate_circuit_v2(spec):
    if not isinstance(spec, dict) or set(spec) != {"schema_version","name","ground","components"}:
        raise CircuitSchemaError("schema v2 requires schema_version, name, ground, components")
    if spec["schema_version"] != 2:
        raise CircuitSchemaError("only circuit schema version 2 is accepted")
    name, ground, parts = spec["name"], spec["ground"], spec["components"]
    if not isinstance(name,str) or not name.strip() or len(name)>120:
        raise CircuitSchemaError("name must contain 1..120 characters")
    if not isinstance(ground,str) or not NODE_RE.fullmatch(ground):
        raise CircuitSchemaError("ground must be a valid node label")
    if not isinstance(parts,list) or not 1<=len(parts)<=256:
        raise CircuitSchemaError("component count must be between 1 and 256")
    refs, nodes, normalized = set(), {ground}, []
    net_roles = {}
    warnings = []
    for part in parts:
        if not isinstance(part,dict) or set(part)-{"ref","type","pins","pin_numbers","value","unit","rating","model_id","package","manufacturer_part","pinout_source","model_source"}:
            raise CircuitSchemaError("component fields are invalid")
        kind=part.get("type")
        if kind not in COMPONENT_LIBRARY:
            raise CircuitSchemaError(f"unsupported component type: {kind}")
        definition=COMPONENT_LIBRARY[kind]
        ref=part.get("ref")
        match=REF_RE.fullmatch(ref) if isinstance(ref,str) else None
        if not match or match.group(1) != definition["prefix"] or ref in refs:
            raise CircuitSchemaError("reference designator is invalid, mismatched, or duplicated")
        refs.add(ref)
        pins=part.get("pins")
        required_pin_numbers={p[0] for p in definition["pins"]}
        if not isinstance(pins,dict) or set(pins)!=required_pin_numbers:
            raise CircuitSchemaError(f"{kind} requires exact logical pin keys {sorted(required_pin_numbers)}")
        pin_numbers=part.get("pin_numbers")
        if not isinstance(pin_numbers,dict) or set(pin_numbers)!=required_pin_numbers:
            raise CircuitSchemaError(f"{ref} requires a physical pin-number map for every logical pin")
        physical=[]
        for pin,node in pins.items():
            if not isinstance(node,str) or not NODE_RE.fullmatch(node):
                raise CircuitSchemaError(f"invalid net label on {ref} logical pin {pin}")
            physical_number=pin_numbers[pin]
            if not isinstance(physical_number,str) or not re.fullmatch(r"[A-Za-z0-9_]{1,8}",physical_number):
                raise CircuitSchemaError(f"invalid package pin number for {ref} logical pin {pin}")
            physical.append(physical_number)
            nodes.add(node)
            role = next(p[2] for p in definition["pins"] if p[0] == pin)
            net_roles.setdefault(node, []).append((ref, pin, role))
        if len(set(physical))!=len(physical):
            raise CircuitSchemaError(f"{ref} maps multiple logical pins to one physical package pin")
        if len(nodes)>512:
            raise CircuitSchemaError("circuit exceeds 512 distinct nets")
        unit=definition["value_unit"]
        if unit is not None:
            value=part.get("value")
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
                raise CircuitSchemaError(f"{ref} requires a finite positive value")
            if part.get("unit")!=unit:
                raise CircuitSchemaError(f"{ref} value unit must be {unit}")
        elif "value" in part or "unit" in part:
            raise CircuitSchemaError(f"{ref} does not accept a scalar value/unit")
        rating_name=definition.get("rating")
        rating=part.get("rating")
        if rating_name:
            if not isinstance(rating,dict) or set(rating)!={rating_name}:
                raise CircuitSchemaError(f"{ref} requires rating.{rating_name}")
            rating_value=rating[rating_name]
            if isinstance(rating_value,bool) or not isinstance(rating_value,(int,float)) or not math.isfinite(rating_value) or rating_value<=0:
                raise CircuitSchemaError(f"{ref} rating.{rating_name} must be positive and finite")
        elif rating is not None:
            raise CircuitSchemaError(f"{ref} does not accept this rating field")
        model_id=part.get("model_id")
        if definition["model_required"] and (not isinstance(model_id,str) or not model_id.strip() or len(model_id)>160):
            raise CircuitSchemaError(f"{ref} requires a model_id before simulation")
        if definition["model_required"]:
            pinout_source=part.get("pinout_source")
            if not isinstance(pinout_source,str) or not pinout_source.strip() or len(pinout_source)>500:
                raise CircuitSchemaError(f"{ref} requires a pinout_source identifying the exact datasheet and package revision")
        model_source=part.get("model_source")
        if model_source is not None and (not isinstance(model_source,str) or not model_source.strip() or len(model_source)>500):
            raise CircuitSchemaError(f"{ref} model_source must identify a source within 500 characters")
        if not definition["model_required"] and model_id is not None and (not isinstance(model_id,str) or len(model_id)>160):
            raise CircuitSchemaError(f"{ref} model_id is invalid")
        for optional in ("package","manufacturer_part"):
            value=part.get(optional)
            if value is not None and (not isinstance(value,str) or not value.strip() or len(value)>160):
                raise CircuitSchemaError(f"{ref} {optional} must be non-empty text")
        normalized.append(dict(part))
    for node, roles in net_roles.items():
        outputs = [(ref, pin) for ref, pin, role in roles if role == "output"]
        if len(outputs) > 1:
            raise CircuitSchemaError(f"net {node} has multiple push-pull output drivers: {outputs}")
        if all(role in {"input", "power_in"} for _, _, role in roles):
            warnings.append(f"net {node} may be floating; it contains only input/power-input pins")
        if len(roles) == 1 and roles[0][2] == "passive":
            warnings.append(f"net {node} has a single passive pin and may be an unconnected stub")
    if ground not in net_roles:
        warnings.append(f"reference ground node {ground} is not connected to any component pin")
    model_refs = [p["ref"] for p in normalized if COMPONENT_LIBRARY[p["type"]]["model_required"]]
    missing_bom_identity = [p["ref"] for p in normalized if not p.get("package") or not p.get("manufacturer_part")]
    return {"schema_version":2,"name":name.strip(),"ground":ground,"components":normalized,
            "nodes":sorted(nodes),"component_count":len(normalized),
            "electrical_warnings":warnings,
            "simulation_ready":False,
            "models_requiring_independent_verification":model_refs,
            "simulation_status":"engine integration and model verification are pending",
            "missing_bom_identity":missing_bom_identity,
            "build_ready":False}
