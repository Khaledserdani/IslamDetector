"""Bounded executor for policy-approved ISLAM agent steps.

No arbitrary shell, network, writes, or GitHub operations are available.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from agent_policy import ALLOWED_INSPECT_TARGETS, PolicyViolation, validate_proposal


ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = ROOT / "tools" / "islam_agent"
MAX_INSPECT_BYTES = 64_000
MAX_OUTPUT_CHARS = 20_000
TEST_TIMEOUT_SECONDS = 120
AGENT_TEST_MODULES = (
    "test_task_queue",
    "test_ollama_client",
    "test_agent_policy",
    "test_tool_runner",
    "test_checkpoint",
    "test_checkpointed_runner",
    "test_local_agent",
    "test_local_workflow",
    "test_agent_cycle",
)


class ToolExecutionError(RuntimeError):
    """Raised when an approved, fixed tool cannot be executed safely."""


class SafeToolRunner:
    def __init__(self, root: Path = ROOT) -> None:
        self.root = Path(root).resolve()
        self.agent_dir = self.root / "tools" / "islam_agent"

    def _inspect(self, relative_path: str) -> dict:
        if relative_path not in ALLOWED_INSPECT_TARGETS:
            raise PolicyViolation("inspect target is not allowlisted")
        path = (self.root / relative_path).resolve()
        try:
            path.relative_to(self.root)
        except ValueError:
            raise PolicyViolation("inspect path escapes the project root") from None
        try:
            if not path.is_file():
                raise ToolExecutionError(f"approved file does not exist: {relative_path}")
            size = path.stat().st_size
            if size > MAX_INSPECT_BYTES:
                raise ToolExecutionError(f"approved file exceeds {MAX_INSPECT_BYTES} bytes")
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            raise ToolExecutionError(f"approved file could not be read safely: {relative_path}") from None
        return {
            "kind": "inspect",
            "target": relative_path,
            "status": "completed",
            "content": content[:MAX_OUTPUT_CHARS],
            "truncated": len(content) > MAX_OUTPUT_CHARS,
        }

    def _run_tests(self, target: str) -> dict:
        if target != "agent_unit_tests":
            raise PolicyViolation("test target is not allowlisted")
        if not self.agent_dir.is_dir():
            raise ToolExecutionError("agent test directory is missing")
        command = [
            sys.executable,
            "-m",
            "unittest",
            "-v",
            *AGENT_TEST_MODULES,
        ]
        try:
            result = subprocess.run(
                command,
                cwd=self.agent_dir,
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=TEST_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise ToolExecutionError("approved agent test suite timed out") from None
        except OSError:
            raise ToolExecutionError("approved agent test suite could not be started") from None
        output = result.stdout or ""
        return {
            "kind": "run_test",
            "target": target,
            "status": "passed" if result.returncode == 0 else "failed",
            "exit_code": result.returncode,
            "output": output[-MAX_OUTPUT_CHARS:],
            "truncated": len(output) > MAX_OUTPUT_CHARS,
        }

    def execute_plan(
        self,
        proposal: object,
        expected_task_id: str,
        *,
        human_approved: bool = False,
    ) -> list[dict]:
        approved = validate_proposal(proposal, expected_task_id)
        if human_approved is not True:
            raise PolicyViolation("explicit human approval is required before tool execution")
        results = []
        for step in approved["steps"]:
            if step["kind"] == "inspect":
                result = self._inspect(step["target"])
            elif step["kind"] == "run_test":
                result = self._run_tests(step["target"])
            else:  # Defensive: policy gate should make this unreachable.
                raise PolicyViolation("step kind is not executable")
            results.append(result)
            if result["kind"] == "run_test" and result["status"] != "passed":
                break
        return results
