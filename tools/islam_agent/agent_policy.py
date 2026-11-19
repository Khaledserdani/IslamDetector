"""Strict policy gate for model-proposed plans.

This module validates data only. It does not execute tools, shell commands,
read files, or contact GitHub.
"""
from __future__ import annotations


ALLOWED_STEP_KINDS = {"inspect", "run_test"}
ALLOWED_INSPECT_TARGETS = {
    "docs/agent/OLLAMA_LOCAL_AGENT_DESIGN_AR.md",
    "docs/agent/agent_memory.json",
    "tools/islam_agent/ollama_client.py",
    "tools/islam_agent/task_queue.py",
}
ALLOWED_TEST_TARGETS = {"agent_unit_tests"}
MAX_STEPS = 5
MAX_SUMMARY_CHARS = 500
MAX_CLAIMS = 20
MAX_CLAIM_CHARS = 500


class PolicyViolation(ValueError):
    """Raised when a model proposal violates the fixed policy."""


def validate_proposal(proposal: object, expected_task_id: str) -> dict:
    """Validate an exact proposal schema and return a defensive copy.

    Only read-only inspect targets and one named test suite are accepted.
    No command text, arbitrary paths, write operations, or tool arguments
    are part of this schema.
    """
    if not isinstance(expected_task_id, str) or not expected_task_id.strip():
        raise PolicyViolation("expected_task_id must be a non-empty string")
    if not isinstance(proposal, dict):
        raise PolicyViolation("proposal must be a JSON object")

    required = {
        "task_id",
        "summary_ar",
        "steps",
        "needs_human_approval",
        "claims_to_verify",
    }
    if set(proposal) != required:
        raise PolicyViolation("proposal fields do not match the exact allowed schema")

    task_id = proposal["task_id"]
    if not isinstance(task_id, str) or task_id != expected_task_id:
        raise PolicyViolation("proposal task_id does not match the active task")

    summary = proposal["summary_ar"]
    if not isinstance(summary, str) or not summary.strip() or len(summary) > MAX_SUMMARY_CHARS:
        raise PolicyViolation("summary_ar must be a non-empty string within the size limit")

    approval = proposal["needs_human_approval"]
    if not isinstance(approval, bool):
        raise PolicyViolation("needs_human_approval must be a boolean")
    if approval is not True:
        raise PolicyViolation("human approval must remain required in this version")

    steps = proposal["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise PolicyViolation("steps must contain between 1 and 5 entries")

    clean_steps = []
    for step in steps:
        if not isinstance(step, dict) or set(step) != {"kind", "target"}:
            raise PolicyViolation("each step must contain only kind and target")
        kind, target = step["kind"], step["target"]
        if not isinstance(kind, str) or kind not in ALLOWED_STEP_KINDS:
            raise PolicyViolation("step kind is not allowlisted")
        if not isinstance(target, str):
            raise PolicyViolation("step target must be a string")
        if kind == "inspect" and target not in ALLOWED_INSPECT_TARGETS:
            raise PolicyViolation("inspect target is not allowlisted")
        if kind == "run_test" and target not in ALLOWED_TEST_TARGETS:
            raise PolicyViolation("test target is not allowlisted")
        clean_steps.append({"kind": kind, "target": target})

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
