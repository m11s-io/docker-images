#!/usr/bin/env bash
set -eo pipefail

mkdir -p "$RUNNER_TEMP/openvino-candidate/evidence"
docker image inspect timestral-standard:openvino-preview > "$RUNNER_TEMP/openvino-candidate/evidence/image-inspect.json" || true
docker logs timestral-openvino-standard > "$RUNNER_TEMP/openvino-candidate/evidence/server.log" 2>&1 || true
docker rm -f timestral-openvino-standard || true
