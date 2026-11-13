#!/usr/bin/env bash
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
