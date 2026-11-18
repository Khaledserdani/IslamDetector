#!/usr/bin/env python3
"""Safe, deterministic audit runner for the ISLAM project.

It validates the versioned project memory and runs selected unit tests.
It never edits project source files and never merges changes.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPIRAL_DIR = ROOT / "simulation" / "spiral"
MEMORY_FILE = ROOT / "docs" / "agent" / "agent_memory.json"
REQUIRED_FILES = (
    SPIRAL_DIR / "mono_spiral_geometry.py",
    SPIRAL_DIR / "mono_spiral_disk.py",
    SPIRAL_DIR / "run_disk_convergence.py",
    SPIRAL_DIR / "test_mono_spiral_geometry.py",
    SPIRAL_DIR / "test_mono_spiral_disk.py",
    MEMORY_FILE,
)
TEST_MODULES = ("test_mono_spiral_geometry", "test_mono_spiral_disk")


def load_memory() -> tuple[dict | None, str | None]:
    try:
        memory = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"Cannot read valid JSON: {exc}"
    if not isinstance(memory, dict):
        return None, "Memory root must be a JSON object."
    if memory.get("schema_version") != 1:
        return None, "Unsupported or missing schema_version (expected 1)."
    for key in ("project", "updated_at", "known_constraints", "next_tasks"):
        if key not in memory:
            return None, f"Missing required memory key: {key}"
    if not isinstance(memory["known_constraints"], list) or not isinstance(memory["next_tasks"], list):
        return None, "known_constraints and next_tasks must be lists."
    for index, task in enumerate(memory["next_tasks"]):
        if not isinstance(task, dict) or not all(k in task for k in ("id", "title", "status", "acceptance")):
            return None, f"Invalid task entry at index {index}."
    return memory, None


def run_tests() -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "unittest", "-v", *TEST_MODULES]
    return subprocess.run(command, cwd=SPIRAL_DIR, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default="islam-agent-report.md")
    args = parser.parse_args()
    missing = [path.relative_to(ROOT).as_posix() for path in REQUIRED_FILES if not path.is_file()]
    memory, memory_error = (None, "Skipped because required files are missing.")
    if not missing:
        memory, memory_error = load_memory()
    test_result = run_tests() if not missing else None
    passed = not missing and memory is not None and test_result is not None and test_result.returncode == 0
    lines = [
        "# ISLAM Agent — تقرير التدقيق الآلي", "",
        f"- UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- Commit: {os.environ.get('GITHUB_SHA', 'not-provided')}",
        f"- Ref: {os.environ.get('GITHUB_REF', 'not-provided')}",
        "- Source modification: none", "- Physical measurements: none",
        "- Field-performance claims: none", "", "## فحص الملفات", "",
    ]
    if missing:
        lines.append("- FAIL — ملفات مطلوبة غير موجودة:")
        lines.extend(f"  - {path}" for path in missing)
    else:
        lines.append(f"- PASS — جميع الملفات المطلوبة موجودة ({len(REQUIRED_FILES)}).")
    lines.extend(["", "## ذاكرة المشروع وطابور المهام", ""])
    if memory is None:
        lines.append(f"- FAIL — {memory_error}")
    else:
        lines.extend([
            f"- PASS — schema v{memory['schema_version']}; updated {memory['updated_at']}",
            f"- المشروع: {memory['project']}",
            f"- قيود هندسية مسجلة: {len(memory['known_constraints'])}",
            f"- مهام محفوظة: {len(memory['next_tasks'])}",
        ])
        for task in memory["next_tasks"]:
            lines.append(f"  - {task['id']} [{task['status']}] {task['title']}")
    lines.extend(["", "## اختبارات الوحدة", ""])
    if test_result is None:
        lines.append("- NOT RUN — لم تبدأ الاختبارات بسبب نقص الملفات.")
    else:
        state = "PASS" if test_result.returncode == 0 else "FAIL"
        lines.append(f"- {state} — exit code: {test_result.returncode}")
        lines.extend(["", "```text", test_result.stdout.rstrip(), "```"])
    lines.extend([
        "", "## حدود هذا التقرير", "",
        "هذا تدقيق برمجي محدود. نجاح الاختبارات لا يثبت صحة النموذج الفيزيائي، "
        "ولا يثبت محاثة الملف أو عمق الكشف أو الأداء الميداني. لم تُشغّل مسوحات "
        "التقارب أو الحساسية في هذا الإصدار. الذاكرة ملف محفوظ في Git؛ لا تُحدّث "
        "تلقائياً بواسطة هذا الـWorkflow ذي صلاحية القراءة فقط.",
        "", f"## النتيجة النهائية: {'PASS' if passed else 'FAIL'}", "",
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