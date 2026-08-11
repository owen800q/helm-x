#!/usr/bin/env bash
# Verifies the streaming-timeout fix end to end against a mock SSE upstream.
#
#   Case A (regression): a low ABSOLUTE ceiling truncates the stream — this is
#     the old fixed-wall behaviour that broke codex (no response.completed).
#   Case B (fix): a normal ceiling + idle-based abort lets the slow-but-
#     still-streaming response finish, so response.completed reaches the client.
#
# The mock streams 16 deltas over 8s (0.5s gaps). No gap exceeds the idle
# window, so Case B must complete; Case A's 3s ceiling must cut it off.
set -u

HELMX=/app/build/helmx
MOCK_PORT=8099
PROXY_PORT=1800

fail() { echo "FAIL: $1"; exit 1; }

python3 /app/tests/streaming/mock_upstream.py &
MOCK_PID=$!
trap 'kill $MOCK_PID 2>/dev/null' EXIT
sleep 1

start_proxy() {
  "$HELMX" proxy --listen "$PROXY_PORT" --upstream "http://127.0.0.1:${MOCK_PORT}/v1" \
    >/tmp/proxy.log 2>&1 &
  PROXY_PID=$!
  sleep 1
}
stop_proxy() { kill "$PROXY_PID" 2>/dev/null; wait "$PROXY_PID" 2>/dev/null; }

req() {
  curl -s -m 60 -X POST "http://127.0.0.1:${PROXY_PORT}/v1/responses" \
    -H 'Content-Type: application/json' \
    -d '{"model":"gpt-5.6-sol","input":[{"type":"message","role":"user","content":[{"type":"input_text","text":"hi"}]}]}'
}

echo "=== Case A: old fixed-wall behaviour (HELMX_UPSTREAM_TIMEOUT=3) ==="
export HELMX_UPSTREAM_TIMEOUT=3
export HELMX_UPSTREAM_IDLE=120
start_proxy
BODY_A="$(req)"
stop_proxy
if echo "$BODY_A" | grep -q "response.completed"; then
  fail "Case A unexpectedly completed — ceiling did not bound the transfer"
fi
echo "OK: 3s ceiling truncated the stream (no response.completed), as the old 120s cap did"

echo "=== Case B: fix (ceiling=900, idle=5) ==="
export HELMX_UPSTREAM_TIMEOUT=900
export HELMX_UPSTREAM_IDLE=5
start_proxy
BODY_B="$(req)"
stop_proxy
echo "$BODY_B" | grep -q "response.completed" \
  || { echo "--- proxy.log ---"; cat /tmp/proxy.log; fail "Case B did not receive response.completed"; }
echo "$BODY_B" | grep -q "tok15" \
  || fail "Case B missing final delta (tok15) — stream was cut early"
echo "OK: slow streaming response completed; client received response.completed + all deltas"

echo
echo "ALL STREAMING TESTS PASSED"
