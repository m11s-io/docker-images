#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
compose_file="$repo_root/deepseek-harness/compose.yaml"

test -f "$compose_file"
docker compose -f "$compose_file" config >"${TMPDIR:-/tmp}/deepseek-harness-compose.yaml"
! grep -A8 '^  chromium:' "${TMPDIR:-/tmp}/deepseek-harness-compose.yaml" | grep -q 'published:'
grep -q 'user: "10001:10001"' "$compose_file"
grep -q 'DSH_BROWSER_CDP_ENDPOINT' "$repo_root/deepseek-harness/entrypoint.sh"
grep -q "mode: attach" "$repo_root/deepseek-harness/entrypoint.sh"
! grep -qi 'playwright install\|chromium-browser\|apt-get install.*chromium' "$repo_root/deepseek-harness/Dockerfile"
grep -q '^USER chromium$' "$repo_root/chromium-cdp/Dockerfile"
