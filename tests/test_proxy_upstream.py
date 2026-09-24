"""Local WinHTTP proxy regression tests; run after building build/helmx.exe."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener


EXE = Path(__file__).resolve().parents[1] / "build" / "helmx.exe"


class ProxyUpstreamTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32" and EXE.exists(), "requires built Windows helmx.exe")
    def test_policy_response_followed_by_bad_request_is_not_fork_pass(self):
        self.assert_proxy_responses(
            [(403, {"error": {"code": "cyber_policy", "message": "blocked"}}),
             (400, {"error": {"code": "invalid_request", "message": "bad request"}})],
            expected_status=403, expected_calls=2, log_marker="result: fork_fail",
            expected_message="blocked",
        )

    @unittest.skipUnless(sys.platform == "win32" and EXE.exists(), "requires built Windows helmx.exe")
    def test_bad_request_is_not_retried(self):
        self.assert_proxy_responses(
            [(400, {"error": {"code": "invalid_request", "message": "bad request"}})],
            expected_status=400, expected_calls=1, log_marker=None,
        )

    @unittest.skipUnless(sys.platform == "win32" and EXE.exists(), "requires built Windows helmx.exe")
    def test_stream_is_forwarded_with_sse_content_type(self):
        stream = 'event: response.created\ndata: {"type":"response.created"}\n\n' \
                 'event: response.completed\ndata: {"type":"response.completed"}\n\n'
        self.assert_proxy_responses(
            [(200, stream)], expected_status=200, expected_calls=1,
            log_marker=None, stream=True,
        )

    @unittest.skipUnless(sys.platform == "win32" and EXE.exists(), "requires built Windows helmx.exe")
    def test_sse_error_is_not_converted_to_synthetic_403(self):
        stream = 'event: response.created\ndata: {"type":"response.created"}\n\n' \
                 'event: error\ndata: {"type":"error","error":{"code":"cyber_policy"}}\n\n'
        self.assert_proxy_responses(
            [(200, stream)], expected_status=200, expected_calls=1,
            log_marker=None, stream=True,
        )

    @unittest.skipUnless(sys.platform == "win32" and EXE.exists(), "requires built Windows helmx.exe")
    def test_stream_with_bom_and_comment_uses_sse_content_type(self):
        stream = '\ufeff: keep-alive\n\nevent: response.created\ndata: {}\n\n' \
                 'event: response.completed\ndata: {}\n\n'
        self.assert_proxy_responses(
            [(200, stream)], expected_status=200, expected_calls=1,
            log_marker=None, stream=True,
        )

    @unittest.skipUnless(sys.platform == "win32" and EXE.exists(), "requires built Windows helmx.exe")
    def test_completed_response_quoting_policy_text_is_not_403(self):
        completed = {"status": "completed", "output": [{"type": "message", "role": "assistant",
            "content": [{"type": "output_text", "text": "The word cyber_policy is in the docs."}]}]}
        self.assert_proxy_responses(
            [(200, completed)], expected_status=200, expected_calls=1, log_marker=None,
        )

    @unittest.skipUnless(sys.platform == "win32" and EXE.exists(), "requires built Windows helmx.exe")
    def test_passthrough_keeps_real_policy_response_and_request(self):
        self.assert_proxy_responses(
            [(403, {"error": {"code": "cyber_policy", "message": "actual upstream denial"}})],
            expected_status=403, expected_calls=1, log_marker=None,
            expected_message="actual upstream denial", passthrough=True,
        )

    def assert_proxy_responses(self, responses, expected_status, expected_calls, log_marker,
                               stream=False, expected_message=None, passthrough=False):
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                raw = self.rfile.read(int(self.headers["Content-Length"]))
                received.append(json.loads(raw))
                status, data = responses[min(len(received) - 1, len(responses) - 1)]
                body = (data if isinstance(data, str) else json.dumps(data)).encode()
                self.send_response(status)
                self.send_header("Content-Type", "text/event-stream" if isinstance(data, str) else "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        with tempfile.TemporaryDirectory() as temp, ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            root = Path(temp)
            codex_home = root / "codex-home"
            codex_home.mkdir()
            (codex_home / "config.toml").write_text(
                'model_provider = "custom"\n[model_providers.custom]\n'
                f'base_url = "http://127.0.0.1:{server.server_port}/v1"\n', encoding="utf-8"
            )
            (root / "helmx.config.json").write_text('{"enabled":false}', encoding="utf-8")
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                proxy_port = sock.getsockname()[1]
            env = os.environ.copy()
            env.update(CODEX_HOME=str(codex_home), USERPROFILE=temp, APPDATA=temp)
            proc = subprocess.Popen(
                [str(EXE), "proxy", "--listen", str(proxy_port),
                 "--upstream", f"http://127.0.0.1:{server.server_port}/v1",
                 "--max-retries", "1", "--retry-delay", "1"] +
                (["--passthrough"] if passthrough else []),
                env=env, cwd=temp, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            try:
                deadline = time.monotonic() + 10
                while True:
                    if proc.poll() is not None:
                        self.fail(f"proxy exited unexpectedly ({proc.returncode})")
                    try:
                        with socket.create_connection(("127.0.0.1", proxy_port), timeout=0.2):
                            break
                    except OSError:
                        if time.monotonic() > deadline:
                            self.fail("proxy did not start")
                        time.sleep(0.05)
                opener = build_opener(ProxyHandler({}))
                payload = json.dumps({
                    "model": "test-model", "stream": stream,
                    "input": [{"type": "message", "role": "user",
                               "content": [{"type": "input_text", "text": "hello"}]}],
                }, separators=(",", ":")).encode()
                request = Request(f"http://127.0.0.1:{proxy_port}/v1/responses", payload,
                                  {"Content-Type": "application/json"})
                if expected_status < 400:
                    with opener.open(request, timeout=10) as reply:
                        self.assertEqual(reply.status, expected_status)
                        if stream:
                            self.assertTrue(reply.headers["Content-Type"].startswith("text/event-stream"))
                            self.assertEqual(reply.read().decode(), responses[0][1])
                        else:
                            self.assertEqual(json.loads(reply.read()), responses[0][1])
                    if stream:
                        self.assertIs(received[0]["stream"], True)
                else:
                    with self.assertRaises(HTTPError) as caught:
                        opener.open(request, timeout=10)
                    with caught.exception as error:
                        self.assertEqual(error.code, expected_status)
                        data = json.loads(error.read())
                        self.assertIn("error", data)
                        if expected_message:
                            self.assertEqual(data["error"]["message"], expected_message)
                if passthrough:
                    self.assertEqual(len(received[0]["input"]), 1)
                    self.assertEqual(received[0]["input"][0]["role"], "user")
                self.assertEqual(len(received), expected_calls)
                if log_marker:
                    self.assertIn(log_marker, (codex_home / "helmx-cyber.log").read_text(encoding="utf-8"))
                    self.assertIn("clean-session request failed: HTTP 400",
                                  (codex_home / "helmx.log").read_text(encoding="utf-8"))
            finally:
                proc.terminate()
                proc.wait(timeout=5)
                server.shutdown()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
