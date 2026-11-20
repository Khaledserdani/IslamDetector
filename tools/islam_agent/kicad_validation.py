"""Fixed, bounded KiCad CLI validation for generated circuit schematics."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from circuit_components import validate_circuit_v2
from kicad_export import compile_kicad_schematic


MAX_SCHEMATIC_BYTES = 2_000_000
MAX_REPORT_CHARS = 20_000
CLI_TIMEOUT_SECONDS = 120


class KiCadValidationError(RuntimeError):
    """Raised when the fixed KiCad validation pipeline fails."""


class KiCadCliUnavailable(KiCadValidationError):
    """Raised when KiCad CLI is not installed on the local worker."""


def _run(command, cwd):
    try:
        result = subprocess.run(
            command, cwd=cwd, shell=False, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=CLI_TIMEOUT_SECONDS, check=False,
        )
    except subprocess.TimeoutExpired:
        raise KiCadValidationError("KiCad CLI validation timed out") from None
    except OSError:
        raise KiCadValidationError("KiCad CLI could not be started") from None
    if result.returncode != 0:
        detail = (result.stdout or "")[-4000:]
        raise KiCadValidationError(f"KiCad CLI command failed: {detail}")
    return result.stdout or ""


def validate_kicad_design(spec, project_name="ISLAM"):
    """Compile, parse, netlist-export, SVG-render, and ERC-report one design.

    ERC is reported for engineering review; a generated report is not treated
    as a zero-violation pass and never upgrades the design to Build-Ready.
    """
    design = validate_circuit_v2(spec)
    compiled = compile_kicad_schematic(design, project_name=project_name)
    source_text = compiled["kicad_sch"]
    if len(source_text.encode("utf-8")) > MAX_SCHEMATIC_BYTES:
        raise KiCadValidationError("generated schematic exceeds the 2 MB limit")
    executable = shutil.which("kicad-cli")
    if not executable:
        raise KiCadCliUnavailable("kicad-cli is not installed; install KiCad to run native validation")

    with tempfile.TemporaryDirectory(prefix="islam-kicad-") as temp:
        root = Path(temp)
        source = root / compiled["filename"]
        netlist = root / "design.net"
        erc_report = root / "erc.rpt"
        svg_dir = root / "svg"
        svg_dir.mkdir()
        source.write_text(source_text, encoding="utf-8")
        version_output = _run([executable, "version"], root).strip()
        _run([executable, "sch", "export", "netlist", "--output", str(netlist), str(source)], root)
        _run([executable, "sch", "export", "svg", "--output", str(svg_dir), str(source)], root)
        erc_output = _run([executable, "sch", "erc", "--output", str(erc_report), str(source)], root)
        if not netlist.is_file() or not erc_report.is_file():
            raise KiCadValidationError("KiCad CLI completed without producing all expected reports")
        svg_files = sorted(svg_dir.glob("*.svg"))
        if not svg_files:
            raise KiCadValidationError("KiCad CLI did not render an SVG page")
        netlist_text = netlist.read_text(encoding="utf-8", errors="replace")
        erc_text = erc_report.read_text(encoding="utf-8", errors="replace")
        return {
            "status": "native_validation_completed",
            "kicad_cli_version": version_output[:120],
            "schematic_parsed": True,
            "netlist_exported": True,
            "svg_rendered": True,
            "svg_page_count": len(svg_files),
            "erc_report_generated": True,
            "erc_status": "review_required",
            "erc_report": erc_text[-MAX_REPORT_CHARS:],
            "erc_console_output": erc_output[-4000:],
            "netlist": netlist_text[-MAX_REPORT_CHARS:],
            "component_count": compiled["component_count"],
            "pin_count": compiled["pin_count"],
            "electrical_warnings": design["electrical_warnings"],
            "missing_bom_identity": design["missing_bom_identity"],
            "build_ready": False,
        }
