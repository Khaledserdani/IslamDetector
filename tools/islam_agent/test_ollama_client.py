import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from ollama_client import LocalOllamaClient, OllamaClientError


class OllamaClientTests(unittest.TestCase):
    def setUp(self):
        self.response_status = 200
        self.response_body = {
            "model": "test-model",
            "message": {"content": json.dumps({"task_id": "agent-003", "steps": []})},
            "done": True,
        }
        self.request_payload = None
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                owner.request_payload = json.loads(self.rfile.read(length).decode("utf-8"))
                body = json.dumps(owner.response_body).encode("utf-8")
                self.send_response(owner.response_status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f"http://127.0.0.1:{self.server.server_port}/api/chat"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def client(self):
        return LocalOllamaClient("test-model", endpoint=self.endpoint, timeout=2)

    def test_valid_json_reply_and_non_streaming_request(self):
        reply = self.client().chat_json([{"role": "user", "content": "Plan one safe task"}])
        self.assertEqual(reply.content["task_id"], "agent-003")
        self.assertTrue(reply.done)
        self.assertFalse(self.request_payload["stream"])
        self.assertEqual(self.request_payload["format"], "json")

    def test_remote_endpoint_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "127.0.0.1"):
            LocalOllamaClient("test-model", endpoint="http://example.com/api/chat")

    def test_tool_role_is_rejected_before_request(self):
        with self.assertRaisesRegex(ValueError, "role"):
            self.client().chat_json([{"role": "tool", "content": "run command"}])
        self.assertIsNone(self.request_payload)

    def test_model_content_must_be_json_object(self):
        self.response_body["message"]["content"] = "not json"
        with self.assertRaisesRegex(OllamaClientError, "not valid JSON"):
            self.client().chat_json([{"role": "user", "content": "hello"}])

    def test_non_object_model_content_is_rejected(self):
        self.response_body["message"]["content"] = "[]"
        with self.assertRaisesRegex(OllamaClientError, "JSON object"):
            self.client().chat_json([{"role": "user", "content": "hello"}])

    def test_http_error_is_reported_without_response_body(self):
        self.response_status = 500
        with self.assertRaisesRegex(OllamaClientError, "HTTP status 500"):
            self.client().chat_json([{"role": "user", "content": "hello"}])

    def test_message_extra_fields_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "only role and content"):
            self.client().chat_json([{"role": "user", "content": "hello", "tools": []}])


if __name__ == "__main__":
    unittest.main()
