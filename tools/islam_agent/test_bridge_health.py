import json
import threading
import unittest
from http.client import HTTPConnection
from unittest.mock import patch

from bridge_health import create_server, health_payload, probe_ollama


class BridgeHealthTests(unittest.TestCase):
    def setUp(self):
        self.server = create_server(0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method="GET", path="/v1/health", headers=None, body=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=2)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        payload = response.read()
        status = response.status
        connection.close()
        return status, response.getheader("Content-Type"), payload

    def test_server_binds_ipv4_loopback_only(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    @patch("bridge_health.probe_ollama", return_value=True)
    def test_health_reports_available_without_leaking_model_details(self, _probe):
        status, content_type, raw = self.request()
        payload = json.loads(raw.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        self.assertEqual(payload["ollama"], "available")
        self.assertEqual(payload["bridge"], "ready")
        self.assertEqual(payload["orchestrator"], "not_connected")
        self.assertEqual(payload["phone_pairing"], "disabled")
        self.assertNotIn("models", payload)

    @patch("bridge_health.probe_ollama", return_value=False)
    def test_health_reports_ollama_unavailable(self, _probe):
        payload = json.loads(self.request()[2].decode("utf-8"))
        self.assertEqual(payload["ollama"], "unavailable")

    def test_unknown_paths_and_query_strings_are_rejected(self):
        self.assertEqual(self.request(path="/")[0], 404)
        self.assertEqual(self.request(path="/v1/health?debug=1")[0], 404)

    def test_mutating_methods_are_disabled(self):
        for method in ("POST", "PUT", "DELETE", "OPTIONS"):
            with self.subTest(method=method):
                self.assertEqual(self.request(method=method)[0], 405)

    def test_browser_origin_is_rejected(self):
        status, _content_type, raw = self.request(
            headers={"Origin": "http://example.test"}
        )
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(raw.decode("utf-8"))["error"]["code"],
                         "browser_origin_forbidden")

    def test_non_loopback_host_header_is_rejected(self):
        status, _content_type, raw = self.request(
            headers={"Host": "example.test"}
        )
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(raw.decode("utf-8"))["error"]["code"],
                         "invalid_host")

    def test_health_snapshot_explicitly_disables_unimplemented_features(self):
        with patch("bridge_health.probe_ollama", return_value=False):
            payload = health_payload()
        self.assertEqual(payload["transport"], "loopback_only")
        self.assertEqual(payload["proposal_execution"], "disabled")


if __name__ == "__main__":
    unittest.main()
