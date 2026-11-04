#!/usr/bin/env bash
set -eo pipefail

mkdir -p "$RUNNER_TEMP/model-cache" "$RUNNER_TEMP/evidence"
chmod 0777 "$RUNNER_TEMP/model-cache"
docker image inspect timestral-standard:candidate > "$RUNNER_TEMP/evidence/image-inspect.json"

docker run -d --name timestral-standard \
  -p 127.0.0.1:18080:8080 -p 127.0.0.1:18081:8081 \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=256m \
  --mount "type=bind,src=$RUNNER_TEMP/model-cache,dst=/models" \
  -e MODEL_ID -e MODEL_REVISION timestral-standard:candidate
ready=false
for attempt in $(seq 1 180); do
  if curl --fail --silent http://localhost:18080/v2/models/timestral/ready; then
    ready=true
    break
  fi
  if [[ $(docker inspect --format '{{.State.Running}}' timestral-standard) != true ]]; then
    docker logs timestral-standard
    exit 1
  fi
  sleep 2
done
if [[ "$ready" != true ]]; then
  docker logs timestral-standard
  exit 1
fi
export TIMESTRAL_REFERENCE_DIR="$RUNNER_TEMP/reference"
mkdir -p "$TIMESTRAL_REFERENCE_DIR"
chmod 0777 "$TIMESTRAL_REFERENCE_DIR"
docker run --rm --entrypoint python \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=256m \
  --mount "type=bind,src=$RUNNER_TEMP/model-cache,dst=/models" \
  --mount "type=bind,src=$TIMESTRAL_REFERENCE_DIR,dst=/reference" \
  --mount "type=bind,src=$GITHUB_WORKSPACE/timestral/tests/integration,dst=/diagnostics,readonly" \
  -e MODEL_ID -e MODEL_REVISION timestral-standard:candidate /diagnostics/reference.py
uv run --frozen --project timestral/dependencies/cpu python -m pytest \
  timestral/tests/integration/test_triton_client.py -q \
  -o asyncio_default_fixture_loop_scope=function \
  --junitxml="$RUNNER_TEMP/evidence/forecast-parity.xml"
cp -a "$TIMESTRAL_REFERENCE_DIR" "$RUNNER_TEMP/evidence/reference"
docker logs timestral-standard > "$RUNNER_TEMP/evidence/server.log" 2>&1
docker rm -f timestral-standard
