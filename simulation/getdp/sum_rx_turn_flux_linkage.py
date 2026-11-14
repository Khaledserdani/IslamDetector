#!/usr/bin/env python3
"""Sum signed flux through individual RX turns into total flux linkage."""
from __future__ import annotations
import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path


def sum_linkage(input_path: Path, output_path: Path, expected_turns: int) -> None:
    if expected_turns <= 0:
        raise ValueError("expected_turns must be positive")
    grouped: dict[float, dict[str, float]] = defaultdict(dict)
    with input_path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {"turn_id", "time_s", "flux_per_turn_Wb"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Input CSV must contain turn_id,time_s,flux_per_turn_Wb")
        for line_no, row in enumerate(reader, start=2):
            turn_id = row["turn_id"].strip()
            if not turn_id:
                raise ValueError(f"Empty turn_id on line {line_no}")
            try:
                t = float(row["time_s"])
                phi = float(row["flux_per_turn_Wb"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid numeric data on line {line_no}") from exc
            if not math.isfinite(t) or not math.isfinite(phi):
                raise ValueError(f"Non-finite data on line {line_no}")
            if turn_id in grouped[t]:
                raise ValueError(f"Duplicate turn {turn_id} at time {t}")
            grouped[t][turn_id] = phi

    if len(grouped) < 2:
        raise ValueError("At least two time samples are required")
    all_turns = set().union(*(set(turns) for turns in grouped.values()))
    if len(all_turns) != expected_turns:
        raise ValueError(f"Expected {expected_turns} unique turns; found {len(all_turns)}")
    expected_ids = all_turns
    times = sorted(grouped)
    for t in times:
        if set(grouped[t]) != expected_ids:
            raise ValueError(f"Incomplete turn set at time {t}")
    with output_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["time_s", "turn_count", "flux_linkage_Wb_turn"])
        for t in times:
            linkage = sum(grouped[t].values())
            writer.writerow([f"{t:.12g}", expected_turns, f"{linkage:.12g}"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--turns", required=True, type=int)
    args = parser.parse_args()
    sum_linkage(args.input, args.output, args.turns)
    print(f"WROTE {args.output}")


if __name__ == "__main__":
    main()
