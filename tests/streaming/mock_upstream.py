#!/usr/bin/env python3
"""Mock 'responses' upstream that STREAMS SSE slowly, like the real relay.

It emits response.created immediately, then dribbles delta events with a gap
between each, and only sends response.completed at the very end. This is the
exact shape that made helm-x's old fixed max-time truncate the stream before
response.completed arrived.

Env:
  PORT           listen port (default 8099)
  STREAM_SECONDS total time to spread the events over (default 8)
  N_DELTAS       number of delta events (default 16)
"""
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8099"))
STREAM_SECONDS = float(os.environ.get("STREAM_SECONDS", "8"))
N_DELTAS = int(os.environ.get("N_DELTAS", "16"))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        try:
            self._stream()
        except (BrokenPipeError, ConnectionResetError):
            # Client (helm-x) closed early, e.g. Case A's ceiling truncation.
            pass

    def _stream(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length:
            self.rfile.read(length)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()

        def emit(obj_line):
            self.wfile.write(obj_line.encode())
            self.wfile.flush()

        emit('event: response.created\n'
             'data: {"type":"response.created","response":{"id":"resp_mock","status":"in_progress"}}\n\n')

        gap = STREAM_SECONDS / max(N_DELTAS, 1)
        for i in range(N_DELTAS):
            time.sleep(gap)
            emit('event: response.output_text.delta\n'
                 'data: {"type":"response.output_text.delta","delta":"tok%d "}\n\n' % i)

        emit('event: response.completed\n'
             'data: {"type":"response.completed","response":{"id":"resp_mock","status":"completed",'
             '"output":[{"type":"message","content":[{"type":"output_text","text":"done"}]}]}}\n\n')
        emit('data: [DONE]\n\n')


if __name__ == "__main__":
    print(f"[mock] streaming upstream on :{PORT} ({STREAM_SECONDS}s, {N_DELTAS} deltas)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
