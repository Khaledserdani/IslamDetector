#!/usr/bin/env python3
"""Run 3D TX field and TX/RX mutual-inductance reference calculations."""
import argparse
import json
from pathlib import Path
from filament_model import field_at_points, mutual_inductance, path_length_m

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("geometry", type=Path, help="JSON geometry input")
    parser.add_argument("--output", type=Path, default=Path("dd3d_reference.json"))
    args = parser.parse_args()
    data = json.loads(args.geometry.read_text(encoding="utf-8"))
    tx, rx = data["paths_m"]["TX"], data["paths_m"]["RX"]
    points = data["observation_points_m"]
    ntx, nrx = int(data["turns"]["TX"]), int(data["turns"]["RX"])
    current = float(data.get("tx_current_a", 1.0))
    b = field_at_points(tx, points, current_a=current, turns=ntx)
    m = mutual_inductance(tx, rx, turns_a=ntx, turns_b=nrx)
    tx_path = path_length_m(tx)
    rx_path = path_length_m(rx)
    wire_lengths = data.get("wire_lengths_m", {})
    result = {
        "schema_version": "1.0",
        "model": "3d_filament_biot_savart_neumann_midpoint",
        "status": "geometry_driven_reference_not_full_PI_or_soil_model",
        "units": {"coordinates":"m","current":"A","B":"T","M":"H"},
        "turns": {"TX":ntx,"RX":nrx},
        "tx_current_a": current,
        "geometry_metrics": {
            "TX_single_turn_centerline_length_m": tx_path,
            "RX_single_turn_centerline_length_m": rx_path,
            "TX_total_wire_length_budget_m": wire_lengths.get("TX"),
            "RX_total_wire_length_budget_m": wire_lengths.get("RX"),
            "TX_average_wire_length_per_turn_m": (float(wire_lengths["TX"]) / ntx) if "TX" in wire_lengths else None,
            "RX_average_wire_length_per_turn_m": (float(wire_lengths["RX"]) / nrx) if "RX" in wire_lengths else None,
            "TX_centerline_to_average_turn_length_ratio": (tx_path / (float(wire_lengths["TX"]) / ntx)) if "TX" in wire_lengths and float(wire_lengths["TX"]) > 0 else None,
            "RX_centerline_to_average_turn_length_ratio": (rx_path / (float(wire_lengths["RX"]) / nrx)) if "RX" in wire_lengths and float(wire_lengths["RX"]) > 0 else None
        },
        "observation_points_m": points,
        "tx_field_tesla": b.tolist(),
        "mutual_inductance_h_signed": m,
        "limitations": [
            "thin-filament centerline approximation",
            "midpoint numerical quadrature",
            "no conductive target or soil",
            "no pulse circuit, receiver front-end, or noise",
            "requires measured or CAD-exported 3D wire centerlines"
        ]
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {args.output}; signed M = {m:.9g} H")

if __name__ == "__main__":
    main()
