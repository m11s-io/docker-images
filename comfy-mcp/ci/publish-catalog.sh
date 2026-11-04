#!/usr/bin/env bash
set -eo pipefail

DOCKER_MCP_VERSION=v0.43.3

curl --fail --location --show-error --silent --output /tmp/docker-mcp.tar.gz \
  "https://github.com/docker/mcp-gateway/releases/download/${DOCKER_MCP_VERSION}/docker-mcp-linux-amd64.tar.gz"
tar --extract --gzip --file /tmp/docker-mcp.tar.gz --directory /tmp
install --directory "$HOME/.docker/cli-plugins"
install --mode 0755 /tmp/docker-mcp "$HOME/.docker/cli-plugins/docker-mcp"
docker mcp version

export DOCKER_MCP_IN_CONTAINER=1
install --directory "$HOME/.docker/mcp/catalogs"
tags=$(python3 scripts/image_tags.py --repository m11s/comfy-mcp \
  --version-arg COMFY_MCP_REF --strip-prefix v --dockerfile comfy-mcp/Dockerfile \
  --latest latest --sha "$GITHUB_SHA")
image=${tags%%$'\n'*}
sed "s|^image: .*|image: $image|" comfy-mcp/server.yaml > "$HOME/.docker/mcp/catalogs/comfy-mcp.yaml"
docker mcp catalog create m11s/mcp-catalog:0.1.0 --title "m11s MCP Catalog" --server file://comfy-mcp.yaml
docker mcp catalog push m11s/mcp-catalog:0.1.0
docker mcp catalog tag m11s/mcp-catalog:0.1.0 m11s/mcp-catalog:latest
docker mcp catalog push m11s/mcp-catalog:latest
