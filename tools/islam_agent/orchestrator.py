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
    "tools/islam_agent/agent_policy.py",
    "tools/islam_agent/tool_runner.py",
    "tools/islam_agent/checkpointed_runner.py",
    "tools/islam_agent/local_agent.py",
    "agent/src/main/java/com/islamfreeagent/app/MainActivity.java",
    "agent/src/main/java/com/islamfreeagent/app/GitHubClient.java",
    "docs/agent/ISLAM_FREE_AGENT_EXECUTION_AR.md",
    "docs/agent/agent_worklog.md",
)


def _bounded_project_context(project_root: Path) -> list[str]:
    """Read a small, fixed set of project files as untrusted model context."""
    snippets = []
    total = 0
    root = Path(project_root).resolve()
    for relative in CONTEXT_TARGETS:
        if relative not in ALLOWED_INSPECT_TARGETS:
            continue
        path = root / relative
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(root)
            if path.is_symlink() or not resolved.is_file() or resolved.stat().st_size > 64_000:
                continue
            body = resolved.read_text(encoding="utf-8")[:1200]
        except (OSError, UnicodeError, ValueError):
            continue
        snippet = f"FILE: {relative}\n{body}"
        if total + len(snippet) > 11_500 or len(snippets) >= 8:
            break
        snippets.append(snippet)
        total += len(snippet)
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
            context = _bounded_project_context(project_root)
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
