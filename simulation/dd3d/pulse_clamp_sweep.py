#!/usr/bin/env python3
"""Compare ideal turn-off clamp levels; outputs are design comparisons, not ratings."""
import argparse
import csv
import copy
import json
from pathlib import Path
from pulse_engine import simulate_pulse

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",type=Path,default=Path("sample_pulse_config.json"))
    parser.add_argument("--output",type=Path,default=Path("clamp_sweep.csv"))
    parser.add_argument("--clamps",default="0,10,20,40,60,80")
    args=parser.parse_args()
    base=json.loads(args.input.read_text(encoding="utf-8"))
    clamps=[float(x) for x in args.clamps.split(",")]
    rows=[]
    for clamp in clamps:
        config=copy.deepcopy(base)
        config["pulse"]["clamp_voltage_v"]=clamp
        metrics,_=simulate_pulse(config)
        rows.append({
            "clamp_voltage_comparison_V":clamp,
            "peak_tx_current_A":metrics["peak_abs_tx_current_a"],
            "tx_current_at_turnoff_A":metrics["tx_current_at_turnoff_a"],
            "rx_direct_peak_after_1us_V":metrics["peak_abs_rx_direct_after_1us_v"],
            "rx_direct_peak_after_5us_V":metrics["peak_abs_rx_direct_after_5us_v"],
            "rx_direct_peak_after_10us_V":metrics["peak_abs_rx_direct_after_10us_v"],
            "rx_target_peak_after_1us_V":metrics["peak_abs_rx_target_after_1us_v"],
            "rx_target_peak_after_5us_V":metrics["peak_abs_rx_target_after_5us_v"],
            "rx_target_peak_after_10us_V":metrics["peak_abs_rx_target_after_10us_v"],
            "target_current_at_turnoff_A":metrics["target_current_at_turnoff_a"],
            "clamp_absorbed_energy_mJ":metrics["clamp_absorbed_energy_j"]*1e3,
            "energy_balance_relative_error":metrics["energy_balance_relative_error"]
        })
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
    print(f"PASS: {len(rows)} ideal clamp comparison cases -> {args.output}")
    print("WARNING: clamp levels are numerical scenarios only, not selected TVS/MOSFET ratings.")

if __name__=="__main__":
    main()
