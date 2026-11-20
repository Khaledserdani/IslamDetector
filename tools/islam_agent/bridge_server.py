#!/usr/bin/env python3
"""TLS-only LAN bridge for ISLAM FREE AGENT.

Ollama remains on 127.0.0.1. The bridge exposes a private-LAN HTTPS endpoint,
one-time pairing, task listing, reviewed proposals, and explicit approve/reject.
It accepts only fixed allowlisted file writes and named tests; never shell commands.
"""
from __future__ import annotations

import argparse
from collections import deque
import hashlib
import hmac
import ipaddress
import json
import secrets
import ssl
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from agent_cycle import select_next_task
from orchestrator import DEFAULT_MEMORY, DEFAULT_PROPOSAL, LocalAgentOrchestrator
from task_queue import load_memory, transition, write_memory_atomic
from review_pending import review_pending, approval_phrase

MAX_BODY_BYTES = 80 * 1024
MAX_TASKS = 100
PAIR_WINDOW_SECONDS = 300
MAX_PAIR_ATTEMPTS = 5


class BridgeError(RuntimeError):
    def __init__(self, status: int, code: str, message_ar: str):
        super().__init__(message_ar)
        self.status, self.code, self.message_ar = status, code, message_ar


class BridgeApplication:
    def __init__(self, pairing_code: str, model: str,
                 memory_path: Path = DEFAULT_MEMORY,
                 proposal_path: Path = DEFAULT_PROPOSAL,
                 state_dir: Path | None = None):
        if not isinstance(pairing_code, str) or len(pairing_code) != 6 or not pairing_code.isdigit():
            raise ValueError("pairing_code must be six digits")
        if not isinstance(model, str) or not model.strip() or len(model) > 128:
            raise ValueError("model must be a bounded non-empty name")
        self._pair_hash = hashlib.sha256(pairing_code.encode("ascii")).digest()
        self._pair_expires = time.monotonic() + PAIR_WINDOW_SECONDS
        self._pair_attempts = 0
        self._session_hash: bytes | None = None
        self._session_token: str | None = None
        self._request_times = deque()
        self._lock = threading.RLock()
        self.model = model.strip()
        self.memory_path = Path(memory_path)
        self.proposal_path = Path(proposal_path)
        self.state_dir = Path(state_dir) if state_dir else self.proposal_path.parent / "review"
        self.orchestrator = None

    def pair(self, code: object) -> str:
        with self._lock:
            if self._session_hash is not None:
                raise BridgeError(409, "already_paired", "هذا الهاتف مقترن بالفعل")
            if time.monotonic() > self._pair_expires or self._pair_attempts >= MAX_PAIR_ATTEMPTS:
                raise BridgeError(410, "pairing_expired", "انتهت صلاحية رمز الاقتران")
            if not isinstance(code, str) or len(code) != 6 or not code.isdigit():
                self._pair_attempts += 1
                raise BridgeError(401, "invalid_pairing_code", "رمز الاقتران غير صحيح")
            candidate = hashlib.sha256(code.encode("ascii")).digest()
            if not hmac.compare_digest(candidate, self._pair_hash):
                self._pair_attempts += 1
                raise BridgeError(401, "invalid_pairing_code", "رمز الاقتران غير صحيح")
            token = secrets.token_urlsafe(32)
            self._session_token = token
            self._session_hash = hashlib.sha256(token.encode("ascii")).digest()
            self._pair_hash = b""
            return token

    def authorized(self, token: str | None) -> bool:
        if not isinstance(token, str) or not token:
            return False
        with self._lock:
            if self._session_hash is None:
                return False
            candidate = hashlib.sha256(token.encode("utf-8")).digest()
            return hmac.compare_digest(candidate, self._session_hash)

    def allow_request(self) -> bool:
        with self._lock:
            now = time.monotonic()
            while self._request_times and now - self._request_times[0] >= 60:
                self._request_times.popleft()
            if len(self._request_times) >= 60:
                return False
            self._request_times.append(now)
            return True

    def health(self) -> dict:
        from bridge_health import probe_ollama
        return {
            "api_version": "0.2",
            "bridge": "ready",
            "transport": "https_lan",
            "orchestrator": "available",
            "ollama": "available" if probe_ollama() else "unavailable",
            "model": self.model,
            "phone_pairing": "paired" if self._session_hash else "waiting",
            "proposal_execution": "human_approval_required",
        }

    def tasks(self) -> dict:
        memory = load_memory(self.memory_path)
        tasks = []
        for item in memory["next_tasks"][:MAX_TASKS]:
            tasks.append({
                "id": item["id"],
                "title": item["title"],
                "status": item["status"],
                "acceptance": item["acceptance"],
                "updated_at": item.get("updated_at"),
            })
        return {"tasks": tasks, "updated_at": memory.get("updated_at")}

    def create_proposal(self) -> dict:
        with self._lock:
            if self.proposal_path.exists():
                raise BridgeError(409, "proposal_already_pending", "يوجد اقتراح ينتظر المراجعة")
            try:
                from local_agent import LocalProposalAgent
                from local_workflow import LocalAgentWorkflow
                from ollama_client import LocalOllamaClient
                workflow = LocalAgentWorkflow(
                    LocalProposalAgent(LocalOllamaClient(model=self.model))
                )
                self.orchestrator = LocalAgentOrchestrator(workflow)
                result = self.orchestrator.run_once(self.memory_path, self.proposal_path)
            except Exception as exc:
                message = str(exc)[:300]
                code = "ollama_unavailable" if "Ollama" in type(exc).__name__ or "connect" in message.lower() else "proposal_failed"
                raise BridgeError(503, code, "تعذر إنشاء الاقتراح: " + message) from None
            if result.get("status") == "no_task":
                return {"status": "no_task"}
            record = json.loads(self.proposal_path.read_text(encoding="utf-8"))
            return {"status": "proposal_created", "proposal": self._public_proposal(record)}

    @staticmethod
    def _proposal_id(record: dict) -> str:
        canonical = json.dumps(
            {"task_id": record["task"]["id"], "proposal": record["proposal"]},
            ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()[:16]

    @classmethod
    def _public_proposal(cls, record: dict) -> dict:
        return {
            "proposal_id": cls._proposal_id(record),
            "task": record["task"],
            "model": record["model"],
            "proposal": record["proposal"],
            "awaiting_human_approval": record["awaiting_human_approval"],
            "executed": record["executed"],
        }

    def pending_proposal(self) -> dict:
        if not self.proposal_path.exists():
            return {"status": "none", "proposal": None}
        try:
            record = json.loads(self.proposal_path.read_text(encoding="utf-8"))
            return {"status": "pending", "proposal": self._public_proposal(record)}
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError):
            raise BridgeError(500, "pending_record_invalid", "سجل الاقتراح المعلق تالف") from None

    def decide(self, proposal_id: str, decision: object, confirmation_text: object = "") -> dict:
        with self._lock:
            pending = self.pending_proposal()
            if pending["status"] != "pending":
                raise BridgeError(404, "no_pending_proposal", "لا يوجد اقتراح معلق")
            record = json.loads(self.proposal_path.read_text(encoding="utf-8"))
            task_id = record["task"]["id"]
            digest = self._proposal_id(record)
            if proposal_id != digest:
                raise BridgeError(409, "proposal_stale", "معرّف الاقتراح لا يطابق الخطة الحالية")
            if decision == "reject":
                archive = self.proposal_path.parent / "decisions"
                archive.mkdir(parents=True, exist_ok=True)
                destination = archive / f"{digest}-rejected.json"
                if destination.exists():
                    raise BridgeError(409, "decision_already_recorded", "سبق تسجيل قرار لهذا الاقتراح")
                record["decision"] = "rejected"
                record["decided_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                destination.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                self.proposal_path.unlink()
                return {"status": "rejected", "executed": False}
            if decision != "approve":
                raise BridgeError(400, "invalid_decision", "القرار يجب أن يكون approve أو reject")
            if confirmation_text != approval_phrase(task_id):
                raise BridgeError(403, "approval_phrase_mismatch", "عبارة التأكيد غير مطابقة")
            memory = load_memory(self.memory_path)
            current = next((t for t in memory["next_tasks"] if t["id"] == task_id), None)
            if current is None or current["status"] not in {"pending", "in_progress"}:
                raise BridgeError(409, "proposal_stale", "المهمة لم تعد قابلة للتنفيذ")
            if current["title"] != record["task"]["title"] or current["acceptance"] != record["task"]["acceptance"]:
                raise BridgeError(409, "proposal_stale", "تغيرت بيانات المهمة بعد إنشاء الاقتراح")
            try:
                state, results = review_pending(
                    self.proposal_path,
                    approval_text=confirmation_text,
                    state_dir=self.state_dir,
                )
            except Exception as exc:
                raise BridgeError(422, "execution_rejected", str(exc)[:300]) from None
            if state.get("state") != "completed":
                return {
                    "status": state.get("state", "paused"),
                    "executed": False,
                    "completed_steps": state.get("completed_steps", []),
                    "results": results,
                    "proposal_remains_pending": True,
                }

            # Mark the project task complete only after every approved step passed.
            fresh_memory = load_memory(self.memory_path)
            fresh_task = next((t for t in fresh_memory["next_tasks"] if t["id"] == task_id), None)
            if fresh_task is None:
                raise BridgeError(409, "proposal_stale", "اختفت المهمة من ذاكرة المشروع")
            if fresh_task["status"] == "pending":
                transition(fresh_memory, task_id, "in_progress", "بدأ تنفيذ الاقتراح بعد موافقة المستخدم من الهاتف")
            if fresh_task["status"] in {"pending", "in_progress"}:
                transition(fresh_memory, task_id, "completed", "اكتملت جميع خطوات الاقتراح المعتمد من الهاتف")
            write_memory_atomic(self.memory_path, fresh_memory)

            archive = self.proposal_path.parent / "decisions"
            archive.mkdir(parents=True, exist_ok=True)
            destination = archive / f"{digest}-approved.json"
            if destination.exists():
                raise BridgeError(409, "decision_already_recorded", "سبق تسجيل قرار لهذا الاقتراح")
            record["decision"] = "approved"
            record["decided_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            record["execution_state"] = state.get("state")
            record["completed_steps"] = state.get("completed_steps", [])
            destination.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
            self.proposal_path.unlink(missing_ok=True)
            return {"status": "completed", "executed": True, "results": results}


def create_server(host: str, port: int, app: BridgeApplication,
                  certfile: Path, keyfile: Path, *, test_allow_loopback: bool = False) -> ThreadingHTTPServer:
    address = ipaddress.ip_address(host)
    allowed_address = address.version == 4 and address.is_private and not address.is_multicast
    if test_allow_loopback and address.is_loopback:
        allowed_address = True
    if not allowed_address:
        raise ValueError("host must be a private IPv4 address on the local network")
    valid_port = isinstance(port, int) and not isinstance(port, bool) and 1024 <= port <= 65535
    if test_allow_loopback and port == 0:
        valid_port = True
    if not valid_port:
        raise ValueError("port must be between 1024 and 65535")
    certfile, keyfile = Path(certfile), Path(keyfile)
    if not certfile.is_file() or not keyfile.is_file():
        raise ValueError("TLS certificate and private key files are required")

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "ISLAMAgentBridge/0.2"
        sys_version = ""

        def _send(self, status: int, payload: dict) -> None:
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

        def _error(self, error: BridgeError) -> None:
            self._send(error.status, {"error": {"code": error.code, "message_ar": error.message_ar}})

        def _valid_request(self) -> bool:
            if self.headers.get("Origin"):
                self._send(403, {"error": {"code": "browser_origin_forbidden"}})
                return False
            try:
                hostname = urlsplit("//" + self.headers.get("Host", "")).hostname
            except ValueError:
                hostname = None
            if hostname != host:
                self._send(400, {"error": {"code": "invalid_host"}})
                return False
            return True

        def _body(self) -> dict:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None or not raw_length.isdigit():
                raise BridgeError(411, "content_length_required", "حجم الطلب مطلوب")
            length = int(raw_length)
            if length > MAX_BODY_BYTES:
                raise BridgeError(413, "payload_too_large", "حجم الطلب أكبر من المسموح")
            raw = self.rfile.read(length)
            try:
                value = json.loads(raw.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError):
                raise BridgeError(400, "invalid_json", "بيانات JSON غير صالحة") from None
            if not isinstance(value, dict):
                raise BridgeError(400, "invalid_json", "يجب أن تكون البيانات كائناً")
            return value

        def _require_auth(self) -> bool:
            header = self.headers.get("Authorization", "")
            token = header[7:] if header.startswith("Bearer ") else None
            if not app.authorized(token):
                self._send(401, {"error": {"code": "unauthorized", "message_ar": "الجلسة غير صالحة أو غير مقترنة"}})
                return False
            if not app.allow_request():
                self._send(429, {"error": {"code": "rate_limited", "message_ar": "تم تجاوز عدد الطلبات المسموح"}})
                return False
            return True

        def do_GET(self):
            if not self._valid_request():
                return
            try:
                if self.path == "/v1/health":
                    self._send(200, app.health())
                    return
                if not self._require_auth():
                    return
                if self.path == "/v1/tasks":
                    self._send(200, app.tasks())
                elif self.path == "/v1/proposals/pending":
                    self._send(200, app.pending_proposal())
                else:
                    self._send(404, {"error": {"code": "not_found"}})
            except BridgeError as exc:
                self._error(exc)
            except Exception:
                self._send(500, {"error": {"code": "internal_error", "message_ar": "حدث خطأ داخلي"}})

        def do_POST(self):
            if not self._valid_request():
                return
            try:
                body = self._body()
                if self.path == "/v1/pair":
                    if set(body) != {"code"}:
                        raise BridgeError(400, "invalid_pair_request", "حقول طلب الاقتران غير صحيحة")
                    token = app.pair(body["code"])
                    self._send(200, {"session_token": token, "api_version": "0.2"})
                    return
                if not self._require_auth():
                    return
                if self.path == "/v1/proposals":
                    if body:
                        raise BridgeError(400, "invalid_proposal_request", "لا يقبل طلب الاقتراح حقولاً إضافية")
                    self._send(201, app.create_proposal())
                    return
                prefix = "/v1/proposals/"
                suffix = "/decision"
                if self.path.startswith(prefix) and self.path.endswith(suffix):
                    proposal_id = self.path[len(prefix):-len(suffix)]
                    if not proposal_id or "/" in proposal_id or set(body) != {"decision", "confirmation_text"}:
                        raise BridgeError(400, "invalid_decision_request", "بيانات القرار غير صحيحة")
                    self._send(200, app.decide(proposal_id, body["decision"], body["confirmation_text"]))
                    return
                self._send(404, {"error": {"code": "not_found"}})
            except BridgeError as exc:
                self._error(exc)
            except Exception:
                self._send(500, {"error": {"code": "internal_error", "message_ar": "حدث خطأ داخلي"}})

        def do_PUT(self):
            self._send(405, {"error": {"code": "method_not_allowed"}})

        def do_DELETE(self):
            self._send(405, {"error": {"code": "method_not_allowed"}})

        def do_OPTIONS(self):
            self._send(405, {"error": {"code": "method_not_allowed"}})

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=str(certfile), keyfile=str(keyfile))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.bridge_app = app
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="private LAN IPv4 address")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model", required=True, help="installed local Ollama model")
    parser.add_argument("--pair-code", required=True, help="six-digit one-time pairing code")
    parser.add_argument("--cert", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    args = parser.parse_args()
    try:
        app = BridgeApplication(args.pair_code, args.model)
        server = create_server(args.host, args.port, app, args.cert, args.key)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    cert_der = ssl.PEM_cert_to_DER_cert(args.cert.read_text(encoding="ascii"))
    fingerprint = hashlib.sha256(cert_der).hexdigest()
    print(f"ISLAM bridge: https://{args.host}:{server.server_port}", flush=True)
    print(f"Certificate SHA-256: {fingerprint}", flush=True)
    print(f"One-time pairing code (valid 5 minutes): {args.pair_code}", flush=True)
    print("Ollama stays bound to 127.0.0.1:11434. Do not expose this port on the router.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nISLAM bridge stopped.", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
