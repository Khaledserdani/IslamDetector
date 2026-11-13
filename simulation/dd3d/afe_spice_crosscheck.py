#!/usr/bin/env python3
"""Cross-check the linear RX/AFE RLC network against ngspice transient analysis."""
import argparse
import copy
import json
import shutil
import subprocess
from pathlib import Path
import numpy as np
from afe_engine import read_waveform, simulate_afe

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("waveform",type=Path)
    ap.add_argument("config",type=Path)
    ap.add_argument("--output-dir",type=Path,default=Path("spice-crosscheck"))
    ap.add_argument("--ngspice",default="ngspice")
    args=ap.parse_args()
    executable=shutil.which(args.ngspice)
    if not executable: raise SystemExit("ngspice executable not found")
    wave=read_waveform(args.waveform)
    cfg=json.loads(args.config.read_text(encoding="utf-8"))
    # Disable nonlinear protection and OPA stages: this comparison isolates the passive linear R/L/R/C network.
    pycfg=copy.deepcopy(cfg)
    pycfg["afe"]["coil_tvs_threshold_v"]=0.0
    pycfg["afe"]["clamp_threshold_v"]=0.0
    pycfg.setdefault("integration",{})["max_step_s"]=2.5e-9
    metrics,py=simulate_afe(wave,pycfg)
    out=args.output_dir
    out.mkdir(parents=True,exist_ok=True)
    netlist=out/"afe_linear_crosscheck.cir"
    data=out/"ngspice_waveform.dat"
    times=wave["time_s"]; volts=wave["v_rx_total_v"]
    pwl=[]
    for k,(t,v) in enumerate(zip(times,volts)):
        pwl.append(f"+ {t:.12e} {v:.12e}")
    cfgafe=cfg["afe"]; rx=cfg["rx_coil"]
    lines=[
      "* ISLAM LAB linear RX/AFE cross-check; nonlinear clamps intentionally disabled",
      f"VEMF src 0 PWL(\n"+"\n".join(pwl)+"\n)",
      f"RCOIL src ncoil {float(rx['resistance_ohm']):.12g}",
      f"LCOIL ncoil rx {float(rx['inductance_h']):.12g} IC=0",
      f"RDAMP rx 0 {float(cfgafe['parallel_damping_ohm']):.12g}",
      f"RPROTECT rx afe {float(cfgafe['series_protection_ohm']):.12g}",
      f"CIN afe 0 {float(cfgafe['input_capacitance_f']):.12g} IC=0",
      f"RBIAS afe 0 {float(cfgafe['input_bias_ohm']):.12g}",
      ".control","set noaskquit","set wr_singlescale",
      "tran 2.5n 6e-4 0 2.5n uic",
      f"wrdata {data.name} v(rx) v(afe) i(LCOIL)",
      "quit",".endc",".end"
    ]
    netlist.write_text("\n".join(lines)+"\n",encoding="utf-8")
    run=subprocess.run([executable,"-b",netlist.name],cwd=out,capture_output=True,text=True,timeout=240)
    (out/"ngspice.log").write_text(run.stdout+"\n"+run.stderr,encoding="utf-8")
    if run.returncode!=0 or not data.is_file():
        raise SystemExit("ngspice failed; inspect ngspice.log")
    raw=np.loadtxt(data)
    if raw.ndim!=2 or raw.shape[1]<4 or raw.shape[0]<100:
        raise SystemExit(f"unexpected ngspice wrdata shape: {raw.shape}")
    st=raw[:,0]; sv_rx=raw[:,1]; sv_afe=raw[:,2]; si=raw[:,3]
    if np.any(np.diff(st)<=0): raise SystemExit("ngspice time vector is not strictly increasing")
    # Compare on the Python engine's fixed output grid.
    rx_sp=np.interp(py["time_s"],st,sv_rx)
    afe_sp=np.interp(py["time_s"],st,sv_afe)
    i_sp=np.interp(py["time_s"],st,si)
    def error(a,b):
        scale=max(float(np.max(np.abs(b))),1e-12)
        return float(np.max(np.abs(a-b))/scale)
    results={
      "ngspice_version":subprocess.run([executable,"--version"],capture_output=True,text=True,timeout=20).stdout.splitlines()[:2],
      "python_samples":int(len(py["time_s"])),"ngspice_samples":int(len(st)),
      "relative_max_error_rx_terminal_voltage":error(py["rx_terminal_voltage_v"],rx_sp),
      "relative_max_error_afe_input_voltage":error(py["afe_input_voltage_v"],afe_sp),
      "relative_max_error_rx_coil_current":error(py["rx_coil_current_a"],i_sp),
      "passive_energy_balance_relative_error_python":metrics["energy_balance_relative_error"],
      "protection_state":"coil TVS and input clamp disabled for linear comparison",
      "scope":"independent linear RLC solver cross-check; not nonlinear TVS or OPA365 validation"
    }
    (out/"spice_crosscheck.json").write_text(json.dumps(results,indent=2)+"\n",encoding="utf-8")
    with (out/"spice_comparison.csv").open("w",encoding="utf-8") as f:
        f.write("time_s,python_rx_terminal_v,ngspice_rx_terminal_v,python_afe_input_v,ngspice_afe_input_v,python_rx_current_a,ngspice_rx_current_a\n")
        for row in zip(py["time_s"],py["rx_terminal_voltage_v"],rx_sp,py["afe_input_voltage_v"],afe_sp,py["rx_coil_current_a"],i_sp):
            f.write(",".join(f"{float(x):.12e}" for x in row)+"\n")
    limits=(0.015,0.015,0.015)
    errors=(results["relative_max_error_rx_terminal_voltage"],results["relative_max_error_afe_input_voltage"],results["relative_max_error_rx_coil_current"])
    print(json.dumps(results,indent=2))
    if any(e>limit for e,limit in zip(errors,limits)):
        raise SystemExit("FAIL: Python/ ngspice maximum relative error exceeded 1.5%")
    print("PASS: Python and ngspice agree within 1.5% for all passive RX/AFE waveforms")

if __name__=="__main__": main()
