#!/usr/bin/env bash
# Audit vendor files without committing or redistributing vendor model archives.
# BAT54S checks include a single-junction DC sweep and a dual-junction rail-clamp DC polarity sweep; no transient or thermal package validation is implied.
set -euo pipefail

ROOT="${RUNNER_TEMP:-/tmp}/islam-vendor-model-audit"
mkdir -p "$ROOT"
REPORT="$ROOT/vendor_model_audit.txt"
: > "$REPORT"

fetch_zip() {
  local name="$1" url="$2" dest="$ROOT/$1.zip"
  echo "FETCH $name $url" | tee -a "$REPORT"
  curl --http1.1 --connect-timeout 15 --max-time 90 --fail --location --retry 1 --retry-all-errors --retry-delay 2 --retry-connrefused --silent --show-error "$url" -o "$dest"
  unzip -q "$dest" -d "$ROOT/$name"
  echo "ARCHIVE_SHA256 $(sha256sum "$dest" | awk '{print $1}')" | tee -a "$REPORT"
}

fetch_zip "ti-opa365" "https://www.ti.com/lit/zip/SBOC133"
# ST lists the electro-thermal PSpice archive on its official product page,
# but the download is gated by myST email verification and NDA acceptance.
# Anonymous CI must not keep retrying an access-controlled resource.
echo "ST_SMAJ_VENDOR_DOWNLOAD UNAVAILABLE (official download requires myST email verification and NDA; anonymous CI has no authorized session)" | tee -a "$REPORT"
echo "ST_SMAJ_OFFICIAL_MODEL_URL https://www.st.com/resource/en/spice_model/smaj-series-thermal-pspice.zip" | tee -a "$REPORT"
curl --http1.1 --connect-timeout 15 --max-time 60 --fail --location --retry 3 --retry-all-errors --retry-delay 2 --retry-connrefused --silent --show-error \
  "https://www.diodes.com/spice/download/431/BAT54S.spice.txt" -o "$ROOT/BAT54S.spice.txt"

echo "BAT54S_SHA256 $(sha256sum "$ROOT/BAT54S.spice.txt" | awk '{print $1}')" | tee -a "$REPORT"

if ! grep -qiE '^[[:space:]]*\.model[[:space:]]+DI_BAT54S[[:space:]]+D' "$ROOT/BAT54S.spice.txt"; then
  echo "FAIL: expected single-junction DI_BAT54S diode model not found" | tee -a "$REPORT"
  exit 1
fi
cat > "$ROOT/bat54s_dc.cir" <<EOF
* One-junction DC sanity sweep using the official Diodes BAT54S model.
.include "$ROOT/BAT54S.spice.txt"
VSWEEP anode 0 0
D1 anode 0 DI_BAT54S
.control
set noaskquit
set wr_singlescale
dc VSWEEP 0 1.0 1m
wrdata $ROOT/BAT54S_dc_iv.dat v(anode) i(VSWEEP)
quit
.endc
.end
EOF
if ngspice -b -o "$ROOT/BAT54S_dc.log" "$ROOT/bat54s_dc.cir" >/dev/null 2>&1 && [[ -s "$ROOT/BAT54S_dc_iv.dat" ]]; then
  echo "BAT54S_OFFICIAL_MODEL_DC_SWEEP PASS (single junction only)" | tee -a "$REPORT"
  cat > "$ROOT/bat54s_dual_clamp.cir" <<EOF
* BAT54S package topology: pin 1 A1 -> pin 3 K1/A2; pin 3 -> pin 2 K2.
* Pin 3 is the protected signal; pin 1 is the low rail; pin 2 is the high rail.
.include "$ROOT/BAT54S.spice.txt"
VLOW low 0 0
VHIGH high 0 3.3
VSWEEP sig 0 0
DLOW low sig DI_BAT54S
DHIGH sig high DI_BAT54S
.control
set noaskquit
dc VSWEEP -0.5 3.8 1m
meas dc i_low FIND i(VSWEEP) AT=-0.5
meas dc i_high FIND i(VSWEEP) AT=3.8
wrdata $ROOT/BAT54S_dual_clamp_iv.dat v(sig) i(VSWEEP)
quit
.endc
.end
EOF
  if ngspice -b -o "$ROOT/BAT54S_dual_clamp.log" "$ROOT/bat54s_dual_clamp.cir" >/dev/null 2>&1 && [[ -s "$ROOT/BAT54S_dual_clamp_iv.dat" ]]; then
    python3 - "$ROOT/BAT54S_dual_clamp_iv.dat" <<'PY'
import sys
rows=[]
with open(sys.argv[1],encoding="utf-8") as f:
    for line in f:
        try:
            values=[float(x) for x in line.split()]
        except ValueError:
            continue
        # wrdata with wr_singlescale writes: sweep voltage, signal voltage, source current.
        if len(values) >= 3:
            rows.append(values)
if len(rows) < 2:
    raise SystemExit("dual-clamp sweep produced too few numeric rows")
lo=rows[0][-1]
hi=rows[-1][-1]
if abs(lo) < 1e-6 or abs(hi) < 1e-6 or lo*hi >= 0:
    raise SystemExit(f"dual clamp did not conduct with opposite polarities: low-end current={lo}, high-end current={hi}")
print(f"dual clamp polarity PASS: low-end source current={lo:.6g} A; high-end source current={hi:.6g} A")
PY
    echo "BAT54S_OFFICIAL_MODEL_DUAL_CLAMP_DC_SWEEP PASS" | tee -a "$REPORT"
  else
    echo "BAT54S_OFFICIAL_MODEL_DUAL_CLAMP_DC_SWEEP FAIL" | tee -a "$REPORT"
    tail -n 20 "$ROOT/BAT54S_dual_clamp.log" | sed 's/^/  /' | tee -a "$REPORT" || true
    exit 1
  fi
else
  echo "BAT54S_OFFICIAL_MODEL_DC_SWEEP FAIL" | tee -a "$REPORT"
  tail -n 20 "$ROOT/BAT54S_dc.log" | sed 's/^/  /' | tee -a "$REPORT" || true
  exit 1
fi

find "$ROOT" -type f \( -iname '*.lib' -o -iname '*.mod' -o -iname '*.spice.txt' \) \
  | sort > "$ROOT/model_files.txt"

while IFS= read -r model; do
  [[ -s "$model" ]] || continue
  rel="${model#"$ROOT/"}"
  echo "MODEL_FILE $rel" | tee -a "$REPORT"
  header="$(grep -im1 -E '^[[:space:]]*\.subckt[[:space:]]+' "$model" || true)"
  if [[ -n "$header" ]]; then
    echo "SUBCKT $header" | tee -a "$REPORT"
  else
    echo "NO_SUBCKT_HEADER" | tee -a "$REPORT"
  fi
  if grep -qiE '(^|[[:space:]])(TABLE|LIMIT|IF|THEN|ELSE|PARAMS:|FUNCTION)' "$model"; then
    echo "PSpice_or_vendor_extensions_present inspect_compatibility" | tee -a "$REPORT"
  fi
  deck="$ROOT/parse_test.cir"
  log="$ROOT/parse_test.log"
  {
    echo "* parser-only model inclusion test"
    echo ".include \"$model\""
    echo ".control"
    echo "quit"
    echo ".endc"
    echo ".end"
  } > "$deck"
  if ngspice -b -o "$log" "$deck" >/dev/null 2>&1; then
    echo "NGSPICE_INCLUDE_PARSE PASS $rel" | tee -a "$REPORT"
  else
    echo "NGSPICE_INCLUDE_PARSE FAIL $rel" | tee -a "$REPORT"
    grep -iE 'error|unknown|syntax|undefined|cannot' "$log" | head -n 12 | sed 's/^/  /' | tee -a "$REPORT" || true
  fi
done < "$ROOT/model_files.txt"

OPA_LIB="$(find "$ROOT/ti-opa365" -type f -iname 'OPA365.lib' -print -quit)"
if [[ -z "$OPA_LIB" ]] || ! grep -qiE '^[[:space:]]*\.subckt[[:space:]]+OPA365[[:space:]]+3[[:space:]]+4[[:space:]]+5[[:space:]]+2[[:space:]]+1' "$OPA_LIB"; then
  echo "OPA365_TRANSIENT_TEST FAIL: official subcircuit or expected pin order not found" | tee -a "$REPORT"
  exit 1
fi
cat > "$ROOT/opa365_closed_loop.cir" <<EOF
* OPA365 official TI macromodel; pins: +IN, -IN, V+, V-, OUT.
.include "$OPA_LIB"
VCC vcc 0 3.3
VEE vee 0 0
VREF ref 0 1.65
VIN in 0 PULSE(1.65 1.66 1u 20n 20n 2u 5u)
RG nminus ref 10k
RF out nminus 10k
XU1 in nminus vcc vee out OPA365
CLOAD out 0 10p
.control
set noaskquit
tran 5n 8u
meas tran vout_peak MAX v(out) FROM=1u TO=4u
meas tran vout_final FIND v(out) AT=7u
quit
.endc
.end
EOF
if ngspice -b -o "$ROOT/opa365_closed_loop.log" "$ROOT/opa365_closed_loop.cir" >/dev/null 2>&1; then
  python3 - "$ROOT/opa365_closed_loop.log" <<'PY'
import re,sys
s=open(sys.argv[1],encoding="utf-8",errors="replace").read()
def value(name):
    m=re.search(rf"\b{name}\s*=\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)",s,re.I)
    if not m: raise SystemExit(f"missing {name} in OPA365 transient log")
    return float(m.group(1))
peak=value("vout_peak"); final=value("vout_final")
# This is a non-inverting gain-of-two stage referenced to 1.65 V:
# Vout,ideal = 2*Vin - Vref = 2*1.66 - 1.65 = 1.67 V.
# The vendor macromodel may show transient overshoot; bound it separately
# from the settled closed-loop gain rather than expecting a unity-gain output.
expected_final = 2.0 * 1.66 - 1.65
if not 1.66 < final < 1.68:
    raise SystemExit(f"OPA365 closed-loop final value disagrees with gain-of-two expectation {expected_final:.6f} V: final={final}")
if not 1.65 < peak < 1.72 or peak < final:
    raise SystemExit(f"OPA365 transient peak outside broad sanity bounds: peak={peak}, final={final}")
print(f"OPA365 closed-loop transient PASS: peak={peak:.6f} V, final={final:.6f} V, expected_final={expected_final:.6f} V")
PY
  echo "OPA365_OFFICIAL_MODEL_CLOSED_LOOP_TRANSIENT PASS" | tee -a "$REPORT"
else
  echo "OPA365_OFFICIAL_MODEL_CLOSED_LOOP_TRANSIENT FAIL" | tee -a "$REPORT"
  tail -n 30 "$ROOT/opa365_closed_loop.log" | sed 's/^/  /' | tee -a "$REPORT" || true
  exit 1
fi

cat "$REPORT"
