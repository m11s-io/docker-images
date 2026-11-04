#!/usr/bin/env bash
set -eo pipefail

mkdir -p "$RUNNER_TEMP/evidence"
docker logs timestral-standard > "$RUNNER_TEMP/evidence/server.log" 2>&1 || true
docker rm -f timestral-standard || true
