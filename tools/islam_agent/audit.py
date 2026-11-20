#!/usr/bin/env python3
"""Safe, deterministic audit runner for the ISLAM project.

It validates project memory and runs engineering plus agent unit tests.
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
AGENT_DIR = ROOT / "tools" / "islam_agent"
MEMORY_FILE = ROOT / "docs" / "agent" / "agent_memory.json"
REQUIRED_FILES = (
    SPIRAL_DIR / "mono_spiral_geometry.py",
    SPIRAL_DIR / "conductor_effects.py",
    SPIRAL_DIR / "mono_spiral_disk.py",
    SPIRAL_DIR / "run_disk_convergence.py",
    SPIRAL_DIR / "test_mono_spiral_geometry.py",
    SPIRAL_DIR / "greenhouse_inductance.py",
    SPIRAL_DIR / "test_greenhouse_inductance.py",
    SPIRAL_DIR / "test_mono_spiral_disk.py",
    SPIRAL_DIR / "test_conductor_effects.py",
    SPIRAL_DIR / "rectangular_cross_section_gmd.py",
    SPIRAL_DIR / "test_rectangular_cross_section_gmd.py",
    SPIRAL_DIR / "rectangular_segment_inductance.py",
    SPIRAL_DIR / "test_rectangular_segment_inductance.py",
    SPIRAL_DIR / "rectangular_segment_general_mutual.py",
    SPIRAL_DIR / "test_rectangular_segment_general_mutual.py",
    MEMORY_FILE,
    AGENT_DIR / "task_queue.py",
    AGENT_DIR / "test_task_queue.py",
    AGENT_DIR / "ollama_client.py",
    AGENT_DIR / "test_ollama_client.py",
    AGENT_DIR / "ollama_preflight.py",
    AGENT_DIR / "test_ollama_preflight.py",
    AGENT_DIR / "agent_policy.py",
    AGENT_DIR / "test_agent_policy.py",
    AGENT_DIR / "tool_runner.py",
    AGENT_DIR / "test_tool_runner.py",
    AGENT_DIR / "checkpoint.py",
    AGENT_DIR / "test_checkpoint.py",
    AGENT_DIR / "checkpointed_runner.py",
    AGENT_DIR / "test_checkpointed_runner.py",
    AGENT_DIR / "local_agent.py",
    AGENT_DIR / "test_local_agent.py",
    AGENT_DIR / "local_workflow.py",
    AGENT_DIR / "test_local_workflow.py",
    AGENT_DIR / "agent_cycle.py",
    AGENT_DIR / "test_agent_cycle.py",
    AGENT_DIR / "orchestrator.py",
    AGENT_DIR / "bridge_health.py",
    AGENT_DIR / "test_bridge_health.py",
    AGENT_DIR / "test_bridge_server.py",
    AGENT_DIR / "review_pending.py",
    AGENT_DIR / "test_review_pending.py",
    AGENT_DIR / "test_orchestrator.py",
    ROOT / "docs" / "agent" / "ISLAM_LOCAL_ORCHESTRATOR_AR.md",
)


def load_memory() -> tuple[dict | None, str | None]:
    try:
        memory = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"Cannot read valid JSON: {exc}"
    if not isinstance(memory, dict) or memory.get("schema_version") != 1:
        return None, "Invalid memory object or unsupported schema_version (expected 1)."
    for key in ("project", "updated_at", "known_constraints", "next_tasks"):
        if key not in memory:
            return None, f"Missing required memory key: {key}"
    if not isinstance(memory["known_constraints"], list) or not isinstance(memory["next_tasks"], list):
        return None, "known_constraints and next_tasks must be lists."
    seen: set[str] = set()
    valid_statuses = {"pending", "in_progress", "blocked", "completed"}
    for index, task in enumerate(memory["next_tasks"]):
        if not isinstance(task, dict) or not all(k in task for k in ("id", "title", "status", "acceptance")):
            return None, f"Invalid task entry at index {index}: missing fields or non-object."
        if not isinstance(task["id"], str) or not task["id"].strip():
            return None, f"Invalid task id at index {index}: expected non-empty string."
        if not isinstance(task["title"], str) or not task["title"].strip():
            return None, f"Invalid task title at index {index}: expected non-empty string."
        if not isinstance(task["acceptance"], str) or not task["acceptance"].strip():
            return None, f"Invalid task acceptance at index {index}: expected non-empty string."
        if not isinstance(task["status"], str) or task["status"] not in valid_statuses:
            return None, f"Invalid task status at index {index}: expected one of {sorted(valid_statuses)}."
        if task["id"] in seen:
            return None, f"Duplicate task id: {task['id']}"
        seen.add(task["id"])
    return memory, None


def run_tests() -> subprocess.CompletedProcess[str]:
    commands = (
        (SPIRAL_DIR, [sys.executable, "-m", "unittest", "-v", "test_mono_spiral_geometry", "test_mono_spiral_disk", "test_conductor_effects", "test_greenhouse_inductance", "test_rectangular_cross_section_gmd", "test_rectangular_segment_inductance", "test_rectangular_segment_general_mutual"]),
        (AGENT_DIR, [sys.executable, "-m", "unittest", "-v", "test_task_queue", "test_ollama_client", "test_ollama_preflight", "test_agent_policy", "test_tool_runner", "test_checkpoint", "test_checkpointed_runner", "test_local_agent", "test_local_workflow", "test_agent_cycle", "test_orchestrator", "test_review_pending", "test_bridge_health", "test_bridge_server"]),
    )
    outputs = []
    exit_code = 0
    for cwd, command in commands:
        result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        outputs.append(f"$ {' '.join(command)}\n{result.stdout.rstrip()}")
        if result.returncode != 0 and exit_code == 0:
            exit_code = result.returncode
    return subprocess.CompletedProcess(args=["ISLAM test suites"], returncode=exit_code, stdout="\n\n".join(outputs))


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
        "التقارب أو الحساسية في هذا الإصدار. أداة الطابور تعدّل ملف الذاكرة محلياً "
        "فقط عند استدعائها؛ يحفظ checkpoint التقدم محلياً. لا يكتب هذا الـWorkflow إلى المستودع.",
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