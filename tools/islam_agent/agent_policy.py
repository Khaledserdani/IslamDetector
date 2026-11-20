"""Strict policy gate for model-proposed plans.

This module validates proposal data only. Execution is delegated to fixed,
allowlisted tools; model-supplied command strings are never accepted.
"""
from __future__ import annotations


ALLOWED_STEP_KINDS = {"inspect", "run_test", "write_file"}
# Deliberately exact paths. The agent cannot write credentials, workflows,
# policy/runner code, project memory, arbitrary paths, or files outside this list.
ALLOWED_WRITE_TARGETS = {
    "tools/islam_agent/local_agent.py",
    "tools/islam_agent/orchestrator.py",
    "tools/islam_agent/agent_cycle.py",
    "docs/agent/ISLAM_FREE_AGENT_EXECUTION_AR.md",
    "docs/agent/agent_worklog.md",
}
ALLOWED_INSPECT_TARGETS = {
    "docs/agent/OLLAMA_LOCAL_AGENT_DESIGN_AR.md",
    "docs/agent/agent_memory.json",
    "tools/islam_agent/ollama_client.py",
    "tools/islam_agent/task_queue.py",
    "tools/islam_agent/agent_cycle.py",
    "tools/islam_agent/orchestrator.py",
    "tools/islam_agent/review_pending.py",
    "tools/islam_agent/bridge_server.py",
    "tools/islam_agent/run_bridge.py",
    "tools/islam_agent/agent_policy.py",
    "agent/src/main/java/com/islamfreeagent/app/MainActivity.java",
    "agent/src/main/java/com/islamfreeagent/app/GitHubClient.java",
    "agent/src/main/java/com/islamfreeagent/app/BridgeClient.java",
    "tools/islam_agent/tool_runner.py",
    "tools/islam_agent/checkpointed_runner.py",
    "docs/agent/ISLAM_LOCAL_ORCHESTRATOR_AR.md",
    *ALLOWED_WRITE_TARGETS,
}
ALLOWED_TEST_TARGETS = {"agent_unit_tests", "android_unit_tests"}
MAX_STEPS = 5
MAX_SUMMARY_CHARS = 500
MAX_CLAIMS = 20
MAX_CLAIM_CHARS = 500
MAX_WRITE_CHARS = 12_000


class PolicyViolation(ValueError):
    """Raised when a model proposal violates the fixed policy."""


def validate_proposal(proposal: object, expected_task_id: str) -> dict:
    """Validate an exact schema and return a defensive, bounded copy."""
    if not isinstance(expected_task_id, str) or not expected_task_id.strip():
        raise PolicyViolation("expected_task_id must be a non-empty string")
    if not isinstance(proposal, dict):
        raise PolicyViolation("proposal must be a JSON object")

    required = {"task_id", "summary_ar", "steps", "needs_human_approval", "claims_to_verify"}
    if set(proposal) != required:
        raise PolicyViolation("proposal fields do not match the exact allowed schema")
    task_id = proposal["task_id"]
    if not isinstance(task_id, str) or task_id != expected_task_id:
        raise PolicyViolation("proposal task_id does not match the active task")
    summary = proposal["summary_ar"]
    if not isinstance(summary, str) or not summary.strip() or len(summary) > MAX_SUMMARY_CHARS:
        raise PolicyViolation("summary_ar must be a non-empty string within the size limit")
    if proposal["needs_human_approval"] is not True:
        raise PolicyViolation("human approval must remain required in this version")

    steps = proposal["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise PolicyViolation("steps must contain between 1 and 5 entries")
    clean_steps = []
    for step in steps:
        if not isinstance(step, dict):
            raise PolicyViolation("each step must be an object")
        kind = step.get("kind")
        target = step.get("target")
        if not isinstance(kind, str) or kind not in ALLOWED_STEP_KINDS:
            raise PolicyViolation("step kind is not allowlisted")
        if not isinstance(target, str):
            raise PolicyViolation("step target must be a string")
        expected_keys = {"kind", "target", "content"} if kind == "write_file" else {"kind", "target"}
        if set(step) != expected_keys:
            if kind == "write_file":
                raise PolicyViolation("write_file steps must contain only kind, target, and content")
            raise PolicyViolation("each step must contain only kind and target")
        if kind == "inspect" and target not in ALLOWED_INSPECT_TARGETS:
            raise PolicyViolation("inspect target is not allowlisted")
        if kind == "run_test" and target not in ALLOWED_TEST_TARGETS:
            raise PolicyViolation("test target is not allowlisted")
        if kind == "write_file":
            if target not in ALLOWED_WRITE_TARGETS:
                raise PolicyViolation("write target is not allowlisted")
            content = step["content"]
            if not isinstance(content, str) or not content.strip() or len(content) > MAX_WRITE_CHARS:
                raise PolicyViolation("write content must be non-empty text within the 12,000 character limit")
            clean_steps.append({"kind": kind, "target": target, "content": content})
        else:
            clean_steps.append({"kind": kind, "target": target})

    write_targets = [step["target"] for step in clean_steps if step["kind"] == "write_file"]
    test_targets = {step["target"] for step in clean_steps if step["kind"] == "run_test"}
    if any(target.startswith("tools/islam_agent/") for target in write_targets):
        if "agent_unit_tests" not in test_targets:
            raise PolicyViolation("Python agent edits require agent_unit_tests in the same approved plan")

    claims = proposal["claims_to_verify"]
    if not isinstance(claims, list) or len(claims) > MAX_CLAIMS:
        raise PolicyViolation("claims_to_verify must be a list of at most 20 strings")
    clean_claims = []
    for claim in claims:
        if not isinstance(claim, str) or not claim.strip() or len(claim) > MAX_CLAIM_CHARS:
            raise PolicyViolation("each claim must be a non-empty bounded string")
        clean_claims.append(claim)

    return {
        "task_id": task_id,
        "summary_ar": summary,
        "steps": clean_steps,
        "needs_human_approval": True,
        "claims_to_verify": clean_claims,
    }
