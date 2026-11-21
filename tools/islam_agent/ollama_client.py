#!/usr/bin/env python3
"""Strict local-only Ollama JSON client. No tools, shell, or remote endpoints."""
from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


DEFAULT_ENDPOINT = "http://127.0.0.1:11434/api/chat"
MAX_PROMPT_CHARS = 16_000
MAX_RESPONSE_BYTES = 1_000_000


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OllamaClientError(RuntimeError):
    """Safe, user-facing error for local Ollama communication."""


@dataclass(frozen=True)
class OllamaReply:
    model: str
    content: dict
    done: bool


class LocalOllamaClient:
    """Call only an HTTP Ollama endpoint bound to IPv4 loopback."""

    def __init__(
        self,
        model: str,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 30.0,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
    ) -> None:
        if not isinstance(model, str) or not model.strip() or len(model) > 128:
            raise ValueError("model must be a non-empty name of at most 128 characters")
        if any(ord(char) < 32 for char in model):
            raise ValueError("model contains a control character")
        if not isinstance(timeout, (int, float)) or not 0.1 <= timeout <= 120:
            raise ValueError("timeout must be between 0.1 and 120 seconds")
        if not isinstance(max_response_bytes, int) or not 1024 <= max_response_bytes <= MAX_RESPONSE_BYTES:
            raise ValueError("max_response_bytes is outside the permitted range")
        self.model = model.strip()
        self.endpoint = self._validate_endpoint(endpoint)
        self.timeout = float(timeout)
        self.max_response_bytes = max_response_bytes

    @staticmethod
    def _validate_endpoint(endpoint: str) -> str:
        if not isinstance(endpoint, str):
            raise ValueError("endpoint must be a URL string")
        try:
            parsed = urlsplit(endpoint)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("invalid local Ollama endpoint") from exc
        if (
            parsed.scheme != "http"
            or parsed.hostname != "127.0.0.1"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path != "/api/chat"
            or parsed.query
            or parsed.fragment
            or (port is not None and not 1 <= port <= 65535)
        ):
            raise ValueError("Ollama endpoint must be http://127.0.0.1[:port]/api/chat")
        return endpoint

    @staticmethod
    def _validate_messages(messages: list[dict]) -> list[dict]:
        if not isinstance(messages, list) or not 1 <= len(messages) <= 16:
            raise ValueError("messages must contain between 1 and 16 entries")
        clean = []
        has_user = False
        for item in messages:
            if not isinstance(item, dict) or set(item) != {"role", "content"}:
                raise ValueError("each message must contain only role and content")
            role, content = item["role"], item["content"]
            if not isinstance(role, str) or role not in {"system", "user", "assistant"}:
                raise ValueError("unsupported message role")
            if not isinstance(content, str) or not content.strip() or len(content) > MAX_PROMPT_CHARS:
                raise ValueError("message content is empty or exceeds the size limit")
            has_user = has_user or role == "user"
            clean.append({"role": role, "content": content})
        if not has_user:
            raise ValueError("at least one user message is required")
        return clean

    def chat_json(self, messages: list[dict]) -> OllamaReply:
        clean_messages = self._validate_messages(messages)
        payload = {
            "model": self.model,
            "messages": clean_messages,
            "stream": False,
            "format": "json",
        }
        request = Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            opener = build_opener(ProxyHandler({}), _NoRedirectHandler())
            with opener.open(request, timeout=self.timeout) as response:
                raw = response.read(self.max_response_bytes + 1)
        except HTTPError as exc:
            raise OllamaClientError(f"Ollama returned HTTP status {exc.code}") from None
        except (URLError, TimeoutError, OSError) as exc:
            raise OllamaClientError("Cannot reach local Ollama; verify that it is running on this device") from None

        if len(raw) > self.max_response_bytes:
            raise OllamaClientError("Ollama response exceeded the configured size limit")
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise OllamaClientError("Ollama returned an invalid JSON response") from None
        if not isinstance(envelope, dict):
            raise OllamaClientError("Ollama response must be a JSON object")
        message = envelope.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise OllamaClientError("Ollama response is missing message.content")
        if not isinstance(envelope.get("done"), bool):
            raise OllamaClientError("Ollama response is missing a boolean done field")
        try:
            content = json.loads(message["content"])
        except json.JSONDecodeError:
            raise OllamaClientError("Model content is not valid JSON") from None
        if not isinstance(content, dict):
            raise OllamaClientError("Model content must be a JSON object")
        return OllamaReply(
            model=str(envelope.get("model", self.model)),
            content=content,
            done=envelope["done"],
        )
