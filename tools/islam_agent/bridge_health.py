#!/usr/bin/env python3
"""Loopback-only health endpoint for the ISLAM local assistant.

This first bridge milestone exposes health only. It is deliberately not a
phone/LAN service: the server binds IPv4 loopback and rejects browser Origins.
TLS pairing and all task/proposal endpoints remain disabled until separately
implemented and tested.
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
MAX_OLLAMA_RESPONSE_BYTES = 64 * 1024
OLLAMA_TIMEOUT_SECONDS = 1.5
DEFAULT_PORT = 8765


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def probe_ollama() -> bool:
    """Return availability only; never expose model names or response content."""
    request = Request(
        OLLAMA_TAGS_URL,
        headers={"Accept": "application/json"},
        method="GET",
    )
    opener = build_opener(ProxyHandler({}), _NoRedirectHandler())
    try:
        with opener.open(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_OLLAMA_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError):
        return False
    if len(raw) > MAX_OLLAMA_RESPONSE_BYTES:
        return False
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict) and isinstance(payload.get("models"), list)


def health_payload() -> dict:
    return {
        "api_version": "0.1",
        "bridge": "ready",
        "transport": "loopback_only",
        "orchestrator": "not_connected",
        "ollama": "available" if probe_ollama() else "unavailable",
        "phone_pairing": "disabled",
        "proposal_execution": "disabled",
    }


class _HealthHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ISLAMAgentBridge/0.1"
    sys_version = ""

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def _local_request_allowed(self) -> bool:
        host = self.headers.get("Host", "")
        try:
            hostname = urlsplit("//" + host).hostname
        except ValueError:
            hostname = None
        if hostname not in {"127.0.0.1", "localhost"}:
            self._send_json(400, {"error": {"code": "invalid_host"}})
            return False
        if self.headers.get("Origin"):
            self._send_json(403, {"error": {"code": "browser_origin_forbidden"}})
            return False
        return True

    def do_GET(self) -> None:
        if not self._local_request_allowed():
            return
        if self.path != "/v1/health":
            self._send_json(404, {"error": {"code": "not_found"}})
            return
        self._send_json(200, health_payload())

    def do_POST(self) -> None:
        self._send_json(405, {"error": {"code": "method_not_allowed"}})

    def do_PUT(self) -> None:
        self._send_json(405, {"error": {"code": "method_not_allowed"}})

    def do_DELETE(self) -> None:
        self._send_json(405, {"error": {"code": "method_not_allowed"}})

    def do_OPTIONS(self) -> None:
        self._send_json(405, {"error": {"code": "method_not_allowed"}})

    def log_message(self, *_args) -> None:
        # Avoid writing request data or headers into local logs.
        return


def create_server(port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("port must be an integer from 0 to 65535")
    server = ThreadingHTTPServer(("127.0.0.1", port), _HealthHandler)
    server.daemon_threads = True
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    try:
        server = create_server(args.port)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"ISLAM local health bridge: http://127.0.0.1:{server.server_port}/v1/health")
    print("Loopback only. Phone pairing, task APIs and proposal execution are disabled.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nISLAM local health bridge stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
