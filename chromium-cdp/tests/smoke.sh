#!/bin/sh
set -eu

image=${1:-m11s/chromium-cdp:local}
client_image=${CDP_TEST_CLIENT_IMAGE:-node:24-bookworm}
test_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
network="chromium-cdp-test-$$"
container="chromium-cdp-test-$$"
cleanup() {
  docker stop --time 5 "$container" >/dev/null 2>&1 || true
  docker rm -f "$container" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM
docker network create "$network" >/dev/null
docker run -d --name "$container" --network "$network" --network-alias chromium \
  --security-opt seccomp=unconfined "$image" >/dev/null
if ! docker run --rm --network "$network" --entrypoint node \
  -v "$test_dir/cdp.mjs:/test/cdp.mjs:ro" "$client_image" /test/cdp.mjs; then
  docker logs "$container"
  exit 1
fi
docker stop --time 5 "$container" >/dev/null
exit_code=$(docker inspect --format '{{.State.ExitCode}}' "$container")
if [ "$exit_code" != 0 ]; then
  docker logs "$container"
  echo "Container did not stop cleanly: $exit_code" >&2
  exit 1
fi
