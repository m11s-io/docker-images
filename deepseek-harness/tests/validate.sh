#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
compose_file="$repo_root/deepseek-harness/compose.yaml"

test -f "$compose_file"
docker compose -f "$compose_file" config >"${TMPDIR:-/tmp}/deepseek-harness-compose.yaml"
DSH_BROWSER_CDP_ENDPOINT=http://browser.internal:9222 \
  docker compose -f "$compose_file" config >"${TMPDIR:-/tmp}/deepseek-harness-compose-custom-cdp.yaml"
grep -q 'DSH_BROWSER_CDP_ENDPOINT: http://browser.internal:9222' \
  "${TMPDIR:-/tmp}/deepseek-harness-compose-custom-cdp.yaml"
awk '
  /^  dsh:$/ { in_dsh = 1; next }
  in_dsh && /^[^[:space:]]/ { in_dsh = 0 }
  in_dsh && /^  [^[:space:]][^:]*:$/ { in_dsh = 0 }
  in_dsh && /^    build:/ { exit 1 }
' "${TMPDIR:-/tmp}/deepseek-harness-compose.yaml"
grep -q '^    image: m11s/deepseek-harness:0.1.6-alpha.1$' "$compose_file"
awk '
  /^  chromium:$/ { in_chromium = 1; next }
  in_chromium && /^[^[:space:]]/ { in_chromium = 0 }
  in_chromium && /^  [^[:space:]][^:]*:$/ { in_chromium = 0 }
  in_chromium && /published:/ { exit 1 }
' "${TMPDIR:-/tmp}/deepseek-harness-compose.yaml"
grep -q 'user: "10001:10001"' "$compose_file"
grep -q 'DSH_BROWSER_CDP_ENDPOINT' "$repo_root/deepseek-harness/entrypoint.sh"
grep -q "mode: attach" "$repo_root/deepseek-harness/entrypoint.sh"
! grep -qi 'playwright install\|chromium-browser\|apt-get install.*chromium' "$repo_root/deepseek-harness/Dockerfile"
grep -q '^USER chromium$' "$repo_root/chromium-cdp/Dockerfile"
