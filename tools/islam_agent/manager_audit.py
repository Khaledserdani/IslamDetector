#!/usr/bin/env python3
"""ISLAM FREE AGENT-only audit; deliberately excludes detector engineering tracks."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = ROOT / "tools" / "islam_agent"
MEMORY_FILE = ROOT / "docs" / "agent" / "agent_memory.json"
TEST_TIMEOUT_SECONDS = 180
TEST_MODULES = (
    "test_task_queue",
    "test_ollama_client",
    "test_ollama_preflight",
    "test_agent_policy",
    "test_tool_runner",
    "test_checkpoint",
    "test_checkpointed_runner",
    "test_local_agent",
    "test_local_workflow",
    "test_agent_cycle",
    "test_orchestrator",
    "test_review_pending",
    "test_bridge_health",
    "test_bridge_server",
    "test_manager_audit",
)
REQUIRED_FILES = (
    MEMORY_FILE,
    ROOT / "docs" / "agent" / "ISLAM_LOCAL_ORCHESTRATOR_AR.md",
    ROOT / "docs" / "agent" / "ISLAM_AGENT_CYCLE_AR.md",
    ROOT / "docs" / "agent" / "OLLAMA_LOCAL_AGENT_DESIGN_AR.md",
    ROOT / "docs" / "agent" / "ANDROID_AGENT_BRIDGE_API_AR.md",
    AGENT_DIR / "agent_policy.py",
    AGENT_DIR / "agent_cycle.py",
    AGENT_DIR / "bridge_health.py",
    AGENT_DIR / "bridge_server.py",
    AGENT_DIR / "checkpoint.py",
    AGENT_DIR / "checkpointed_runner.py",
    AGENT_DIR / "local_agent.py",
    AGENT_DIR / "local_workflow.py",
    AGENT_DIR / "ollama_client.py",
    AGENT_DIR / "ollama_preflight.py",
    AGENT_DIR / "orchestrator.py",
    AGENT_DIR / "review_pending.py",
    AGENT_DIR / "task_queue.py",
    AGENT_DIR / "tool_runner.py",
    AGENT_DIR / "test_agent_policy.py",
    AGENT_DIR / "test_agent_cycle.py",
    AGENT_DIR / "test_bridge_health.py",
    AGENT_DIR / "test_bridge_server.py",
    AGENT_DIR / "test_checkpoint.py",
    AGENT_DIR / "test_checkpointed_runner.py",
    AGENT_DIR / "test_local_agent.py",
    AGENT_DIR / "test_local_workflow.py",
    AGENT_DIR / "test_manager_audit.py",
    AGENT_DIR / "test_ollama_client.py",
    AGENT_DIR / "test_ollama_preflight.py",
    AGENT_DIR / "test_orchestrator.py",
    AGENT_DIR / "test_review_pending.py",
    AGENT_DIR / "test_task_queue.py",
    AGENT_DIR / "test_tool_runner.py",
)


def validate_memory(path: Path = MEMORY_FILE) -> tuple[dict | None, str | None]:
    try:
        memory = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"Cannot read valid project memory: {type(exc).__name__}"
    if not isinstance(memory, dict) or memory.get("schema_version") != 1:
        return None, "Unsupported or invalid memory schema."
    for key in ("project", "updated_at", "known_constraints", "next_tasks"):
        if key not in memory:
            return None, f"Missing memory key: {key}"
    if not isinstance(memory["known_constraints"], list) or not isinstance(memory["next_tasks"], list):
        return None, "Memory constraints and tasks must be lists."
    seen = set()
    valid_statuses = {"pending", "in_progress", "blocked", "completed"}
    for index, task in enumerate(memory["next_tasks"]):
        if not isinstance(task, dict):
            return None, f"Task {index} is not an object."
        for key in ("id", "title", "acceptance", "status"):
            if not isinstance(task.get(key), str) or not task[key].strip():
                return None, f"Task {index} has an invalid {key}."
        if task["status"] not in valid_statuses:
            return None, f"Task {index} has an unknown status."
        if task["id"] in seen:
            return None, f"Duplicate task ID: {task['id']}"
        seen.add(task["id"])
    return memory, None


def run_tests(root: Path = ROOT, runner: Callable = subprocess.run) -> subprocess.CompletedProcess:
    command = [sys.executable, "-m", "unittest", "-v", *TEST_MODULES]
    try:
        result = runner(
            command, cwd=Path(root) / "tools" / "islam_agent",
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=TEST_TIMEOUT_SECONDS, shell=False, check=False,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(command, 124, "FAIL: manager test suite timed out.")
    except OSError as exc:
        return subprocess.CompletedProcess(command, 127, f"FAIL: could not start manager tests: {type(exc).__name__}")
    return subprocess.CompletedProcess(command, result.returncode, result.stdout or "")


def audit(root: Path = ROOT, runner: Callable = subprocess.run) -> dict:
    root = Path(root).resolve()
    required = tuple(root / path.relative_to(ROOT) for path in REQUIRED_FILES)
    missing = [path.relative_to(root).as_posix() for path in required if not path.is_file()]
    memory, memory_error = validate_memory(root / "docs" / "agent" / "agent_memory.json") if not missing else (None, "Skipped because files are missing.")
    tests = run_tests(root, runner) if not missing and memory is not None else None
    passed = not missing and memory is not None and tests is not None and tests.returncode == 0
    return {
        "scope": "ISLAM FREE AGENT manager only",
        "passed": passed,
        "missing_files": missing,
        "memory_error": memory_error,
        "task_count": len(memory["next_tasks"]) if memory else 0,
        "test_result": tests,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default="artifacts/agent/manager-audit.md")
    args = parser.parse_args()
    result = audit()
    tests = result["test_result"]
    lines = [
        "# ISLAM FREE AGENT — تدقيق المدير المساعد",
        "",
        f"- UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- Commit: {os.environ.get('GITHUB_SHA', 'not-provided')}",
        f"- Ref: {os.environ.get('GITHUB_REF', 'not-provided')}",
        "- Scope: manager assistant only; detector/coil simulation code is excluded.",
        "- Source modification: none; GitHub writes and PR merges: none.",
        "",
        "## ملفات المدير المساعد",
        "",
    ]
    if result["missing_files"]:
        lines.append("- FAIL — ملفات ناقصة:")
        lines.extend(f"  - {path}" for path in result["missing_files"])
    else:
        lines.append(f"- PASS — {len(REQUIRED_FILES)} ملفاً مطلوباً موجود.")
    lines.extend(["", "## ذاكرة المهام", ""])
    if result["memory_error"]:
        lines.append(f"- FAIL — {result['memory_error']}")
    else:
        lines.append(f"- PASS — الذاكرة صالحة؛ {result['task_count']} مهمة.")
    lines.extend(["", "## اختبارات المدير المساعد", ""])
    if tests is None:
        lines.append("- NOT RUN — أوقفت بوابة الملفات/الذاكرة الاختبارات.")
    else:
        lines.append(f"- {'PASS' if tests.returncode == 0 else 'FAIL'} — exit code {tests.returncode}.")
        lines.extend(["", "\u0060\u0060\u0060text", tests.stdout.rstrip(), "\u0060\u0060\u0060"])
    lines.extend([
        "",
        "## حدود الاعتماد",
        "",
        "هذا تدقيق برمجي للمدير المساعد فقط. لا يثبت اتصال Ollama على جهاز المستخدم، "
        "ولا يثبت اقتران هاتف فعلي أو تشغيل APK على جهاز حقيقي. لا ينفذ اقتراحات النموذج "
        "ولا يغير ذاكرة المشروع أو ملفات المصدر.",
        "",
        f"## النتيجة: {'PASS' if result['passed'] else 'FAIL'}",
        "",
    ])
    report = Path(args.report)
    if not report.is_absolute():
        report = ROOT / report
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
