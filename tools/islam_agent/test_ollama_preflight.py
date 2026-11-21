import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from ollama_preflight import (
    DEFAULT_TAGS_ENDPOINT,
    OllamaPreflightError,
    inspect_local_ollama,
)


class OllamaPreflightTests(unittest.TestCase):
    def setUp(self):
        self.status = 200
        self.payload = {"models": [{"name": "qwen2.5:7b"}, {"name": "llama3.2:latest"}]}
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = json.dumps(owner.payload).encode("utf-8")
                self.send_response(owner.status)
                if owner.status == 302:
                    self.send_header("Location", "http://example.com/tags")
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f"http://127.0.0.1:{self.server.server_port}/api/tags"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def inspect(self, model="qwen2.5:7b"):
        # Tests inject a loopback test server; production accepts only the fixed endpoint.
        from unittest.mock import patch
        with patch("ollama_preflight.DEFAULT_TAGS_ENDPOINT", self.endpoint):
            return inspect_local_ollama(model, endpoint=self.endpoint, timeout=2)

    def test_exact_installed_model_is_available(self):
        result = self.inspect()
        self.assertTrue(result.available)
        self.assertEqual(result.requested_model, "qwen2.5:7b")
        self.assertEqual(result.installed_models, ("llama3.2:latest", "qwen2.5:7b"))

    def test_missing_model_is_reported_without_generation(self):
        result = self.inspect("missing:latest")
        self.assertFalse(result.available)

    def test_remote_endpoint_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "fixed local"):
            inspect_local_ollama("qwen2.5:7b", endpoint="http://example.com/api/tags")

    def test_invalid_models_payload_is_rejected(self):
        self.payload = {"models": [{"bad": "entry"}]}
        with self.assertRaisesRegex(OllamaPreflightError, "invalid model entry"):
            self.inspect()

    def test_invalid_json_is_rejected(self):
        self.payload = []
        with self.assertRaisesRegex(OllamaPreflightError, "missing the models list"):
            self.inspect()

    def test_http_error_is_bounded(self):
        self.status = 500
        with self.assertRaisesRegex(OllamaPreflightError, "HTTP status 500"):
            self.inspect()

    def test_redirect_is_not_followed(self):
        self.status = 302
        with self.assertRaisesRegex(OllamaPreflightError, "HTTP status 302"):
            self.inspect()

    def test_invalid_model_name_is_rejected(self):
        with self.assertRaises(ValueError):
            self.inspect(" ")


if __name__ == "__main__":
    unittest.main()
