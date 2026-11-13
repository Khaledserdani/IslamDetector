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
    raw_curve=afe.get("input_clamp_iv_curve_v_a")
    clamp_curve=None
    if raw_curve is not None:
        clamp_curve=np.asarray(raw_curve,dtype=float)
        if clamp_curve.ndim!=2 or clamp_curve.shape[1]!=2 or len(clamp_curve)<2 or not np.isfinite(clamp_curve).all():
            raise ValueError("input_clamp_iv_curve_v_a must be a finite Nx2 voltage/current table")
        if np.any(clamp_curve[:,0]<0) or np.any(clamp_curve[:,1]<0) or np.any(np.diff(clamp_curve[:,0])<=0) or np.any(np.diff(clamp_curve[:,1])<=0):
            raise ValueError("input clamp I-V table must be strictly increasing and nonnegative")
    coil_vt=_nonnegative(afe.get("coil_tvs_threshold_v",0.0),"afe.coil_tvs_threshold_v")
    coil_rt=_positive(afe.get("coil_tvs_dynamic_resistance_ohm",1.0),"afe.coil_tvs_dynamic_resistance_ohm")
    op=config.get("opamp",{})
    gain=_positive(op.get("closed_loop_gain",2.0),"opamp.closed_loop_gain")
    vlow=float(op.get("supply_low_v",0.0)); vhigh=float(op.get("supply_high_v",3.3))
    vref=float(op.get("reference_v",0.5*(vlow+vhigh)))
    gbw=_positive(op.get("gain_bandwidth_hz",50e6),"opamp.gain_bandwidth_hz")
    slew=_positive(op.get("slew_rate_v_per_s",25e6),"opamp.slew_rate_v_per_s")
    headroom=_nonnegative(op.get("output_headroom_v",0.01),"opamp.output_headroom_v")
    if not all(math.isfinite(x) for x in (vlow,vhigh,vref)) or vhigh<=vlow or vref<vlow or vref>vhigh or vhigh-vlow<2.2 or vhigh-vlow>5.5 or 2*headroom>=vhigh-vlow:
        raise ValueError("invalid opamp rails, reference or output headroom")
    max_step=_positive(config.get("integration",{}).get("max_step_s",float(np.min(np.diff(t)))),"integration.max_step_s")
    if len(t)>200001: raise ValueError("input waveform exceeds 200,001 samples")
    def clamp_current(v,threshold,dynamic_r):
        if threshold<=0: return 0.0
        if v>threshold: return (v-threshold)/dynamic_r
        if v< -threshold: return (v+threshold)/dynamic_r
        return 0.0
    def input_clamp_current(v):
        if clamp_curve is None:return clamp_current(v,vclamp,rclamp)
        av=abs(v)
        if av<clamp_curve[0,0]:return 0.0
        current=float(np.interp(av,clamp_curve[:,0],clamp_curve[:,1]))
        if av>clamp_curve[-1,0]:
            dv=clamp_curve[-1,0]-clamp_curve[-2,0]
            di=clamp_curve[-1,1]-clamp_curve[-2,1]
            current+=((av-clamp_curve[-1,0])*di/dv)
        return math.copysign(current,v)
    def terminal_voltage(icoil,vnode):
        # Closed-form passive solution when the coil TVS is not conducting.
        linear=rdamp*(rseries*icoil+vnode)/(rdamp+rseries)
        if coil_vt<=0 or abs(linear)<=coil_vt: return linear
        # Piecewise-linear TVS branch has a closed-form KCL solution.
        sign=1.0 if linear>0 else -1.0
        conductance=1.0/rdamp+1.0/rseries+1.0/coil_rt
        return (icoil+vnode/rseries+sign*coil_vt/coil_rt)/conductance
    def deriv(state, source):
        icoil,vnode=state
        va=terminal_voltage(icoil,vnode)
        iseries=(va-vnode)/rseries
        itvs=clamp_current(va,coil_vt,coil_rt) if coil_vt>0 else 0.0
        iclamp=input_clamp_current(vnode)
        di=(source-rcoil*icoil-va)/lcoil
        dv=(iseries-vnode/rbias-iclamp)/cin
        return np.array([di,dv]),(va,iseries,itvs,iclamp)
    def source_at(x):
        return float(np.interp(x,t,emf))
    def powers(state, source):
        icoil,vnode=state
        _,(va,iseries,itvs,iclamp)=deriv(state,source)
        return np.array([
            source*icoil,
            rcoil*icoil*icoil,
            va*va/rdamp,
            va*itvs,
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
    out_t=[float(t[0])]; out_i=[0.0]; out_v=[0.0]; out_va=[0.0]; out_is=[0.0]; out_itvs=[0.0]; out_ic=[0.0]
    state=np.array([0.0,0.0]); totals=np.zeros(7)
    generated_steps=0
    for idx in range(len(t)-1):
        left=float(t[idx]); right=float(t[idx+1]); span=right-left
        count=max(1,int(math.ceil(span/max_step)))
        generated_steps+=count
        if generated_steps>500000: raise ValueError("AFE integration exceeds 500,000 steps")
        h=span/count
        for k in range(count):
            now=left+k*h
            state,energy=step(state,now,h)
            totals+=energy
            va,iseries,itvs,iclamp=deriv(state,source_at(now+h))[1]
            out_t.append(now+h);out_i.append(state[0]);out_v.append(state[1])
            out_va.append(va);out_is.append(iseries);out_itvs.append(itvs);out_ic.append(iclamp)
    ta=np.asarray(out_t); ia=np.asarray(out_i); vb=np.asarray(out_v)
    vaa=np.asarray(out_va); isa=np.asarray(out_is); itvsa=np.asarray(out_itvs); ica=np.asarray(out_ic)
    stored=0.5*lcoil*ia**2+0.5*cin*vb**2
    # First-order closed-loop OPA365 behavioral stage with finite GBW, slew and rail limits.
    # This is not a transistor-level vendor macromodel.
    opout=np.empty_like(vb);opout[0]=min(max(vref,vlow+headroom),vhigh-headroom)
    slew_limited=0;saturated=0
    bw=gbw/gain
    for k in range(1,len(ta)):
        h=ta[k]-ta[k-1]
        requested=vref+gain*vb[k]
        target=min(max(requested,vlow+headroom),vhigh-headroom)
        if requested< vlow+headroom or requested>vhigh-headroom:saturated+=1
        ideal=(target-opout[k-1])*(-math.expm1(-2.0*math.pi*bw*h))
        limit=slew*h
        delta_out=max(-limit,min(limit,ideal))
        if abs(ideal)>limit:slew_limited+=1
        raw=opout[k-1]+delta_out
        clipped=min(max(raw,vlow+headroom),vhigh-headroom)
        if clipped!=raw:saturated+=1
        opout[k]=clipped
    delta=float(stored[-1]-stored[0])
    residual=float(totals[0]-sum(totals[1:])-delta)
    metrics={
        "model":"rx_thevenin_rl_damping_series_protection_input_capacitance_bias_and_bidirectional_clamp",
        "model_status":"reduced_order_lumped_rx_protection_plus_first_order_opa365_behavioral_model_not_transistor_level",
        "sample_count":int(len(ta)),
        "peak_abs_induced_emf_v":float(np.max(np.abs(emf))),
        "peak_abs_rx_coil_current_a":float(np.max(np.abs(ia))),
        "peak_abs_rx_terminal_voltage_v":float(np.max(np.abs(vaa))),
        "peak_abs_afe_input_voltage_v":float(np.max(np.abs(vb))),
        "opamp_model":"OPA365_first_order_closed_loop_GBW_slew_and_rail_limited_behavioral_model",
        "opamp_peak_output_v":float(np.max(opout)),
        "opamp_min_output_v":float(np.min(opout)),
        "opamp_slew_limited_sample_count":int(slew_limited),
        "opamp_output_saturation_sample_count":int(saturated),
        "opamp_closed_loop_gain":gain,
        "opamp_gain_bandwidth_hz":gbw,
        "opamp_slew_rate_v_per_s":slew,
        "afe_input_voltage_at_end_v":float(vb[-1]),
        "peak_abs_protection_series_current_a":float(np.max(np.abs(isa))),
        "peak_abs_clamp_current_a":float(np.max(np.abs(ica))),
        "clamp_conduction_sample_count":int(np.count_nonzero(ica)),
        "source_energy_j":float(totals[0]),
        "rx_copper_loss_j":float(totals[1]),
        "damping_loss_j":float(totals[2]),
        "series_resistor_loss_j":float(totals[4]),
        "bias_resistor_loss_j":float(totals[5]),
        "coil_tvs_absorbed_energy_j":float(totals[3]),
        "input_clamp_absorbed_energy_j":float(totals[6]),
        "stored_energy_change_j":delta,
        "energy_balance_residual_j":residual,
        "energy_balance_relative_error":abs(residual)/max(abs(totals[0]),1e-18),
        "rx_coil_resistance_ohm":rcoil,
        "rx_coil_inductance_h":lcoil,
        "parallel_damping_ohm":rdamp,
        "series_protection_ohm":rseries,
        "input_capacitance_f":cin,
        "input_bias_ohm":rbias,
        "coil_tvs_threshold_v":coil_vt,
        "coil_tvs_dynamic_resistance_ohm":coil_rt,
        "input_clamp_threshold_v":vclamp,
        "input_clamp_dynamic_resistance_ohm":rclamp,\n        "input_clamp_iv_curve_v_a":clamp_curve.tolist() if clamp_curve is not None else None
    }
    arrays={"time_s":ta,"induced_emf_v":np.interp(ta,t,emf),"rx_coil_current_a":ia,
            "rx_terminal_voltage_v":vaa,"afe_input_voltage_v":vb,
            "protection_series_current_a":isa,"coil_tvs_current_a":itvsa,
            "input_clamp_current_a":ica,"opamp_output_v":opout,"stored_energy_j":stored}
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
