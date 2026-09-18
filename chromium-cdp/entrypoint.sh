#!/bin/sh
set -eu

exec chromium \
  --headless=new \
  --no-first-run \
  --no-default-browser-check \
  --disable-dev-shm-usage \
  --remote-debugging-address=0.0.0.0 \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chromium-profile \
  about:blank
