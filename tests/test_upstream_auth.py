"""helm-x 单元测试 — 代理层补齐上游凭据

codex 0.149.0 起，自定义 model provider 不再继承 auth.json 的凭据，请求到达
代理时没有 Authorization 头，上游中转直接返回 401 {"error":"Missing API key"}。
代理必须自己从 codex 配置里解析出同一份凭据并补上。

用法：python -m unittest test_upstream_auth -v
"""
import json
import os
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

HELMX = Path(os.environ.get(
    "HELMX_TEST_BIN", Path(__file__).resolve().parents[1] / "build" / "helmx"
))


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class RecordingUpstream:
    """Minimal /v1/responses upstream that records the headers it was sent."""

    def __init__(self):
        self.requests = []
        self.port = free_port()
        recorder = self.requests

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                if length:
                    self.rfile.read(length)
                recorder.append({k.lower(): v for k, v in self.headers.items()})
                payload = json.dumps({
                    "id": "resp_mock",
                    "status": "completed",
                    "output": [{
                        "type": "message",
                        "content": [{"type": "output_text", "text": "ok"}],
                    }],
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)

    def __enter__(self):
        Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


class TestUpstreamAuth(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="helmx-auth-test-")
        self.codex_home = Path(self.tmp) / ".codex"
        self.codex_home.mkdir()
        self.cfg = self.codex_home / "config.toml"
        self.write_config()

    def write_config(self, provider_extra=""):
        self.cfg.write_text(
            'model_provider = "custom"\n'
            'model = "gpt-5.6-terra"\n\n'
            '[model_providers.custom]\n'
            'name = "test"\n'
            'base_url = "https://example.com/v1"\n'
            'wire_api = "responses"\n' + provider_extra,
            encoding="utf-8",
        )

    def write_auth_json(self, payload):
        (self.codex_home / "auth.json").write_text(json.dumps(payload), encoding="utf-8")

    def post(self, port, headers=None):
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/responses",
            data=json.dumps({
                "model": "gpt-5.6-terra",
                "input": [{
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hi"}],
                }],
            }).encode(),
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:  # body still carries the proxy reply
            return e.read()

    def send(self, headers=None, env=None):
        """Run one request through the proxy; return the headers upstream saw."""
        with RecordingUpstream() as upstream:
            port = free_port()
            proc = subprocess.Popen(
                [str(HELMX), "proxy", "--listen", str(port),
                 "--upstream", f"http://127.0.0.1:{upstream.port}/v1"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=self.tmp,
                env={**os.environ, "CODEX_HOME": str(self.codex_home), **(env or {})},
            )
            try:
                deadline = time.time() + 10
                while time.time() < deadline:
                    with socket.socket() as s:
                        if s.connect_ex(("127.0.0.1", port)) == 0:
                            break
                    time.sleep(0.1)
                else:
                    self.fail("proxy did not start listening")
                self.post(port, headers)
            finally:
                proc.terminate()
                try:
                    proc.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate()
            self.assertEqual(len(upstream.requests), 1, "upstream saw no request")
            return upstream.requests[0]

    def test_api_key_from_provider_table(self):
        self.write_config('api_key = "sk-from-config"\n')
        self.assertEqual(self.send().get("authorization"), "Bearer sk-from-config")

    def test_experimental_bearer_token_from_provider_table(self):
        self.write_config('experimental_bearer_token = "sk-experimental"\n')
        self.assertEqual(self.send().get("authorization"), "Bearer sk-experimental")

    def test_env_key_from_provider_table(self):
        self.write_config('env_key = "HELMX_TEST_RELAY_KEY"\n')
        sent = self.send(env={"HELMX_TEST_RELAY_KEY": "sk-from-env"})
        self.assertEqual(sent.get("authorization"), "Bearer sk-from-env")

    def test_api_key_used_when_env_key_var_is_unset(self):
        self.write_config('env_key = "HELMX_TEST_MISSING_KEY"\napi_key = "sk-from-config"\n')
        os.environ.pop("HELMX_TEST_MISSING_KEY", None)
        self.assertEqual(self.send().get("authorization"), "Bearer sk-from-config")

    def test_api_key_from_auth_json(self):
        self.write_auth_json({"OPENAI_API_KEY": "sk-from-auth-json", "tokens": None})
        self.assertEqual(self.send().get("authorization"), "Bearer sk-from-auth-json")

    def test_access_token_from_auth_json_carries_account_id(self):
        self.write_auth_json({
            "OPENAI_API_KEY": None,
            "tokens": {"access_token": "chatgpt-access-token", "account_id": "acct-123"},
        })
        sent = self.send()
        self.assertEqual(sent.get("authorization"), "Bearer chatgpt-access-token")
        self.assertEqual(sent.get("chatgpt-account-id"), "acct-123")

    def test_config_key_wins_over_auth_json(self):
        self.write_config('api_key = "sk-from-config"\n')
        self.write_auth_json({"OPENAI_API_KEY": "sk-from-auth-json"})
        self.assertEqual(self.send().get("authorization"), "Bearer sk-from-config")

    def test_client_authorization_is_not_overridden(self):
        self.write_config('api_key = "sk-from-config"\n')
        sent = self.send(headers={"Authorization": "Bearer sk-from-codex"})
        self.assertEqual(sent.get("authorization"), "Bearer sk-from-codex")
        self.assertIsNone(sent.get("chatgpt-account-id"))

    def test_bearer_prefix_is_not_doubled(self):
        self.write_config('api_key = "Bearer sk-already-prefixed"\n')
        self.assertEqual(self.send().get("authorization"), "Bearer sk-already-prefixed")

    def test_no_credential_leaves_request_unauthenticated(self):
        sent = self.send()
        self.assertIsNone(sent.get("authorization"))


if __name__ == "__main__":
    unittest.main()
