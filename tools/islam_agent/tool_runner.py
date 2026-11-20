"""Bounded executor for policy-approved ISLAM agent steps.

No arbitrary shell, network, GitHub operations, or unrestricted file writes
are available. Writes are limited to exact source/document paths.
"""
from __future__ import annotations

import hashlib
import os
import stat
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from agent_policy import (
    ALLOWED_INSPECT_TARGETS, ALLOWED_WRITE_TARGETS, MAX_WRITE_CHARS,
    PolicyViolation, validate_proposal,
)


ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = ROOT / "tools" / "islam_agent"
MAX_INSPECT_BYTES = 64_000
MAX_OUTPUT_CHARS = 20_000
TEST_TIMEOUT_SECONDS = 120
ANDROID_TEST_TIMEOUT_SECONDS = 900
AGENT_TEST_MODULES = (
    "test_task_queue", "test_ollama_client", "test_agent_policy",
    "test_tool_runner", "test_checkpoint", "test_checkpointed_runner",
    "test_local_agent", "test_local_workflow", "test_agent_cycle",
    "test_orchestrator", "test_review_pending", "test_bridge_server",
    "test_safe_writer",
)


class ToolExecutionError(RuntimeError):
    """Raised when an approved, fixed tool cannot be executed safely."""


class SafeToolRunner:
    def __init__(self, root: Path = ROOT) -> None:
        self.root = Path(root).resolve()
        self.agent_dir = self.root / "tools" / "islam_agent"

    def _safe_target(self, relative_path: str, allowed: set[str]) -> Path:
        if relative_path not in allowed:
            raise PolicyViolation("file target is not allowlisted")
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise PolicyViolation("file path is not a safe relative path")
        candidate = self.root / relative
        try:
            candidate.resolve(strict=False).relative_to(self.root)
        except ValueError:
            raise PolicyViolation("file path escapes the project root") from None
        # Refuse symlinks in every existing path component to prevent redirection.
        current = self.root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise PolicyViolation("symbolic links are not accepted in agent file paths")
        return candidate

    def _inspect(self, relative_path: str) -> dict:
        path = self._safe_target(relative_path, ALLOWED_INSPECT_TARGETS)
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
            "kind": "inspect", "target": relative_path, "status": "completed",
            "content": content[:MAX_OUTPUT_CHARS], "truncated": len(content) > MAX_OUTPUT_CHARS,
        }

    def _write_file(self, relative_path: str, content: str) -> dict:
        path = self._safe_target(relative_path, ALLOWED_WRITE_TARGETS)
        if not isinstance(content, str) or not content.strip() or len(content) > MAX_WRITE_CHARS:
            raise PolicyViolation("write content is empty or exceeds the configured limit")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and (path.is_symlink() or not path.is_file()):
                raise ToolExecutionError("write target exists but is not a regular file")
            mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
            encoded = content.encode("utf-8")
            fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(temp_name, mode)
                os.replace(temp_name, path)
            except Exception:
                try:
                    os.unlink(temp_name)
                except FileNotFoundError:
                    pass
                raise
        except (OSError, UnicodeError):
            raise ToolExecutionError(f"approved file could not be written safely: {relative_path}") from None
        return {
            "kind": "write_file", "target": relative_path, "status": "written",
            "bytes": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest(),
        }

    def _run_tests(self, target: str) -> dict:
        if target == "agent_unit_tests":
            if not self.agent_dir.is_dir():
                raise ToolExecutionError("agent test directory is missing")
            command = [sys.executable, "-m", "unittest", "-v", *AGENT_TEST_MODULES]
            cwd = self.agent_dir
            timeout = TEST_TIMEOUT_SECONDS
        elif target == "android_unit_tests":
            if not shutil.which("gradle"):
                raise ToolExecutionError("Gradle is not installed; Android source changes cannot be approved for upload")
            command = ["gradle", "--no-daemon", ":agent:testDebugUnitTest", ":agent:assembleDebug"]
            cwd = self.root
            timeout = ANDROID_TEST_TIMEOUT_SECONDS
        else:
            raise PolicyViolation("test target is not allowlisted")
        try:
            result = subprocess.run(
                command, cwd=cwd, shell=False, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired:
            raise ToolExecutionError("approved test suite timed out") from None
        except OSError:
            raise ToolExecutionError("approved test suite could not be started") from None
        output = result.stdout or ""
        return {
            "kind": "run_test", "target": target,
            "status": "passed" if result.returncode == 0 else "failed",
            "exit_code": result.returncode, "output": output[-MAX_OUTPUT_CHARS:],
            "truncated": len(output) > MAX_OUTPUT_CHARS,
        }

    def execute_plan(self, proposal: object, expected_task_id: str, *, human_approved: bool = False) -> list[dict]:
        approved = validate_proposal(proposal, expected_task_id)
        if human_approved is not True:
            raise PolicyViolation("explicit human approval is required before tool execution")
        results = []
        for step in approved["steps"]:
            if step["kind"] == "inspect":
                result = self._inspect(step["target"])
            elif step["kind"] == "write_file":
                result = self._write_file(step["target"], step["content"])
            elif step["kind"] == "run_test":
                result = self._run_tests(step["target"])
            else:
                raise PolicyViolation("step kind is not executable")
            results.append(result)
            if result["kind"] == "run_test" and result["status"] != "passed":
                break
        return results
