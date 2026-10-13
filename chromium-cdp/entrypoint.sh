#!/bin/bash
set -euo pipefail

chromium \
  --headless=new \
  --no-first-run \
  --no-default-browser-check \
  --disable-dev-shm-usage \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9223 \
  --user-data-dir=/tmp/chromium-profile \
  about:blank &
browser_pid=$!
nginx -g 'daemon off;' &
proxy_pid=$!

cleanup() {
  trap - EXIT INT TERM
  kill "$browser_pid" "$proxy_pid" 2>/dev/null || true
  wait "$browser_pid" "$proxy_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 0' INT TERM
# If either service exits, stop the other and let the container exit too.
wait -n "$browser_pid" "$proxy_pid"
