#!/bin/sh
set -eu

: "${DSH_BROWSER_CDP_ENDPOINT:=http://chromium:9222}"
mkdir -p "$DSH_HOME"
cat >"$DSH_HOME/cordis.patch.yml" <<EOF
- id: webserver
  config:
    host: 0.0.0.0
    port: 3080
- insert:
    - name: '@deepseek-ai/dsh-browser-use'
    - name: '@deepseek-ai/dsh-experimental-browser-use-playwright-mcp'
      config:
        mode: attach
        endpoint: ${DSH_BROWSER_CDP_ENDPOINT}
EOF

exec node /opt/deepseek-harness/apps/cli/lib/bin.js web --no-open --trusted-host localhost:3080
