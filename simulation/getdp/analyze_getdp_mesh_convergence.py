#!/usr/bin/env python3
"""Strict GetDP mesh audit: actual MSH2 counts, hashes, and medium/fine metrics."""
from __future__ import annotations
import csv
import hashlib
import math
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
LEVELS = (3, 4, 6)
TARGET_VOLUME_M3 = math.pi * 0.250**2 * 0.005
ACCEPTANCE_PERCENT = 5.0
NUMBER = re.compile(r"[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eEdD][-+]?[0-9]+)?")

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def msh2_counts(path: Path) -> tuple[int, int]:
    """Read actual ASCII Gmsh 2.x node and element block counts."""
    lines = path.read_text(errors="strict").splitlines()
    counts = {}
    for section, key in (("$Nodes", "nodes"), ("$Elements", "elements")):
        try:
            start = lines.index(section)
            count = int(lines[start + 1].strip())
        except (ValueError, IndexError) as exc:
            raise SystemExit(f"Invalid/missing {section} section in {path}") from exc
        if count <= 0 or start + 2 + count > len(lines):
            raise SystemExit(f"Invalid {section} count in {path}")
        counts[key] = count
    return counts["nodes"], counts["elements"]

def read_j2(path: Path):
    values = []
    for line in path.read_text(errors="replace").splitlines():
        nums = [float(x.replace("D", "E").replace("d", "e")) for x in NUMBER.findall(line)]
        if len(nums) >= 2:
            times = [x for x in nums[:-1] if -1e-12 <= x <= 400.001e-6]
            if times:
                values.append((times[0], nums[-1]))
    by_time = {t: q for t, q in values
               if math.isfinite(t) and math.isfinite(q) and q >= 0}
    rows = sorted(by_time.items())
    if len(rows) < 390:
        raise SystemExit(f"Expected >=390 unique J2 samples in {path}; got {len(rows)}")
    if any(rows[i][0] >= rows[i + 1][0] for i in range(len(rows) - 1)):
        raise SystemExit(f"Non-increasing time values in {path}")
    return [(t, math.sqrt(q / TARGET_VOLUME_M3)) for t, q in rows]

def nearest_value(rows, target, label, tolerance=1.1e-6):
    t, value = min(rows, key=lambda pair: abs(pair[0] - target))
    if abs(t - target) > tolerance:
        raise SystemExit(f"Missing {label} sample near {target * 1e6:.1f} us; nearest is {t * 1e6:.3f} us")
    return value

def trapezoid(rows):
    return sum((rows[i][1] + rows[i + 1][1]) * 0.5 *
               (rows[i + 1][0] - rows[i][0]) for i in range(len(rows) - 1))

def relative_change(a, b):
    scale = max(abs(a), abs(b), 1e-30)
    return abs(b - a) / scale * 100.0

records = []
mesh_hashes = set()
for divisions in LEVELS:
    folder = ROOT / f"gap-45mm-refine-{divisions}"
    mesh = folder / "model.msh"
    history = folder / "j2.txt"
    if not mesh.is_file() or not history.is_file():
        raise SystemExit(f"Missing mesh or J2 history for refinement {divisions}")
    nodes, elements = msh2_counts(mesh)
    digest = sha256(mesh)
    if digest in mesh_hashes:
        raise SystemExit(f"Duplicate mesh content at refinement {divisions}: {digest}")
    mesh_hashes.add(digest)
    rows = read_j2(history)
    peak_t, peak = max(rows, key=lambda pair: pair[1])
    records.append({
        "gap_mm": 45,
        "target_thickness_divisions": divisions,
        "nodes_actual_msh2": nodes,
        "elements_actual_msh2": elements,
        "mesh_sha256": digest,
        "samples": len(rows),
        "peak_time_us": peak_t * 1e6,
        "peak_volume_rms_J_A_per_m2": peak,
        "J_rms_at_150us_A_per_m2": nearest_value(rows, 150e-6, "150 us"),
        "J_rms_at_400us_A_per_m2": nearest_value(rows, 400e-6, "400 us"),
        "time_integral_rms_J_A_s_per_m2": trapezoid(rows),
    })

# A genuine refinement sequence must contain three distinct meshes and
# strictly increasing actual element counts, not merely increasing labels.
element_counts = [r["elements_actual_msh2"] for r in records]
if not (element_counts[0] < element_counts[1] < element_counts[2]):
    raise SystemExit(f"FAIL: actual element counts are not strictly increasing: {element_counts}")

coarse, medium, fine = records
metrics = (
    "peak_volume_rms_J_A_per_m2",
    "J_rms_at_150us_A_per_m2",
    "J_rms_at_400us_A_per_m2",
    "time_integral_rms_J_A_s_per_m2",
)
changes = {key: relative_change(medium[key], fine[key]) for key in metrics}
passed = all(math.isfinite(v) and v < ACCEPTANCE_PERCENT for v in changes.values())
for record in records:
    record["medium_to_fine_acceptance_percent"] = ""
    record["overall_convergence_status"] = ""
for key, value in changes.items():
    fine[f"change_{key}_medium_to_fine_percent"] = value
fine["overall_convergence_status"] = "CONVERGED" if passed else "NOT_CONVERGED"

out = ROOT / "getdp_mesh_convergence_45mm.csv"
fields = list(records[0])
for key in changes:
    fields.append(f"change_{key}_medium_to_fine_percent")
fields.append("overall_convergence_status")
with out.open("w", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(records)

manifest = ROOT / "mesh-integrity-sha256.txt"
with manifest.open("w") as stream:
    for divisions, record in zip(LEVELS, records):
        stream.write(f"{record['mesh_sha256']}  gap-45mm-refine-{divisions}/model.msh\n")

print("GETDP_MESH_CONVERGENCE_45MM")
for record in records:
    print(record)
print("MEDIUM_TO_FINE_RELATIVE_CHANGES_PERCENT")
for key, value in changes.items():
    print(f"{key}: {value:.6f}%")
print(f"ACCEPTANCE_LIMIT_PERCENT: {ACCEPTANCE_PERCENT:.3f}")
print(f"RESULT: {'CONVERGED' if passed else 'NOT_CONVERGED'}")
print(f"WROTE: {out}")
print(f"WROTE: {manifest}")
if not passed:
    raise SystemExit("GetDP mesh convergence acceptance failed; no convergence claim is permitted.")
