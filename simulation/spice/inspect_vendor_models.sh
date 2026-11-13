#!/usr/bin/env bash
# Audit vendor files without committing or redistributing vendor model archives.
# BAT54S DC sweep is one junction only; package-level two-junction topology is a separate gate.
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
fetch_zip "st-smaj-series" "https://www.st.com/resource/en/spice_model/smaj-series-thermal-pspice.zip"
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
    python3 - "$ROOT/BAT54S_dual_clamp.log" <<'PY'
import re,sys
s=open(sys.argv[1],encoding="utf-8",errors="replace").read()
def value(name):
    m=re.search(rf"\\b{name}\\s*=\\s*([-+]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)(?:[eE][-+]?\\d+)?)",s,re.I)
    if not m: raise SystemExit(f"missing {name} in ngspice log")
    return float(m.group(1))
lo=value("i_low"); hi=value("i_high")
if not lo < 0 or not hi > 0:
    raise SystemExit(f"wrong clamp current directions: i_low={lo}, i_high={hi}")
print(f"dual clamp polarity PASS: low-rail current={lo:.6g} A; high-rail current={hi:.6g} A")
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

find "$ROOT" -type f \( -iname '*.lib' -o -iname '*.cir' -o -iname '*.mod' -o -iname '*.txt' \) \
  ! -name 'vendor_model_audit.txt' | sort > "$ROOT/model_files.txt"

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

cat "$REPORT"
