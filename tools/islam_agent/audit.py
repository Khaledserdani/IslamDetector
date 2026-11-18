#!/usr/bin/env python3
"""Safe, deterministic audit runner for the ISLAM project.

This first version only verifies required source files and runs selected
unit tests. It never edits project source files and never merges changes.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPIRAL_DIR = ROOT / "simulation" / "spiral"
REQUIRED_FILES = (
    SPIRAL_DIR / "mono_spiral_geometry.py",
    SPIRAL_DIR / "mono_spiral_disk.py",
    SPIRAL_DIR / "run_disk_convergence.py",
    SPIRAL_DIR / "test_mono_spiral_geometry.py",
    SPIRAL_DIR / "test_mono_spiral_disk.py",
)
TEST_MODULES = ("test_mono_spiral_geometry", "test_mono_spiral_disk")


def run_tests() -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "unittest", "-v", *TEST_MODULES]
    return subprocess.run(
        command,
        cwd=SPIRAL_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        default="islam-agent-report.md",
        help="report output path (default: islam-agent-report.md)",
    )
    args = parser.parse_args()

    missing = [path.relative_to(ROOT).as_posix() for path in REQUIRED_FILES if not path.is_file()]
    test_result = None
    if not missing:
        test_result = run_tests()

    passed = not missing and test_result is not None and test_result.returncode == 0
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    commit = os.environ.get("GITHUB_SHA", "not-provided")
    ref = os.environ.get("GITHUB_REF", "not-provided")

    lines = [
        "# ISLAM Agent — تقرير التدقيق الآلي",
        "",
        f"- UTC: {timestamp}",
        f"- Commit: {commit}",
        f"- Ref: {ref}",
        "- Scope: required-file checks + selected unit tests only",
        "- Source modification: none",
        "- Physical measurements: none",
        "- Field-performance claims: none",
        "",
        "## فحص الملفات",
        "",
    ]
    if missing:
        lines.append("- FAIL — ملفات مطلوبة غير موجودة:")
        lines.extend(f"  - {path}" for path in missing)
    else:
        lines.append(f"- PASS — جميع الملفات المطلوبة موجودة ({len(REQUIRED_FILES)}).")

    lines.extend(["", "## اختبارات الوحدة", ""])
    if test_result is None:
        lines.append("- NOT RUN — لم تبدأ الاختبارات بسبب نقص الملفات.")
    else:
        state = "PASS" if test_result.returncode == 0 else "FAIL"
        lines.append(f"- {state} — exit code: {test_result.returncode}")
        lines.extend(["", "```text", test_result.stdout.rstrip(), "```"])

    lines.extend([
        "",
        "## حدود هذا التقرير",
        "",
        "هذا تدقيق برمجي محدود. نجاح الاختبارات لا يثبت صحة النموذج الفيزيائي، "
        "ولا يثبت محاثة الملف أو عمق الكشف أو الأداء الميداني. لم تُشغّل مسوحات "
        "التقارب أو الحساسية في هذا الإصدار.",
        "",
        f"## النتيجة النهائية: {'PASS' if passed else 'FAIL'}",
        "",
    ])

    report_path = Path(args.report)
    if not report_path.is_absolute():
        report_path = ROOT / report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written to: {report_path}")
    print(f"Audit result: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())