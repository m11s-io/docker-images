#!/bin/sh
set -eu

: "${DSH_BROWSER_CDP_ENDPOINT:=http://chromium:9222}"
DSH_BIND_HOST=$(node /usr/local/lib/dsh/bind-host.mjs)
export DSH_BIND_HOST
mkdir -p "$DSH_HOME"
cat >"$DSH_HOME/cordis.patch.yml" <<EOF
- id: webserver
  config:
    host: "${DSH_BIND_HOST}"
    port: 3080
- insert:
    - name: '@deepseek-ai/dsh-browser-use'
    - name: '@deepseek-ai/dsh-experimental-browser-use-playwright-mcp'
      config:
        mode: attach
        endpoint: ${DSH_BROWSER_CDP_ENDPOINT}
EOF

exec node /opt/deepseek-harness/apps/cli/lib/bin.js web --no-open --trusted-host localhost:3080
