import json
import http.client
import ssl
import subprocess
import threading
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from bridge_server import BridgeApplication, BridgeError, create_server
from review_pending import approval_phrase


def memory_fixture(path, status="pending"):
    path.write_text(json.dumps({
        "schema_version": 1,
        "project": "bridge-test",
        "updated_at": "2026-11-20",
        "known_constraints": [],
        "next_tasks": [{
            "id": "agent-011",
            "title": "Implement secure bridge",
            "acceptance": "Phone pairs securely and requests a proposal",
            "status": status,
        }],
    }), encoding="utf-8")


def proposal_record():
    return {
        "schema_version": 1,
        "created_at_utc": "2026-11-20T10:00:00+00:00",
        "task": {
            "id": "agent-011",
            "title": "Implement secure bridge",
            "acceptance": "Phone pairs securely and requests a proposal",
            "status": "pending",
        },
        "model": "local-test-model",
        "proposal": {
            "task_id": "agent-011",
            "summary_ar": "فحص آمن",
            "steps": [{"kind": "run_test", "target": "agent_unit_tests"}],
            "needs_human_approval": True,
            "claims_to_verify": [],
        },
        "awaiting_human_approval": True,
        "executed": False,
    }


class BridgeServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.memory = self.root / "memory.json"
        self.pending = self.root / "pending.json"
        memory_fixture(self.memory)
        self.app = BridgeApplication(
            "123456", "local-test-model",
            memory_path=self.memory,
            proposal_path=self.pending,
            state_dir=self.root / "state",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_pairing_issues_single_random_session_token(self):
        token = self.app.pair("123456")
        self.assertGreaterEqual(len(token), 32)
        self.assertTrue(self.app.authorized(token))
        self.assertFalse(self.app.authorized("wrong-token"))
        with self.assertRaises(BridgeError) as caught:
            self.app.pair("123456")
        self.assertEqual(caught.exception.code, "already_paired")

    def test_invalid_pairing_attempts_are_bounded(self):
        for _ in range(5):
            with self.assertRaises(BridgeError):
                self.app.pair("000000")
        with self.assertRaises(BridgeError) as caught:
            self.app.pair("123456")
        self.assertEqual(caught.exception.code, "pairing_expired")

    def test_pairing_code_expires(self):
        self.app._pair_expires = time.monotonic() - 1
        with self.assertRaises(BridgeError) as caught:
            self.app.pair("123456")
        self.assertEqual(caught.exception.code, "pairing_expired")


    def test_authenticated_requests_are_rate_limited(self):
        for _ in range(60):
            self.assertTrue(self.app.allow_request())
        self.assertFalse(self.app.allow_request())

    def test_continuous_worker_is_bounded_and_stoppable(self):
        with self.assertRaisesRegex(ValueError, "between 300"):
            self.app.start_continuous_worker(299)
        self.app.start_continuous_worker(300)
        self.assertEqual(self.app.health()["continuous_worker"], "running")
        self.app.stop_continuous_worker()
        self.assertEqual(self.app.health()["continuous_worker"], "stopped")

    def test_task_listing_is_read_only_and_bounded(self):
        payload = self.app.tasks()
        self.assertEqual(len(payload["tasks"]), 1)
        self.assertEqual(payload["tasks"][0]["id"], "agent-011")
        self.assertEqual(self.app.tasks()["tasks"][0]["status"], "pending")

    def test_health_does_not_claim_pairing_or_ollama_without_evidence(self):
        with patch("bridge_health.probe_ollama", return_value=False):
            health = self.app.health()
        self.assertEqual(health["transport"], "https_lan")
        self.assertEqual(health["ollama"], "unavailable")
        self.assertEqual(health["phone_pairing"], "waiting")
        self.assertEqual(health["proposal_execution"], "human_approval_required")

    def test_proposal_identifier_is_stable_and_bound_to_plan(self):
        record = proposal_record()
        first = self.app._proposal_id(record)
        self.assertEqual(first, self.app._proposal_id(record))
        record["proposal"]["summary_ar"] = "خطة مختلفة"
        self.assertNotEqual(first, self.app._proposal_id(record))

    def test_reject_decision_archives_and_removes_pending_proposal(self):
        record = proposal_record()
        self.pending.write_text(json.dumps(record), encoding="utf-8")
        proposal_id = self.app._proposal_id(record)
        result = self.app.decide(proposal_id, "reject")
        self.assertEqual(result, {"status": "rejected", "executed": False})
        self.assertFalse(self.pending.exists())
        archived = self.root / "decisions" / f"{proposal_id}-rejected.json"
        self.assertTrue(archived.is_file())
        self.assertEqual(json.loads(archived.read_text(encoding="utf-8"))["decision"], "rejected")

    def test_wrong_approval_phrase_never_calls_executor(self):
        record = proposal_record()
        self.pending.write_text(json.dumps(record), encoding="utf-8")
        with patch("bridge_server.review_pending") as executor:
            with self.assertRaises(BridgeError) as caught:
                self.app.decide(self.app._proposal_id(record), "approve", "نعم")
            self.assertEqual(caught.exception.code, "approval_phrase_mismatch")
        executor.assert_not_called()
        self.assertTrue(self.pending.exists())

    def test_approval_requires_current_task_to_match_pending_record(self):
        record = proposal_record()
        self.pending.write_text(json.dumps(record), encoding="utf-8")
        memory_fixture(self.memory, status="completed")
        with patch("bridge_server.review_pending") as executor:
            with self.assertRaises(BridgeError) as caught:
                self.app.decide(
                    self.app._proposal_id(record), "approve",
                    approval_phrase("agent-011"),
                )
            self.assertEqual(caught.exception.code, "proposal_stale")
        executor.assert_not_called()

    def test_continuous_worker_waits_for_github_upload_ack(self):
        record = proposal_record()
        record["proposal"]["steps"] = [{
            "kind": "write_file",
            "target": "docs/agent/agent_worklog.md",
            "content": "# approved\\n",
        }]
        self.pending.write_text(json.dumps(record), encoding="utf-8")
        proposal_id = self.app._proposal_id(record)
        with patch("bridge_server.review_pending", return_value=(
            {"state": "completed", "completed_steps": ["001:write_file:docs/agent/agent_worklog.md"]},
            [{"kind": "write_file", "status": "written"}],
        )):
            result = self.app.decide(
                proposal_id, "approve", approval_phrase("agent-011")
            )
        self.assertEqual(result["status"], "completed")
        self.assertTrue(self.app.upload_pending_path.is_file())
        self.assertTrue(self.app.health()["github_upload_pending"])
        with self.assertRaises(BridgeError) as caught:
            self.app.create_proposal()
        self.assertEqual(caught.exception.code, "github_upload_pending")
        with self.assertRaises(BridgeError) as mismatch:
            self.app.complete_github_upload(proposal_id, ["wrong/path"])
        self.assertEqual(mismatch.exception.code, "upload_file_list_mismatch")
        ack = self.app.complete_github_upload(
            proposal_id, ["docs/agent/agent_worklog.md"]
        )
        self.assertEqual(ack["status"], "upload_confirmed")
        self.assertFalse(self.app.upload_pending_path.exists())
        self.assertFalse(self.app.health()["github_upload_pending"])

    def test_approval_calls_fixed_review_gate_only_after_explicit_phrase(self):
        record = proposal_record()
        self.pending.write_text(json.dumps(record), encoding="utf-8")
        with patch("bridge_server.review_pending", return_value=(
            {"state": "completed", "completed_steps": ["001:run_test:agent_unit_tests"]},
            [{"kind": "run_test", "status": "passed"}],
        )) as executor:
            result = self.app.decide(
                self.app._proposal_id(record), "approve",
                approval_phrase("agent-011"),
            )
        executor.assert_called_once()
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["executed"])
        self.assertFalse(self.pending.exists())
        updated_memory = json.loads(self.memory.read_text(encoding="utf-8"))
        self.assertEqual(updated_memory["next_tasks"][0]["status"], "completed")


    def test_https_transport_pairs_and_authenticates_phone(self):
        openssl = __import__("shutil").which("openssl")
        if not openssl:
            self.skipTest("OpenSSL is not available")
        cert = self.root / "server.crt"
        key = self.root / "server.key"
        subprocess.run([
            openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(key), "-out", str(cert), "-subj", "/CN=127.0.0.1",
            "-addext", "subjectAltName=IP:127.0.0.1", "-days", "1",
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        server = create_server(
            "127.0.0.1", 0, self.app, cert, key, test_allow_loopback=True
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            context = ssl._create_unverified_context()
            connection = http.client.HTTPSConnection(
                "127.0.0.1", server.server_port, context=context, timeout=3
            )
            connection.request("GET", "/v1/tasks")
            unauthorized = connection.getresponse()
            self.assertEqual(unauthorized.status, 401)
            unauthorized.read()

            body = json.dumps({"code": "123456"})
            connection.request(
                "POST", "/v1/pair", body=body,
                headers={"Content-Type": "application/json"},
            )
            paired = connection.getresponse()
            self.assertEqual(paired.status, 200)
            token = json.loads(paired.read().decode("utf-8"))["session_token"]

            connection.request(
                "GET", "/v1/tasks",
                headers={"Authorization": "Bearer " + token},
            )
            authorized = connection.getresponse()
            self.assertEqual(authorized.status, 200)
            payload = json.loads(authorized.read().decode("utf-8"))
            self.assertEqual(payload["tasks"][0]["id"], "agent-011")
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_accepts_tailscale_overlay_address(self):
        import ipaddress
        from bridge_server import is_allowed_bridge_ipv4
        self.assertTrue(is_allowed_bridge_ipv4(ipaddress.ip_address("100.100.20.30")))

    def test_refuses_addresses_outside_lan_and_tailscale_ranges(self):
        import ipaddress
        from bridge_server import is_allowed_bridge_ipv4
        for value in ("8.8.8.8", "100.63.255.255", "100.128.0.1", "127.0.0.1"):
            self.assertFalse(is_allowed_bridge_ipv4(ipaddress.ip_address(value)))

    def test_refuses_public_network_bind_address(self):
        with self.assertRaisesRegex(ValueError, "RFC1918"):
            create_server("8.8.8.8", 8765, self.app, self.root / "cert.pem", self.root / "key.pem")

    def test_refuses_invalid_port(self):
        with self.assertRaisesRegex(ValueError, "port"):
            create_server("192.168.1.10", 80, self.app, self.root / "cert.pem", self.root / "key.pem")

    def test_refuses_missing_tls_files(self):
        with self.assertRaisesRegex(ValueError, "TLS certificate"):
            create_server("192.168.1.10", 8765, self.app, self.root / "cert.pem", self.root / "key.pem")


if __name__ == "__main__":
    unittest.main()
