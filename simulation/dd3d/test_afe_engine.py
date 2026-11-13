#!/usr/bin/env python3
"""Unit and convergence tests for the lumped RX/AFE front-end."""
import unittest
import numpy as np
from afe_engine import simulate_afe

def cfg():
    return {
      "rx_coil":{"resistance_ohm":4.8,"inductance_h":750e-6},
      "afe":{"parallel_damping_ohm":390.0,"series_protection_ohm":1000.0,
             "input_capacitance_f":2e-9,"input_bias_ohm":1e6,
             "clamp_threshold_v":0.35,"clamp_dynamic_resistance_ohm":5.0},
      "integration":{"max_step_s":0.1e-6}
    }
def wave(amplitude=1.0):
    t=np.linspace(0,100e-6,1001)
    # finite, smooth induced pulse to exercise input loading and clamp
    v=amplitude*np.exp(-((t-20e-6)/(3e-6))**2)-0.4*amplitude*np.exp(-((t-35e-6)/(5e-6))**2)
    return {"time_s":t,"v_rx_total_v":v}

class AfeEngineTests(unittest.TestCase):
    def test_zero_source_remains_at_zero_and_energy_balances(self):
        w=wave(0.0)
        m,d=simulate_afe(w,cfg())
        self.assertAlmostEqual(m["peak_abs_afe_input_voltage_v"],0.0,delta=1e-15)
        self.assertLess(m["energy_balance_relative_error"],1e-8)

    def test_bidirectional_clamp_limits_input_node_and_absorbs_energy(self):
        m,d=simulate_afe(wave(30.0),cfg())
        self.assertGreater(m["clamp_absorbed_energy_j"],0.0)
        self.assertLess(m["peak_abs_afe_input_voltage_v"],2.0)
        self.assertLess(m["energy_balance_relative_error"],2e-4)

    def test_more_damping_reduces_rx_terminal_voltage(self):
        c1=cfg();c2=cfg()
        c1["afe"]["parallel_damping_ohm"]=390.0
        c2["afe"]["parallel_damping_ohm"]=100.0
        m1,_=simulate_afe(wave(0.1),c1)
        m2,_=simulate_afe(wave(0.1),c2)
        self.assertLess(m2["peak_abs_rx_terminal_voltage_v"],m1["peak_abs_rx_terminal_voltage_v"])

    def test_smaller_integration_step_converges(self):
        c1=cfg();c2=cfg()
        c1["integration"]["max_step_s"]=0.2e-6
        c2["integration"]["max_step_s"]=0.1e-6
        m1,_=simulate_afe(wave(0.5),c1)
        m2,_=simulate_afe(wave(0.5),c2)
        self.assertAlmostEqual(m1["peak_abs_afe_input_voltage_v"],m2["peak_abs_afe_input_voltage_v"],
                               delta=max(1e-5,m2["peak_abs_afe_input_voltage_v"]*0.01))

    def test_rejects_non_monotonic_waveform_time(self):
        w=wave()
        w["time_s"][20]=w["time_s"][19]
        with self.assertRaises(ValueError): simulate_afe(w,cfg())

if __name__=="__main__": unittest.main(verbosity=2)
