#!/usr/bin/env python3
"""Compare BAT54S vendor SPICE diode model with published maximum VF points."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path
import numpy as np

MODEL = ".model DI_BAT54S D (IS=34.9u RS=0.210 BV=30 IBV=2.00u CJO=13.3p M=0.333 N=2.28 TT=7.20n)"
# Parameters copied from the Diodes Inc. BAT54S.spice.txt vendor model.
# https://www.diodes.com/spice/download/431/BAT54S.spice.txt
DATASHEET_MAX = [(0.1e-3,0.24),(1e-3,0.32),(10e-3,0.40),(30e-3,0.50),(100e-3,0.80)]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output-dir",type=Path,default=Path("bat54s-spice"))
    ap.add_argument("--ngspice",default="ngspice")
    args=ap.parse_args()
    exe=shutil.which(args.ngspice)
    if not exe:raise SystemExit("ngspice executable not found")
    out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    net=out/"bat54s_dc_sweep.cir";data=out/"bat54s_dc_iv.dat"
    lines=[
      "* Diodes Inc. BAT54S vendor model; one junction DC forward sweep",
      MODEL,
      "VSWEEP anode 0 0",
      "D1 anode 0 DI_BAT54S",
      ".control","set noaskquit","set wr_singlescale",
      "dc VSWEEP 0 1.0 1m",
      f"wrdata {data.name} i(VSWEEP)",
      "quit",".endc",".end"
    ]
    net.write_text("\n".join(lines)+"\n",encoding="utf-8")
    run=subprocess.run([exe,"-b",net.name],cwd=out,capture_output=True,text=True,timeout=90)
    (out/"ngspice.log").write_text(run.stdout+"\n"+run.stderr,encoding="utf-8")
    if run.returncode!=0 or not data.is_file():raise SystemExit("ngspice BAT54S DC sweep failed")
    raw=np.loadtxt(data)
    if raw.ndim!=2 or raw.shape[1]<2 or len(raw)<100:raise SystemExit(f"unexpected DC sweep output {raw.shape}")
    voltage=raw[:,0];current=np.abs(raw[:,1])
    order=np.argsort(current);current=current[order];voltage=voltage[order]
    if np.any(np.diff(current)<0) or current[-1]<0.099:raise SystemExit("BAT54S model sweep is not monotonic or does not reach 100mA")
    rows=[]
    for target,vmax in DATASHEET_MAX:
        vf=float(np.interp(target,current,voltage))
        rows.append({"current_a":target,"vendor_model_vf_v":vf,"datasheet_max_vf_v":vmax,
                     "margin_to_datasheet_max_v":vmax-vf})
    result={
      "vendor_model":"Diodes Inc DI_BAT54S",
      "model_parameters":{"IS_A":34.9e-6,"RS_OHM":0.210,"BV_V":30.0,"IBV_A":2e-6,"CJO_F":13.3e-12,"M":0.333,"N":2.28,"TT_S":7.2e-9},
      "sweep_points":int(len(raw)),
      "datasheet_max_forward_voltage_comparison":rows,
      "scope":"DC single-junction I-V comparison only; the two-diode BAT54S rail-steering topology is handled in the system model"
    }
    (out/"bat54s_iv_comparison.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))
    if any(row["margin_to_datasheet_max_v"] < -0.02 for row in rows):
        raise SystemExit("Vendor model exceeds a datasheet maximum VF point by more than 20mV")
    print("PASS: vendor BAT54S model remains below published maximum VF points")

if __name__=="__main__":main()
