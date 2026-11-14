#!/usr/bin/env python3
"""Small-signal thermal and OPA input-noise budget for the lumped RX/AFE network.

The network is linearized with protection clamps OFF. Noise is referred to the
AFE input node; this is a reduced-order estimate, not a transistor-level model.
"""
from __future__ import annotations
import math
import numpy as np

K_B = 1.380649e-23

def _positive(value, name):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and > 0")
    return value

def _nonnegative(value, name):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and >= 0")
    return value

def estimate_input_noise(config):
    """Integrate independent Johnson + op-amp input noise through the RX/AFE network."""
    rx = config["rx_coil"]
    afe = config["afe"]
    op = config.get("opamp", {})
    noise = config["noise"]
    rcoil = _positive(rx["resistance_ohm"], "rx_coil.resistance_ohm")
    lcoil = _nonnegative(rx["inductance_h"], "rx_coil.inductance_h")
    rd = _positive(afe["parallel_damping_ohm"], "afe.parallel_damping_ohm")
    rs = _positive(afe["series_protection_ohm"], "afe.series_protection_ohm")
    cin = _positive(afe["input_capacitance_f"], "afe.input_capacitance_f")
    rb = _positive(afe["input_bias_ohm"], "afe.input_bias_ohm")
    temp = _positive(noise["temperature_k"], "noise.temperature_k")
    fmin = _positive(noise["frequency_min_hz"], "noise.frequency_min_hz")
    fmax = _positive(noise["frequency_max_hz"], "noise.frequency_max_hz")
    points = int(noise.get("frequency_points", 4001))
    if fmax <= fmin or points < 101 or points > 200001:
        raise ValueError("noise frequency range/point count is invalid")
    en = _nonnegative(op.get("input_voltage_noise_density_v_rt_hz", 0.0),
                      "opamp.input_voltage_noise_density_v_rt_hz")
    inn = _nonnegative(op.get("input_current_noise_density_a_rt_hz", 0.0),
                       "opamp.input_current_noise_density_a_rt_hz")

    freq = np.geomspace(fmin, fmax, points)
    w = 2.0 * np.pi * freq
    jw = 1j * w
    zb = 1.0 / (1.0 / rb + jw * cin)
    za = 1.0 / (1.0 / rd + 1.0 / (rs + zb))
    zcoil = rcoil + jw * lcoil
    zseen = 1.0 / (1.0 / zb + 1.0 / (rs + za))

    # Transfer functions from each independent noise source to the AFE input.
    h_coil = (za / (zcoil + za)) * (zb / (rs + zb))
    h_damping_current = za * zb / (rs + zb)
    h_series_voltage = zb / (za + rs + zb)
    h_bias_current = zseen

    psd = (
        4.0 * K_B * temp * rcoil * np.abs(h_coil) ** 2
        + (4.0 * K_B * temp / rd) * np.abs(h_damping_current) ** 2
        + 4.0 * K_B * temp * rs * np.abs(h_series_voltage) ** 2
        + (4.0 * K_B * temp / rb) * np.abs(h_bias_current) ** 2
        + en ** 2
        + inn ** 2 * np.abs(zseen) ** 2
    )
    total = float(np.trapezoid(psd, freq))
    components = {
        "rx_coil_johnson_noise_v2": float(np.trapezoid(
            4.0*K_B*temp*rcoil*np.abs(h_coil)**2, freq)),
        "damping_resistor_johnson_noise_v2": float(np.trapezoid(
            (4.0*K_B*temp/rd)*np.abs(h_damping_current)**2, freq)),
        "series_resistor_johnson_noise_v2": float(np.trapezoid(
            4.0*K_B*temp*rs*np.abs(h_series_voltage)**2, freq)),
        "bias_resistor_johnson_noise_v2": float(np.trapezoid(
            (4.0*K_B*temp/rb)*np.abs(h_bias_current)**2, freq)),
        "opamp_voltage_noise_v2": float(np.trapezoid(np.full_like(freq, en**2), freq)),
        "opamp_current_noise_v2": float(np.trapezoid(inn**2*np.abs(zseen)**2, freq)),
    }
    return {
        "model": "linear_small_signal_rx_afe_input_referred_noise",
        "model_status": "clamps_off_reduced_order_white_noise_budget_not_vendor_transistor_model",
        "temperature_k": temp,
        "frequency_min_hz": fmin,
        "frequency_max_hz": fmax,
        "frequency_points": points,
        "integrated_input_noise_rms_v": math.sqrt(max(total, 0.0)),
        "integrated_input_noise_variance_v2": total,
        "noise_components_variance_v2": components,
        "noise_components_rms_v": {k: math.sqrt(max(v, 0.0)) for k, v in components.items()},
        "assumptions": [
            "protection clamps and TVS are non-conducting in the small-signal noise model",
            "resistors and amplifier noise densities are white over the selected band",
            "noise sources are independent and uncorrelated",
            "OPA noise parameters must be supplied from a verified datasheet/model",
            "frequency integration is limited to the explicitly configured band"
        ]
    }

def compare_target_and_baseline(target_waveform, baseline_waveform, noise_config):
    """Compute target-induced differential RMS and SNR against an identical noise budget."""
    t = np.asarray(target_waveform["time_s"], dtype=float)
    vt = np.asarray(target_waveform["afe_input_voltage_v"], dtype=float)
    tb = np.asarray(baseline_waveform["time_s"], dtype=float)
    vb = np.asarray(baseline_waveform["afe_input_voltage_v"], dtype=float)
    if t.ndim != 1 or tb.ndim != 1 or vt.shape != t.shape or vb.shape != tb.shape:
        raise ValueError("target and baseline waveforms must have matching time/value arrays")
    if len(t) < 3 or len(tb) < 3 or not np.isfinite(t).all() or not np.isfinite(tb).all() or not np.isfinite(vt).all() or not np.isfinite(vb).all():
        raise ValueError("waveforms must contain at least three finite samples")
    if np.any(np.diff(t) <= 0) or np.any(np.diff(tb) <= 0):
        raise ValueError("waveform times must be strictly increasing")
    if t[0] > tb[0] or t[-1] < tb[-1]:
        # Use the common interval rather than extrapolating either waveform.
        lo, hi = max(t[0], tb[0]), min(t[-1], tb[-1])
    else:
        lo, hi = tb[0], tb[-1]
    if hi <= lo:
        raise ValueError("target and baseline waveforms have no common time interval")
    start = float(noise_config.get("signal_window_start_s", lo))
    end = float(noise_config.get("signal_window_end_s", hi))
    start, end = max(start, lo), min(end, hi)
    if end <= start:
        raise ValueError("signal analysis window does not overlap the waveforms")
    grid = np.unique(np.concatenate((t[(t >= start) & (t <= end)],
                                     tb[(tb >= start) & (tb <= end)],
                                     np.array([start, end]))))
    if len(grid) < 3:
        raise ValueError("signal window requires at least three distinct time samples")
    differential = np.interp(grid, t, vt) - np.interp(grid, tb, vb)
    # Remove DC offset over the analysis window before calculating target signal RMS.
    differential = differential - float(np.mean(differential))
    signal_rms = float(np.sqrt(np.trapezoid(differential**2, grid) / (grid[-1]-grid[0])))
    budget = estimate_input_noise(noise_config)
    noise_rms = budget["integrated_input_noise_rms_v"]
    ratio = signal_rms / noise_rms if noise_rms > 0 else (math.inf if signal_rms > 0 else 0.0)
    snr_db = 20.0 * math.log10(ratio) if ratio > 0 and math.isfinite(ratio) else (math.inf if math.isinf(ratio) else -math.inf)
    return {
        "model": "target_vs_baseline_differential_snr",
        "signal_window_start_s": start,
        "signal_window_end_s": end,
        "target_differential_input_rms_v": signal_rms,
        "integrated_input_noise_rms_v": noise_rms,
        "snr_linear": ratio,
        "snr_db": snr_db,
        "noise_budget": budget
    }
