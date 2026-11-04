#!/usr/bin/env bash
set -eo pipefail

digest=$(cat "$RUNNER_TEMP/openvino-candidate/evidence/manifest-sha256.txt")
docker run -d --name timestral-openvino-standard \
  -p 127.0.0.1:18080:8080 -p 127.0.0.1:18081:8081 \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=256m \
  --mount "type=bind,src=$RUNNER_TEMP/openvino-candidate/profiles,dst=/profiles,readonly" \
  -e MODEL_ID -e MODEL_REVISION -e TIMESTRAL_FORECAST_ARTIFACTS=/profiles \
  -e "TIMESTRAL_ARTIFACT_MANIFEST_SHA256=$digest" timestral-standard:openvino-preview
for attempt in $(seq 1 60); do
  if curl --fail --silent http://localhost:18080/v2/models/timestral/ready; then
    exit 0
  fi
  if [[ $(docker inspect --format '{{.State.Running}}' timestral-openvino-standard) != true ]]; then
    docker logs timestral-openvino-standard
    exit 1
  fi
  sleep 2
done
exit 1
