#!/usr/bin/env bash
set -eo pipefail

image_tag="m11s/timestral:sha-${GITHUB_SHA:0:12}-openvino"
digest=$(docker buildx imagetools inspect "$image_tag" --format '{{.Manifest.Digest}}')
[[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]]
echo "TIMESTRAL_RELEASE_IMAGE=m11s/timestral@$digest" >> "$GITHUB_ENV"
