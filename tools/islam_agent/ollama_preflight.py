#!/usr/bin/env python3
"""Safe local Ollama availability and model preflight; no model generation."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


DEFAULT_TAGS_ENDPOINT = "http://127.0.0.1:11434/api/tags"
MAX_TAGS_BYTES = 256 * 1024


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OllamaPreflightError(RuntimeError):
    """Safe, bounded preflight failure."""


@dataclass(frozen=True)
class PreflightResult:
    endpoint: str
    requested_model: str
    available: bool
    installed_models: tuple[str, ...]


def inspect_local_ollama(
    model: str,
    endpoint: str = DEFAULT_TAGS_ENDPOINT,
    timeout: float = 3.0,
    max_response_bytes: int = MAX_TAGS_BYTES,
) -> PreflightResult:
    if not isinstance(model, str) or not model.strip() or len(model) > 128:
        raise ValueError("model must be a non-empty name of at most 128 characters")
    if any(ord(char) < 32 for char in model):
        raise ValueError("model contains a control character")
    if endpoint != DEFAULT_TAGS_ENDPOINT:
        raise ValueError("preflight endpoint must be the fixed local Ollama tags endpoint")
    if not isinstance(timeout, (int, float)) or not 0.1 <= timeout <= 15:
        raise ValueError("timeout must be between 0.1 and 15 seconds")
    if not isinstance(max_response_bytes, int) or not 1024 <= max_response_bytes <= MAX_TAGS_BYTES:
        raise ValueError("max_response_bytes is outside the permitted range")

    request = Request(endpoint, headers={"Accept": "application/json"}, method="GET")
    try:
        opener = build_opener(ProxyHandler({}), _NoRedirectHandler())
        with opener.open(request, timeout=float(timeout)) as response:
            raw = response.read(max_response_bytes + 1)
    except HTTPError as exc:
        raise OllamaPreflightError(f"Ollama returned HTTP status {exc.code}") from None
    except (URLError, TimeoutError, OSError):
        raise OllamaPreflightError(
            "Cannot reach local Ollama at 127.0.0.1:11434; start Ollama on this device"
        ) from None

    if len(raw) > max_response_bytes:
        raise OllamaPreflightError("Ollama tags response exceeded the configured size limit")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise OllamaPreflightError("Ollama tags endpoint returned invalid JSON") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
        raise OllamaPreflightError("Ollama tags response is missing the models list")

    names = []
    for item in payload["models"]:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise OllamaPreflightError("Ollama tags response contains an invalid model entry")
        name = item["name"]
        if not name or len(name) > 256 or any(ord(char) < 32 for char in name):
            raise OllamaPreflightError("Ollama tags response contains an invalid model name")
        names.append(name)

    requested = model.strip()
    return PreflightResult(
        endpoint=endpoint,
        requested_model=requested,
        available=requested in names,
        installed_models=tuple(sorted(set(names))),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="exact installed Ollama model name")
    args = parser.parse_args()
    try:
        result = inspect_local_ollama(args.model)
        print(json.dumps({
            "status": "ready" if result.available else "model_missing",
            "endpoint": result.endpoint,
            "requested_model": result.requested_model,
            "available": result.available,
            "installed_models": list(result.installed_models),
            "generation_performed": False,
            "executed": False,
        }, ensure_ascii=False, sort_keys=True))
        return 0 if result.available else 2
    except Exception as exc:
        print(json.dumps({
            "status": "error",
            "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            "generation_performed": False,
            "executed": False,
        }, ensure_ascii=False, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
