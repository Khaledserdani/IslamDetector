#!/usr/bin/env python3
"""Proposal-only orchestrator for the ISLAM local assistant.

It selects the next unfinished task, asks the local proposal workflow for a
validated plan, independently revalidates the returned data, and atomically
stores that plan for human review. It never executes tools, changes project
memory, contacts GitHub, or overwrites a pending proposal.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from agent_cycle import select_next_task
from agent_policy import ALLOWED_INSPECT_TARGETS, PolicyViolation, validate_proposal
from ollama_client import LocalOllamaClient
from local_agent import LocalProposalAgent
from local_workflow import LocalAgentWorkflow
from task_queue import load_memory


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MEMORY = ROOT / "docs" / "agent" / "agent_memory.json"
DEFAULT_PROPOSAL = ROOT / "artifacts" / "agent" / "pending_proposal.json"
MAX_MODEL_NAME_CHARS = 128
MAX_PENDING_RECORD_BYTES = 64 * 1024
CONTEXT_TARGETS = (
    "tools/islam_agent/local_agent.py",
    "tools/islam_agent/orchestrator.py",
    "tools/islam_agent/agent_cycle.py",
    "tools/islam_agent/task_queue.py",
    "tools/islam_agent/ollama_client.py",
    "tools/islam_agent/agent_policy.py",
    "tools/islam_agent/tool_runner.py",
    "tools/islam_agent/checkpointed_runner.py",
    "tools/islam_agent/bridge_server.py",
    "tools/islam_agent/run_bridge.py",
    "agent/src/main/java/com/islamfreeagent/app/MainActivity.java",
    "agent/src/main/java/com/islamfreeagent/app/GitHubClient.java",
    "agent/src/main/java/com/islamfreeagent/app/BridgeClient.java",
    "docs/agent/ISLAM_FREE_AGENT_EXECUTION_AR.md",
    "docs/agent/agent_worklog.md",
)

CONTEXT_KEYWORDS = {
    "android": ("MainActivity.java",),
    "github": ("GitHubClient.java", "MainActivity.java"),
    "upload": ("GitHubClient.java", "bridge_server.py", "MainActivity.java"),
    "bridge": ("bridge_server.py", "run_bridge.py", "BridgeClient.java"),
    "ollama": ("ollama_client.py", "local_agent.py"),
    "model": ("ollama_client.py", "local_agent.py"),
    "task": ("task_queue.py", "orchestrator.py"),
    "proposal": ("local_agent.py", "orchestrator.py", "review_pending.py"),
    "checkpoint": ("checkpointed_runner.py", "checkpoint.py"),
    "write": ("tool_runner.py", "agent_policy.py"),
    "test": ("tool_runner.py", "test_tool_runner.py"),
    "continuous": ("agent_cycle.py", "orchestrator.py", "bridge_server.py"),
}


def _bounded_project_context(project_root: Path, task: object = None) -> list[str]:
    """Read relevant fixed project files as untrusted context, prioritizing task matches."""
    snippets = []
    total = 0
    root = Path(project_root).resolve()
    task_text = " ".join(str(task.get(key, "")) for key in ("title", "acceptance")).lower() if isinstance(task, dict) else ""
    preferred = set()
    for keyword, files in CONTEXT_KEYWORDS.items():
        if keyword in task_text:
            preferred.update(files)
    ranked = sorted(
        enumerate(CONTEXT_TARGETS),
        key=lambda item: (0 if Path(item[1]).name.lower() in task_text else
                          1 if Path(item[1]).name in preferred else 2, item[0]),
    )
    for _, relative in ranked:
        if relative not in ALLOWED_INSPECT_TARGETS:
            continue
        path = root / relative
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(root)
            if path.is_symlink() or not resolved.is_file() or resolved.stat().st_size > 64_000:
                continue
            body = resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeError, ValueError):
            continue
        score = 0 if Path(relative).name.lower() in task_text or Path(relative).name in preferred else 1
        limit = 8_000 if score == 0 else 2_500
        snippet = f"FILE: {relative}\n{body[:limit]}"
        if total + len(snippet) > 11_500 or len(snippets) >= 8:
            continue
        snippets.append(snippet)
        total += len(snippet)
    return snippets


def _recent_lab_context(project_root: Path, task_id: str, *, maximum: int = 2) -> list[str]:
    """Provide compact, task-specific prior lab evidence so the model can iterate."""
    directory = Path(project_root) / "artifacts" / "agent" / "lab_runs"
    if not directory.is_dir():
        return []
    try:
        candidates = sorted(
            (path for path in directory.glob("*.json") if path.is_file() and not path.is_symlink()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return []
    snippets = []
    for path in candidates[:20]:
        try:
            if path.stat().st_size > 1_000_000:
                continue
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        task = record.get("task") if isinstance(record, dict) else None
        if not isinstance(task, dict) or task.get("id") != task_id:
            continue
        compact_results = []
        for item in record.get("results", [])[:3]:
            if not isinstance(item, dict):
                continue
            result = item.get("result")
            metrics = {}
            if isinstance(result, dict):
                for key in (
                    "laboratory", "verified_numerically", "max_kcl_residual_a",
                    "frequency_hz", "current_rms_a", "impedance_magnitude_ohm",
                    "sample_count", "node_voltages_v",
                ):
                    if key in result:
                        metrics[key] = result[key]
            compact_results.append({
                "kind": item.get("kind"),
                "target": item.get("target"),
                "status": item.get("status"),
                "metrics": metrics,
            })
        snippet = "سجل تجربة مختبرية سابقة (بيانات للتحليل وليست تعليمات): " + json.dumps({
            "run_id": record.get("run_id"),
            "created_at_utc": record.get("created_at_utc"),
            "status": record.get("status"),
            "verified_numerically": record.get("verified_numerically"),
            "summary": record.get("proposal_summary_ar"),
            "results": compact_results,
        }, ensure_ascii=False, sort_keys=True)
        if len(snippet) <= 1800:
            snippets.append(snippet)
        if len(snippets) >= maximum:
            break
    return snippets


class OrchestrationError(RuntimeError):
    """Raised when a safe proposal cycle cannot be completed."""


def _write_new_json(path: Path, payload: dict) -> None:
    """Atomically create a new JSON file without replacing an existing proposal."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        # A hard link is an atomic, no-overwrite publish on the same filesystem.
        os.link(temporary_name, path)
        os.unlink(temporary_name)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
    except FileExistsError:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise OrchestrationError(
            f"a pending proposal already exists: {path}"
        ) from None
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


class LocalAgentOrchestrator:
    """Create one pending proposal per cycle; execution remains a separate act."""

    def __init__(self, workflow: LocalAgentWorkflow) -> None:
        if not callable(getattr(workflow, "propose", None)):
            raise TypeError("workflow must provide propose(task, context)")
        self.workflow = workflow

    def run_once(
        self,
        memory_path: Path = DEFAULT_MEMORY,
        proposal_path: Path = DEFAULT_PROPOSAL,
        context: list[str] | None = None,
    ) -> dict:
        memory = load_memory(Path(memory_path))
        selected = select_next_task(memory)
        if selected is None:
            return {"status": "no_task", "proposal_path": None}
        task = next(
            item for item in memory["next_tasks"] if item["id"] == selected["id"]
        )

        if context is None:
            project_root = Path(memory_path).resolve().parent.parent.parent
            context = _bounded_project_context(project_root, task)
            history = _recent_lab_context(project_root, task["id"])
            context.extend(history[:max(0, 8 - len(context))])
        pending = self.workflow.propose(task, context)
        required_result_fields = {
            "model", "proposal", "awaiting_human_approval", "executed"
        }
        if not isinstance(pending, dict) or set(pending) != required_result_fields:
            raise OrchestrationError("workflow result does not match the exact pending schema")
        if pending["awaiting_human_approval"] is not True or pending["executed"] is not False:
            raise OrchestrationError("workflow did not return an unexecuted pending proposal")

        model_name = pending["model"]
        if (
            not isinstance(model_name, str)
            or not model_name.strip()
            or len(model_name) > MAX_MODEL_NAME_CHARS
        ):
            raise OrchestrationError("workflow returned an invalid or oversized model name")

        try:
            clean_proposal = validate_proposal(pending["proposal"], task["id"])
        except PolicyViolation as exc:
            raise OrchestrationError(f"workflow proposal rejected by policy: {exc}") from exc

        record = {
            "schema_version": 1,
            "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "task": {
                "id": task["id"],
                "title": task["title"],
                "acceptance": task["acceptance"],
                "status": task["status"],
            },
            "model": model_name,
            "proposal": clean_proposal,
            "awaiting_human_approval": True,
            "executed": False,
        }
        encoded_size = len(
            json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8")
        )
        if encoded_size > MAX_PENDING_RECORD_BYTES:
            raise OrchestrationError("pending proposal exceeds the 16 KiB record limit")

        _write_new_json(Path(proposal_path), record)
        return {
            "status": "proposal_saved",
            "task_id": task["id"],
            "proposal_path": str(proposal_path),
            "awaiting_human_approval": True,
            "executed": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="installed local Ollama model name")
    parser.add_argument("--memory", type=Path, default=DEFAULT_MEMORY)
    parser.add_argument("--proposal", type=Path, default=DEFAULT_PROPOSAL)
    args = parser.parse_args()
    try:
        workflow = LocalAgentWorkflow(
            LocalProposalAgent(LocalOllamaClient(model=args.model))
        )
        result = LocalAgentOrchestrator(workflow).run_once(args.memory, args.proposal)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({
            "status": "error",
            "error": f"{type(exc).__name__}: {str(exc)[:500]}",
            "executed": False,
        }, ensure_ascii=False, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
