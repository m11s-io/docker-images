# m11s Docker Images

[![Build and push](https://github.com/m11s-io/docker-images/actions/workflows/build.yaml/badge.svg)](https://github.com/m11s-io/docker-images/actions/workflows/build.yaml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Public Docker images published to [Docker Hub](https://hub.docker.com/u/m11s).

## Available Images

| Image | Description | Version |
|-------|-------------|---------|
| [m11s/rclone](https://hub.docker.com/r/m11s/rclone) | rclone with inotify-tools | ![Version](https://img.shields.io/docker/v/m11s/rclone/latest-inotify?label=) |
| [m11s/decap-cms](https://hub.docker.com/r/m11s/decap-cms) | Decap CMS with S3 media library | ![Version](https://img.shields.io/docker/v/m11s/decap-cms/latest-s3?label=) |
| [m11s/caddy](https://hub.docker.com/r/m11s/caddy) | Caddy with the caddy-dns/cloudflare DNS-01 module | ![Version](https://img.shields.io/docker/v/m11s/caddy/latest-cloudflare?label=) |
| [m11s/s3-upload-proxy](https://hub.docker.com/r/m11s/s3-upload-proxy) | Proxies browser multipart uploads to any S3-compatible store (MinIO, R2, S3) | ![Version](https://img.shields.io/docker/v/m11s/s3-upload-proxy/latest?label=) |
| [m11s/redis-http-proxy](https://hub.docker.com/r/m11s/redis-http-proxy) | Bearer-token-authenticated HTTP proxy in front of a Redis instance | ![Version](https://img.shields.io/docker/v/m11s/redis-http-proxy/latest?label=) |
| [m11s/comfyui](https://hub.docker.com/r/m11s/comfyui) | Generic ComfyUI built from source on a CUDA runtime base; the `latest-gguf` variant includes the ComfyUI-GGUF loader | ![Version](https://img.shields.io/docker/v/m11s/comfyui/latest?label=) |
| [m11s/comfy-mcp](https://hub.docker.com/r/m11s/comfy-mcp) | Comfy MCP server with stdio and native Streamable HTTP transports; uses the Comfy CLI engine against a separately deployed ComfyUI | ![Version](https://img.shields.io/docker/v/m11s/comfy-mcp/latest?label=) |
| [m11s/deepseek-harness](https://hub.docker.com/r/m11s/deepseek-harness) | DeepSeek Harness web runtime; connects to a separately deployed browser provider when browser automation is needed | ![Version](https://img.shields.io/docker/v/m11s/deepseek-harness/latest?label=) |
| [m11s/chromium-cdp](https://hub.docker.com/r/m11s/chromium-cdp) | Headless Chromium browser exposing the Chrome DevTools Protocol for a colocated DeepSeek Harness runtime | ![Version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fhub.docker.com%2Fv2%2Frepositories%2Fm11s%2Fchromium-cdp%2Ftags%3Fname%3Dbookworm-%26ordering%3Dlast_updated%26page_size%3D1&query=%24.results%5B0%5D.name&label=&color=blue) |
| [m11s/vllm-openai-orjson](https://hub.docker.com/r/m11s/vllm-openai-orjson) | vLLM's official OpenAI-compatible server image with orjson for faster JSON serialization | ![Version](https://img.shields.io/docker/v/m11s/vllm-openai-orjson/latest-x86_64?label=) |
| [m11s/timestral](https://hub.docker.com/r/m11s/timestral) | Timestral forecasting API with CPU-only or NVIDIA CUDA PyTorch | ![CPU version](https://img.shields.io/docker/v/m11s/timestral/latest-cpu?label=CPU) ![CUDA version](https://img.shields.io/docker/v/m11s/timestral/latest-cuda?label=CUDA) |

## Quick Start

```bash
docker pull m11s/rclone:latest-inotify
docker pull m11s/decap-cms:latest-s3
docker pull m11s/caddy:latest-cloudflare
docker pull m11s/s3-upload-proxy:latest
docker pull m11s/redis-http-proxy:latest
docker pull m11s/comfyui:latest
docker pull m11s/comfy-mcp:latest
docker pull m11s/deepseek-harness:latest
docker pull m11s/chromium-cdp:latest
docker pull m11s/vllm-openai-orjson:latest-x86_64
docker pull m11s/timestral:latest-cpu
docker pull m11s/timestral:latest-cuda
```

## Publishing

Images are maintained in the private monorepo and published here via CI.

See the [build workflow](.github/workflows/build.yaml) for image selection,
version sources, tags, and build platforms, and the
[lint workflow](.github/workflows/lint.yaml) for Dockerfile checks.
Image-specific configuration and usage are documented in each image's directory.

To request a rebuild, use **Run workflow** in the build workflow and select an
image or `all`.

Run the tag resolver checks with
`python3 -m unittest discover -s scripts -p 'test_*.py'`.

## MCP catalog

CI publishes [`m11s/mcp-catalog:latest`](https://hub.docker.com/r/m11s/mcp-catalog)
from the version-controlled MCP server definitions. Docker Desktop users import
that OCI reference in **MCP Toolkit → Catalog → Import catalog**, then add an
approved server to a profile.
