#!/usr/bin/env python3
"""Verification tests for the coupled PI pulse engine."""
import math
import unittest
import numpy as np
from filament_model import circular_loop
from pulse_engine import simulate_pulse, validate_inductance_matrix

def config():
    tx = circular_loop(0.12, 128, 0.0).tolist()
    rx = circular_loop(0.10, 128, 0.015).tolist()
    target = circular_loop(0.04, 128, -0.06).tolist()
    return {
        "paths_m": {"TX": tx, "RX": rx, "target_loop": target},
        "turns": {"TX": 20, "RX": 30, "target_loop": 1},
        "electrical": {
            "tx_resistance_ohm": 1.52,
            "tx_inductance_h": 350e-6,
            "rx_inductance_h": 750e-6
        },
        "target": {"resistance_ohm": 0.08, "inductance_h": 20e-6},
        "pulse": {
            "bus_voltage_v": 5.0,
            "pulse_width_s": 100e-6,
            "clamp_voltage_v": 0.0,
            "time_step_s": 0.25e-6,
            "stop_time_s": 600e-6
        }
    }

class PulseEngineTests(unittest.TestCase):
    def test_zero_coupling_matches_closed_form_rl_on_and_off(self):
        c = config()
        c["paths_m"]["target_loop"] = circular_loop(0.04, 128, 0.0).tolist()
        # Use an almost-zero target coupling by orienting the target normal perpendicular.
        c["paths_m"]["target_loop"] = [
            [0.04*math.cos(2*math.pi*i/128), 0.0, 0.04*math.sin(2*math.pi*i/128)]
            for i in range(129)
        ]
        c["electrical"]["tx_inductance_h"] = 350e-6
        c["pulse"]["clamp_voltage_v"] = 0.0
        metrics, data = simulate_pulse(c)
        r, l, v, width = 1.52, 350e-6, 5.0, 100e-6
        expected_on = v/r * (1-math.exp(-r*width/l))
        expected_off = expected_on * math.exp(-r*(600e-6-width)/l)
        self.assertAlmostEqual(metrics["tx_current_at_turnoff_a"], expected_on, delta=0.003)
        self.assertAlmostEqual(float(data["i_tx_a"][-1]), expected_off, delta=0.003)


    def test_rx_flux_linkage_derivative_matches_coupled_voltage(self):
        c = config()
        c["pulse"]["clamp_voltage_v"] = 0.0
        metrics, data = simulate_pulse(c)
        expected_linkage = (
            metrics["coupling_h"]["M_TX_RX_signed"] * data["i_tx_a"]
            + metrics["coupling_h"]["M_RX_target_signed"] * data["i_target_a"]
        )
        np.testing.assert_allclose(data["rx_flux_linkage_wb_turn"], expected_linkage,
                                   rtol=1e-12, atol=1e-18)
        mask = ((data["time_s"] > data["time_s"][0])
                & (data["time_s"] < data["time_s"][-1])
                & (np.abs(data["time_s"] - metrics["pulse_width_s"])
                   > 2.5 * metrics["time_step_nominal_s"]))
        self.assertLess(metrics["rx_flux_derivative_relative_rms_error_smooth"], 0.01)
        np.testing.assert_allclose(
            data["v_rx_total_v"][mask],
            -metrics["coupling_h"]["M_TX_RX_signed"] * data["di_tx_dt_a_per_s"][mask]
            -metrics["coupling_h"]["M_RX_target_signed"] * data["di_target_dt_a_per_s"][mask],
            rtol=1e-12, atol=1e-12
        )

    def test_flux_derivative_error_reduces_when_time_step_is_halved(self):
        c = config()
        c["pulse"]["clamp_voltage_v"] = 0.0
        m1, _ = simulate_pulse(c)
        c["pulse"]["time_step_s"] *= 0.5
        m2, _ = simulate_pulse(c)
        self.assertLess(
            m2["rx_flux_derivative_relative_rms_error_smooth"],
            m1["rx_flux_derivative_relative_rms_error_smooth"]
        )

    def test_clamped_flux_derivative_metric_excludes_current_zero_event(self):
        c = config()
        c["pulse"]["clamp_voltage_v"] = 20.0
        metrics, data = simulate_pulse(c)
        event_time = metrics["tx_clamp_zero_event_time_s"]
        self.assertIsNotNone(event_time)
        self.assertGreater(event_time, metrics["pulse_width_s"])
        self.assertLess(event_time, data["time_s"][-1])

        times = data["time_s"]
        dt = metrics["time_step_nominal_s"]
        mask = ((times > times[0]) & (times < times[-1])
                & (np.abs(times - metrics["pulse_width_s"]) > 2.5 * dt)
                & (np.abs(times - event_time) > 2.5 * dt))
        self.assertGreaterEqual(np.count_nonzero(mask), 3)
        expected = (
            np.sqrt(np.mean((data["v_rx_from_flux_derivative_v"][mask]
                             - data["v_rx_total_v"][mask]) ** 2))
            / max(np.sqrt(np.mean(data["v_rx_total_v"][mask] ** 2)), 1e-18)
        )
        self.assertAlmostEqual(
            metrics["rx_flux_derivative_relative_rms_error_smooth"], expected,
            delta=1e-12
        )

    def test_energy_balance_closes_for_unclamped_case(self):
        c=config()
        c["pulse"]["clamp_voltage_v"]=0.0
        metrics,_=simulate_pulse(c)
        self.assertLess(metrics["energy_balance_relative_error"], 2e-4)
        self.assertGreaterEqual(metrics["source_energy_j"], 0)
        self.assertGreaterEqual(metrics["tx_copper_loss_j"], 0)
        self.assertGreaterEqual(metrics["target_copper_loss_j"], 0)

    def test_target_coupling_creates_separate_rx_components(self):
        metrics,data=simulate_pulse(config())
        self.assertGreater(metrics["peak_abs_rx_direct_component_v"],0)
        self.assertGreater(metrics["peak_abs_rx_target_component_v"],0)
        np.testing.assert_allclose(
            data["v_rx_total_v"],
            data["v_rx_direct_v"]+data["v_rx_target_v"],
            rtol=1e-12,atol=1e-15
        )

    def test_inductance_matrix_must_be_positive_definite(self):
        with self.assertRaises(ValueError):
            validate_inductance_matrix(100e-6,20e-6,750e-6,2e-3,1e-6,1e-6)

    def test_clamped_turnoff_energy_balance(self):
        c = config()
        c["pulse"]["clamp_voltage_v"] = 20.0
        metrics, _ = simulate_pulse(c)
        self.assertGreater(metrics["clamp_absorbed_energy_j"], 0.0)
        self.assertLess(metrics["energy_balance_relative_error"], 3e-4)

    def test_pulse_current_increases_with_bus_voltage(self):
        c1 = config()
        c2 = config()
        c2["pulse"]["bus_voltage_v"] *= 2.0
        m1, _ = simulate_pulse(c1)
        m2, _ = simulate_pulse(c2)
        self.assertAlmostEqual(m2["peak_abs_tx_current_a"], 2*m1["peak_abs_tx_current_a"], delta=1e-6)

    def test_higher_clamp_reduces_direct_rx_after_ten_microseconds(self):
        values = []
        target_values = []
        for clamp in (0.0, 20.0, 40.0, 80.0):
            c = config()
            c["pulse"]["clamp_voltage_v"] = clamp
            metrics, _ = simulate_pulse(c)
            values.append(metrics["peak_abs_rx_direct_after_10us_v"])
            target_values.append(metrics["peak_abs_rx_target_after_10us_v"])
        self.assertLess(values[-1], values[0])
        self.assertGreater(target_values[-1], 0.0)

    def test_halving_time_step_converges_waveform(self):
        c=config()
        m1,d1=simulate_pulse(c)
        c["pulse"]["time_step_s"]*=0.5
        m2,d2=simulate_pulse(c)
        self.assertAlmostEqual(m1["peak_abs_rx_voltage_v"],m2["peak_abs_rx_voltage_v"],delta=max(m2["peak_abs_rx_voltage_v"]*0.01,1e-9))
        self.assertAlmostEqual(m1["tx_current_at_turnoff_a"],m2["tx_current_at_turnoff_a"],delta=1e-5)

if __name__ == "__main__":
    unittest.main(verbosity=2)
