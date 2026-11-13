#!/usr/bin/env python3
"""Reduced-order coupled TX/target PI pulse engine with open-circuit RX sensing.

The target is represented by one equivalent eddy-current loop. A positive
turn-off clamp is treated as a one-way energy-absorption path: once TX current
reaches zero, reverse current is blocked and the target loop continues to decay.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path
import numpy as np
from filament_model import mutual_inductance

MODEL = "coupled_tx_target_rl_with_one_way_clamped_turnoff_open_circuit_rx"

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
    """Require a positive-definite symmetric three-coil inductance matrix."""
    matrix = np.array([
        [ltx, mtx_target, mtx_rx],
        [mtx_target, ltarget, mrx_target],
        [mtx_rx, mrx_target, lrx],
    ], dtype=float)
    if not np.isfinite(matrix).all():
        raise ValueError("inductance matrix must be finite")
    eigenvalues = np.linalg.eigvalsh(matrix)
    if eigenvalues[0] <= max(eigenvalues[-1] * 1e-10, 1e-18):
        raise ValueError(
            "non-passive or singular TX/target/RX coupling matrix; "
            f"minimum eigenvalue={eigenvalues[0]:.9g} H"
        )
    return eigenvalues

def simulate_pulse(config):
    """Simulate TX and one equivalent target eddy-current loop; RX stays open-circuit."""
    pulse, target, electrical = config["pulse"], config["target"], config["electrical"]
    ltx = _positive(electrical["tx_inductance_h"], "tx_inductance_h")
    rtx = _positive(electrical["tx_resistance_ohm"], "tx_resistance_ohm")
    lrx = _positive(electrical["rx_inductance_h"], "rx_inductance_h")
    lt = _positive(target["inductance_h"], "target.inductance_h")
    rt = _positive(target["resistance_ohm"], "target.resistance_ohm")
    vbus = _positive(pulse["bus_voltage_v"], "bus_voltage_v")
    width = _positive(pulse["pulse_width_s"], "pulse_width_s")
    clamp = _finite(pulse.get("clamp_voltage_v", 0.0), "clamp_voltage_v")
    if clamp < 0:
        raise ValueError("clamp_voltage_v cannot be negative")
    dt_nominal = _positive(pulse["time_step_s"], "time_step_s")
    stop = _positive(pulse["stop_time_s"], "stop_time_s")
    if stop <= width:
        raise ValueError("stop_time_s must be later than pulse_width_s")
    if math.ceil(stop / dt_nominal) > 200000:
        raise ValueError("requested simulation exceeds 200,000 time steps")

    paths, turns = config["paths_m"], config["turns"]
    ntx, nrx, nt = int(turns["TX"]), int(turns["RX"]), int(turns.get("target_loop", 1))
    if min(ntx, nrx, nt) < 1:
        raise ValueError("turn counts must be positive integers")
    tx_path, rx_path, target_path = paths["TX"], paths["RX"], paths["target_loop"]
    mtt = mutual_inductance(tx_path, target_path, ntx, nt)
    mtr = mutual_inductance(tx_path, rx_path, ntx, nrx)
    mrt = mutual_inductance(rx_path, target_path, nrx, nt)
    eigenvalues = validate_inductance_matrix(ltx, lt, lrx, mtt, mtr, mrt)
    det = ltx * lt - mtt * mtt
    if det <= max(ltx * lt * 1e-12, 1e-24):
        raise ValueError("TX/target inductance submatrix is not positive definite")

    def derivative(state, drive_on, tx_blocked=False):
        itx, itarget = map(float, state)
        if tx_blocked:
            # One-way turn-off path is open after the TX current reaches zero.
            return np.array([0.0, -rt * itarget / lt], dtype=float)
        v_clamp = 0.0 if drive_on else clamp
        applied = (vbus if drive_on else 0.0) - rtx * itx - v_clamp
        dtx = (lt * applied + mtt * rt * itarget) / det
        dtarget = (-mtt * applied - ltx * rt * itarget) / det
        return np.array([dtx, dtarget], dtype=float)

    def energy(state):
        itx, itarget = map(float, state)
        return 0.5 * ltx * itx * itx + mtt * itx * itarget + 0.5 * lt * itarget * itarget

    def rk4_step(state, h, drive_on, tx_blocked=False):
        s1 = state
        k1 = derivative(s1, drive_on, tx_blocked)
        s2 = state + 0.5 * h * k1
        k2 = derivative(s2, drive_on, tx_blocked)
        s3 = state + 0.5 * h * k2
        k3 = derivative(s3, drive_on, tx_blocked)
        s4 = state + h * k3
        k4 = derivative(s4, drive_on, tx_blocked)
        new_state = state + (h / 6.0) * (k1 + 2*k2 + 2*k3 + k4)

        def powers(stage):
            si, ti = map(float, stage)
            return (
                vbus * si if drive_on else 0.0,
                0.0 if tx_blocked else rtx * si * si,
                rt * ti * ti,
                0.0 if drive_on or tx_blocked else clamp * max(si, 0.0)
            )
        q1, q2, q3, q4 = map(powers, (s1, s2, s3, s4))
        integrals = tuple(
            h * (q1[k] + 2*q2[k] + 2*q3[k] + q4[k]) / 6.0
            for k in range(4)
        )
        return new_state, integrals

    times = [0.0]
    states = [np.array([0.0, 0.0], dtype=float)]
    derivatives = [derivative(states[0], True)]
    tx_blocked = False
    source_energy = tx_loss_energy = target_loss_energy = clamp_energy = 0.0
    t, state = 0.0, states[0].copy()
    while t < stop - max(1e-15, stop * 1e-14):
        drive_on = t < width - max(1e-15, width * 1e-14)
        boundary = width if drive_on else stop
        h = min(dt_nominal, stop - t, boundary - t)
        if h <= 0:
            raise RuntimeError("non-positive integration step")

        trial, _ = rk4_step(state, h, drive_on, tx_blocked)
        # Locate the one-way clamp current-zero event instead of allowing
        # an ideal constant-voltage clamp to chatter and create reverse current.
        hit_zero = (not drive_on and clamp > 0 and not tx_blocked
                    and state[0] > 0 and trial[0] <= 0)
        if hit_zero:
            lo, hi = 0.0, h
            for _ in range(48):
                mid = 0.5 * (lo + hi)
                candidate, _ = rk4_step(state, mid, False, False)
                if candidate[0] > 0:
                    lo = mid
                else:
                    hi = mid
            h = hi
            new_state, integrals = rk4_step(state, h, False, False)
            new_state[0] = 0.0
            tx_blocked = True
        else:
            new_state, integrals = rk4_step(state, h, drive_on, tx_blocked)

        source_energy += integrals[0]
        tx_loss_energy += integrals[1]
        target_loss_energy += integrals[2]
        clamp_energy += integrals[3]
        state = new_state
        t = min(t + h, stop)
        sample_on = t < width - max(1e-15, width * 1e-14)
        deriv = derivative(state, sample_on, tx_blocked)
        times.append(t)
        states.append(state.copy())
        derivatives.append(deriv)

    times_a = np.asarray(times)
    states_a = np.asarray(states)
    deriv_a = np.asarray(derivatives)
    itx, itarget = states_a[:, 0], states_a[:, 1]
    ditx, ditarget = deriv_a[:, 0], deriv_a[:, 1]
    vrx_direct = -mtr * ditx
    vrx_target = -mrt * ditarget
    vrx_total = vrx_direct + vrx_target
    stored = np.asarray([energy(s) for s in states_a])
    energy_delta = float(stored[-1] - stored[0])
    energy_residual = source_energy - tx_loss_energy - target_loss_energy - clamp_energy - energy_delta
    post = times_a >= width
    metrics = {
        "model": MODEL,
        "model_status": "reduced_order_single_target_loop_surrogate_not_3d_conductor_fem",
        "turnoff_clamp_mode": "one_way_current_clamp_then_open_circuit_at_zero" if clamp > 0 else "natural_RL_decay",
        "coupling_h": {
            "M_TX_target_signed": mtt,
            "M_TX_RX_signed": mtr,
            "M_RX_target_signed": mrt
        },
        "inductance_matrix_eigenvalues_h": eigenvalues.tolist(),
        "peak_abs_tx_current_a": float(np.max(np.abs(itx))),
        "tx_current_at_turnoff_a": float(np.interp(width, times_a, itx)),
        "peak_abs_target_loop_current_a": float(np.max(np.abs(itarget))),
        "peak_abs_rx_voltage_v": float(np.max(np.abs(vrx_total))),
        "peak_abs_rx_voltage_after_turnoff_v": float(np.max(np.abs(vrx_total[post]))),
        "peak_abs_rx_direct_component_v": float(np.max(np.abs(vrx_direct))),
        "peak_abs_rx_target_component_v": float(np.max(np.abs(vrx_target))),
        "source_energy_j": source_energy,
        "tx_copper_loss_j": tx_loss_energy,
        "target_copper_loss_j": target_loss_energy,
        "clamp_absorbed_energy_j": clamp_energy,
        "stored_magnetic_energy_change_j": energy_delta,
        "energy_balance_residual_j": energy_residual,
        "energy_balance_relative_error": abs(energy_residual) / max(abs(source_energy), 1e-18),
        "sample_count": int(len(times_a)),
        "time_step_nominal_s": dt_nominal,
        "pulse_width_s": width,
        "stop_time_s": stop,
        "turns": {"TX": ntx, "RX": nrx, "target_loop": nt}
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
        "stored_magnetic_energy_j": stored
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
