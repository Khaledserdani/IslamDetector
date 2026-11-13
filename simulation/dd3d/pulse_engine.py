#!/usr/bin/env python3
"""Reduced-order coupled TX/target PI pulse engine with open-circuit RX sensing.

This is a circuit-domain transient kernel. It requires measured or independently
computed L/R/M inputs and a target-loop equivalent. It is not a 3D conductor FEM.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path
import numpy as np
from filament_model import mutual_inductance

MODEL = "coupled_tx_target_rl_with_clamped_turnoff_open_circuit_rx"

def _positive(value, name):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value

def _finite(value, name):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value

def validate_inductance_matrix(ltx, ltarget, lrx, mtx_target, mtx_rx, mrx_target):
    """Require positive-definite 3-coil inductance matrix (strict passivity check)."""
    matrix = np.array([
        [ltx, mtx_target, mtx_rx],
        [mtx_target, ltarget, mrx_target],
        [mtx_rx, mrx_target, lrx],
    ], dtype=float)
    if not np.isfinite(matrix).all() or not np.allclose(matrix, matrix.T, rtol=0, atol=1e-18):
        raise ValueError("inductance matrix must be finite and symmetric")
    eigenvalues = np.linalg.eigvalsh(matrix)
    if eigenvalues[0] <= max(eigenvalues[-1] * 1e-10, 1e-18):
        raise ValueError(
            "non-passive or singular TX/target/RX coupling matrix; "
            f"minimum eigenvalue={eigenvalues[0]:.9g} H"
        )
    return eigenvalues

def simulate_pulse(config):
    """Simulate TX and one equivalent target eddy-current loop; RX remains open-circuit."""
    pulse = config["pulse"]
    target = config["target"]
    electrical = config["electrical"]

    ltx = _positive(electrical["tx_inductance_h"], "tx_inductance_h")
    rtx = _positive(electrical["tx_resistance_ohm"], "tx_resistance_ohm")
    lrx = _positive(electrical["rx_inductance_h"], "rx_inductance_h")
    ltarget = _positive(target["inductance_h"], "target.inductance_h")
    rtarget = _positive(target["resistance_ohm"], "target.resistance_ohm")
    vbus = _positive(pulse["bus_voltage_v"], "bus_voltage_v")
    width = _positive(pulse["pulse_width_s"], "pulse_width_s")
    clamp = _finite(pulse.get("clamp_voltage_v", 0.0), "clamp_voltage_v")
    if clamp < 0:
        raise ValueError("clamp_voltage_v cannot be negative")
    dt_nominal = _positive(pulse["time_step_s"], "time_step_s")
    stop = _positive(pulse["stop_time_s"], "stop_time_s")
    if stop <= width:
        raise ValueError("stop_time_s must be later than pulse_width_s")

    paths = config["paths_m"]
    turns = config["turns"]
    ntx, nrx = int(turns["TX"]), int(turns["RX"])
    ntarget = int(turns.get("target_loop", 1))
    if min(ntx, nrx, ntarget) < 1:
        raise ValueError("turn counts must be positive integers")
    tx_path, rx_path, target_path = paths["TX"], paths["RX"], paths["target_loop"]
    mtx_target = mutual_inductance(tx_path, target_path, ntx, ntarget)
    mtx_rx = mutual_inductance(tx_path, rx_path, ntx, nrx)
    mrx_target = mutual_inductance(rx_path, target_path, nrx, ntarget)
    eigenvalues = validate_inductance_matrix(
        ltx, ltarget, lrx, mtx_target, mtx_rx, mrx_target
    )

    det = ltx * ltarget - mtx_target * mtx_target
    if det <= 0:
        raise ValueError("TX/target inductance submatrix is not positive definite")

    def derivative(state, drive_on):
        itx, itarget = state
        v_clamp = 0.0 if drive_on else clamp * (1.0 if itx > 0 else -1.0 if itx < 0 else 0.0)
        applied = (vbus if drive_on else 0.0) - rtx * itx - v_clamp
        dtx = (ltarget * applied + mtx_target * rtarget * itarget) / det
        dtarget = (-mtx_target * applied - ltx * rtarget * itarget) / det
        return np.array([dtx, dtarget], dtype=float)

    def energy(state):
        itx, itarget = state
        return 0.5 * ltx * itx * itx + mtx_target * itx * itarget + 0.5 * ltarget * itarget * itarget

    times = [0.0]
    states = [np.array([0.0, 0.0], dtype=float)]
    derivatives = [derivative(states[0], True)]
    source_power = [0.0]
    tx_loss_power = [0.0]
    target_loss_power = [0.0]
    clamp_power = [0.0]

    t = 0.0
    state = states[0].copy()
    while t < stop - max(1e-15, stop * 1e-14):
        # Split exactly at the switch transition so no RK4 step straddles it.
        drive_on = t < width - max(1e-15, width * 1e-14)
        boundary = width if drive_on else stop
        h = min(dt_nominal, stop - t, boundary - t)
        if h <= 0:
            raise RuntimeError("non-positive integration step")
        k1 = derivative(state, drive_on)
        k2 = derivative(state + 0.5*h*k1, drive_on)
        k3 = derivative(state + 0.5*h*k2, drive_on)
        k4 = derivative(state + h*k3, drive_on)
        state = state + (h/6.0)*(k1 + 2*k2 + 2*k3 + k4)
        t = min(t+h, stop)
        deriv = derivative(state, drive_on)
        itx, itarget = map(float, state)
        times.append(t)
        states.append(state.copy())
        derivatives.append(deriv)
        source_power.append(vbus * itx if drive_on else 0.0)
        tx_loss_power.append(rtx * itx * itx)
        target_loss_power.append(rtarget * itarget * itarget)
        clamp_power.append(0.0 if drive_on else clamp * abs(itx))

    times_a = np.asarray(times)
    states_a = np.asarray(states)
    deriv_a = np.asarray(derivatives)
    itx = states_a[:, 0]
    itarget = states_a[:, 1]
    ditx = deriv_a[:, 0]
    ditarget = deriv_a[:, 1]
    vrx_direct = -mtx_rx * ditx
    vrx_target = -mrx_target * ditarget
    vrx_total = vrx_direct + vrx_target

    def integrate(power):
        return float(np.trapezoid(np.asarray(power, dtype=float), times_a))

    source_energy = integrate(source_power)
    tx_copper_energy = integrate(tx_loss_power)
    target_copper_energy = integrate(target_loss_power)
    clamp_energy = integrate(clamp_power)
    stored_energy = np.asarray([energy(s) for s in states_a])
    energy_delta = float(stored_energy[-1] - stored_energy[0])
    energy_residual = source_energy - tx_copper_energy - target_copper_energy - clamp_energy - energy_delta

    post = times_a >= width
    metrics = {
        "model": MODEL,
        "model_status": "reduced_order_single_target_loop_surrogate_not_3d_conductor_fem",
        "coupling_h": {
            "M_TX_target_signed": mtx_target,
            "M_TX_RX_signed": mtx_rx,
            "M_RX_target_signed": mrx_target
        },
        "inductance_matrix_min_eigenvalue_h": float(eigenvalues[0]),
        "peak_abs_tx_current_a": float(np.max(np.abs(itx))),
        "tx_current_at_turnoff_a": float(np.interp(width, times_a, itx)),
        "peak_abs_target_loop_current_a": float(np.max(np.abs(itarget))),
        "peak_abs_rx_voltage_v": float(np.max(np.abs(vrx_total))),
        "peak_abs_rx_voltage_after_turnoff_v": float(np.max(np.abs(vrx_total[post]))),
        "peak_abs_rx_direct_component_v": float(np.max(np.abs(vrx_direct))),
        "peak_abs_rx_target_component_v": float(np.max(np.abs(vrx_target))),
        "source_energy_j": source_energy,
        "tx_copper_loss_j": tx_copper_energy,
        "target_copper_loss_j": target_copper_energy,
        "clamp_absorbed_energy_j": clamp_energy,
        "stored_magnetic_energy_change_j": energy_delta,
        "energy_balance_residual_j": energy_residual,
        "energy_balance_relative_error": abs(energy_residual) / max(abs(source_energy), 1e-18),
        "sample_count": int(len(times_a)),
        "time_step_nominal_s": dt_nominal,
        "pulse_width_s": width,
        "stop_time_s": stop,
        "turns": {"TX": ntx, "RX": nrx, "target_loop": ntarget}
    }
    arrays = {
        "time_s": times_a,
        "i_tx_a": itx,
        "i_target_a": itarget,
        "di_tx_dt_a_per_s": ditx,
        "di_target_dt_a_per_s": ditarget,
        "v_rx_direct_v": vrx_direct,
        "v_rx_target_v": vrx_target,
        "v_rx_total_v": vrx_total,
        "stored_magnetic_energy_j": stored_energy
    }
    return metrics, arrays

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("pulse-engine-output"))
    args = parser.parse_args()
    config = json.loads(args.input.read_text(encoding="utf-8"))
    metrics, arrays = simulate_pulse(config)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "pulse_waveform.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(arrays.keys())
        writer.writerows(zip(*arrays.values()))
    (args.output_dir / "pulse_metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2))

if __name__ == "__main__":
    main()
