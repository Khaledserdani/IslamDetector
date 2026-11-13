#!/usr/bin/env python3
"""Transient RX-coil loading and protection-network model driven by PI induced EMF."""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path
import numpy as np

def _positive(x, name):
    x=float(x)
    if not math.isfinite(x) or x<=0: raise ValueError(f"{name} must be finite and > 0")
    return x

def _nonnegative(x, name):
    x=float(x)
    if not math.isfinite(x) or x<0: raise ValueError(f"{name} must be finite and >= 0")
    return x

def simulate_afe(waveform, config):
    """Model RX as induced Thevenin EMF + R/L; damped node, series R, C, bias and bidirectional clamp."""
    t=np.asarray(waveform["time_s"],dtype=float)
    emf=np.asarray(waveform["v_rx_total_v"],dtype=float)
    if t.ndim!=1 or len(t)<3 or emf.shape!=t.shape or not np.isfinite(t).all() or not np.isfinite(emf).all():
        raise ValueError("waveform requires at least 3 finite, equally sized time/voltage samples")
    if np.any(np.diff(t)<=0): raise ValueError("waveform time must be strictly increasing")
    rx=config["rx_coil"]; afe=config["afe"]
    rcoil=_positive(rx["resistance_ohm"],"rx_coil.resistance_ohm")
    lcoil=_positive(rx["inductance_h"],"rx_coil.inductance_h")
    rdamp=_positive(afe["parallel_damping_ohm"],"afe.parallel_damping_ohm")
    rseries=_positive(afe["series_protection_ohm"],"afe.series_protection_ohm")
    cin=_positive(afe["input_capacitance_f"],"afe.input_capacitance_f")
    rbias=_positive(afe["input_bias_ohm"],"afe.input_bias_ohm")
    vclamp=_nonnegative(afe["clamp_threshold_v"],"afe.clamp_threshold_v")
    rclamp=_positive(afe["clamp_dynamic_resistance_ohm"],"afe.clamp_dynamic_resistance_ohm")
    max_step=_positive(config.get("integration",{}).get("max_step_s",float(np.min(np.diff(t)))),"integration.max_step_s")
    if len(t)>200001: raise ValueError("input waveform exceeds 200,001 samples")
    def clamp_current(v):
        if v>vclamp: return (v-vclamp)/rclamp
        if v< -vclamp: return (v+vclamp)/rclamp
        return 0.0
    def deriv(state, source):
        icoil,vnode=state
        # KCL at RX terminal: coil current splits into damping and protected input.
        # vA = Rdamp*(icoil-is), is=(vA-vnode)/Rseries.
        va=(rdamp*(rseries*icoil+vnode))/(rdamp+rseries)
        iseries=(va-vnode)/rseries
        iclamp=clamp_current(vnode)
        di=(source-rcoil*icoil-va)/lcoil
        dv=(iseries-vnode/rbias-iclamp)/cin
        return np.array([di,dv]),(va,iseries,iclamp)
    def source_at(x):
        return float(np.interp(x,t,emf))
    def powers(state, source):
        icoil,vnode=state
        _,(va,iseries,iclamp)=deriv(state,source)
        return np.array([
            source*icoil,
            rcoil*icoil*icoil,
            va*va/rdamp,
            rseries*iseries*iseries,
            vnode*vnode/rbias,
            vnode*iclamp
        ])
    def step(state,ta,h):
        s1=source_at(ta); s2=source_at(ta+h/2); s4=source_at(ta+h)
        k1,_=deriv(state,s1)
        k2,_=deriv(state+0.5*h*k1,s2)
        k3,_=deriv(state+0.5*h*k2,s2)
        k4,_=deriv(state+h*k3,s4)
        stages=(state,state+0.5*h*k1,state+0.5*h*k2,state+h*k3)
        srcs=(s1,s2,s2,s4)
        p=[powers(s,src) for s,src in zip(stages,srcs)]
        integ=h*(p[0]+2*p[1]+2*p[2]+p[3])/6
        return state+h*(k1+2*k2+2*k3+k4)/6,integ
    out_t=[float(t[0])]; out_i=[0.0]; out_v=[0.0]; out_va=[0.0]; out_is=[0.0]; out_ic=[0.0]
    state=np.array([0.0,0.0]); totals=np.zeros(6)
    for idx in range(len(t)-1):
        left=float(t[idx]); right=float(t[idx+1]); span=right-left
        count=max(1,int(math.ceil(span/max_step)))
        h=span/count
        for k in range(count):
            now=left+k*h
            state,energy=step(state,now,h)
            totals+=energy
            va,iseries,iclamp=deriv(state,source_at(now+h))[1]
            out_t.append(now+h);out_i.append(state[0]);out_v.append(state[1])
            out_va.append(va);out_is.append(iseries);out_ic.append(iclamp)
    ta=np.asarray(out_t); ia=np.asarray(out_i); vb=np.asarray(out_v)
    vaa=np.asarray(out_va); isa=np.asarray(out_is); ica=np.asarray(out_ic)
    stored=0.5*lcoil*ia**2+0.5*cin*vb**2
    delta=float(stored[-1]-stored[0])
    residual=float(totals[0]-sum(totals[1:])-delta)
    metrics={
        "model":"rx_thevenin_rl_damping_series_protection_input_capacitance_bias_and_bidirectional_clamp",
        "model_status":"reduced_order_lumped_afe_front_end_not_opamp_or_pcb_parasitic_model",
        "sample_count":int(len(ta)),
        "peak_abs_induced_emf_v":float(np.max(np.abs(emf))),
        "peak_abs_rx_coil_current_a":float(np.max(np.abs(ia))),
        "peak_abs_rx_terminal_voltage_v":float(np.max(np.abs(vaa))),
        "peak_abs_afe_input_voltage_v":float(np.max(np.abs(vb))),
        "afe_input_voltage_at_end_v":float(vb[-1]),
        "peak_abs_protection_series_current_a":float(np.max(np.abs(isa))),
        "peak_abs_clamp_current_a":float(np.max(np.abs(ica))),
        "clamp_conduction_sample_count":int(np.count_nonzero(ica)),
        "source_energy_j":float(totals[0]),
        "rx_copper_loss_j":float(totals[1]),
        "damping_loss_j":float(totals[2]),
        "series_resistor_loss_j":float(totals[3]),
        "bias_resistor_loss_j":float(totals[4]),
        "clamp_absorbed_energy_j":float(totals[5]),
        "stored_energy_change_j":delta,
        "energy_balance_residual_j":residual,
        "energy_balance_relative_error":abs(residual)/max(abs(totals[0]),1e-18),
        "rx_coil_resistance_ohm":rcoil,
        "rx_coil_inductance_h":lcoil,
        "parallel_damping_ohm":rdamp,
        "series_protection_ohm":rseries,
        "input_capacitance_f":cin,
        "input_bias_ohm":rbias,
        "clamp_threshold_v":vclamp,
        "clamp_dynamic_resistance_ohm":rclamp
    }
    arrays={"time_s":ta,"induced_emf_v":np.interp(ta,t,emf),"rx_coil_current_a":ia,
            "rx_terminal_voltage_v":vaa,"afe_input_voltage_v":vb,
            "protection_series_current_a":isa,"clamp_current_a":ica,"stored_energy_j":stored}
    return metrics,arrays

def read_waveform(path):
    with Path(path).open(newline="",encoding="utf-8") as f:
        rows=list(csv.DictReader(f))
    return {k:np.asarray([float(r[k]) for r in rows]) for k in ("time_s","v_rx_total_v")}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("waveform",type=Path)
    ap.add_argument("config",type=Path)
    ap.add_argument("--output-dir",type=Path,default=Path("afe-output"))
    a=ap.parse_args()
    metrics,arrays=simulate_afe(read_waveform(a.waveform),json.loads(a.config.read_text(encoding="utf-8")))
    a.output_dir.mkdir(parents=True,exist_ok=True)
    with (a.output_dir/"afe_waveform.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f);w.writerow(arrays.keys());w.writerows(zip(*arrays.values()))
    (a.output_dir/"afe_metrics.json").write_text(json.dumps(metrics,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(metrics,indent=2))
if __name__=="__main__": main()
