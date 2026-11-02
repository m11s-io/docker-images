# m11s Docker Images

[![Build and push](https://github.com/m11s-io/docker-images/actions/workflows/build.yaml/badge.svg)](https://github.com/m11s-io/docker-images/actions/workflows/build.yaml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Public Docker images published to [Docker Hub](https://hub.docker.com/u/m11s).

## Available Images

| Image | Description | Version |
|-------|-------------|---------|
| [m11s/rclone](https://hub.docker.com/r/m11s/rclone) | rclone with filesystem event monitoring | ![Version](https://img.shields.io/docker/v/m11s/rclone/latest-inotify?label=) |
| [m11s/decap-cms](https://hub.docker.com/r/m11s/decap-cms) | Decap CMS with an S3 media library | ![Version](https://img.shields.io/docker/v/m11s/decap-cms/latest-s3?label=) |
| [m11s/caddy](https://hub.docker.com/r/m11s/caddy) | Caddy with Cloudflare DNS support | ![Version](https://img.shields.io/docker/v/m11s/caddy/latest-cloudflare?label=) |
| [m11s/s3-upload-proxy](https://hub.docker.com/r/m11s/s3-upload-proxy) | HTTP file uploads to S3-compatible storage | ![Version](https://img.shields.io/docker/v/m11s/s3-upload-proxy/latest?label=) |
| [m11s/redis-http-proxy](https://hub.docker.com/r/m11s/redis-http-proxy) | Redis over HTTP with token authentication | ![Version](https://img.shields.io/docker/v/m11s/redis-http-proxy/latest?label=) |
| [m11s/comfyui](https://hub.docker.com/r/m11s/comfyui) | ComfyUI for NVIDIA and AMD GPUs | ![CUDA](https://img.shields.io/docker/v/m11s/comfyui/latest-cuda?label=CUDA) ![ROCm](https://img.shields.io/docker/v/m11s/comfyui/latest-rocm?label=ROCm) |
| [m11s/comfy-mcp](https://hub.docker.com/r/m11s/comfy-mcp) | MCP server for controlling ComfyUI | ![Version](https://img.shields.io/docker/v/m11s/comfy-mcp/latest?label=) |
| [m11s/deepseek-harness](https://hub.docker.com/r/m11s/deepseek-harness) | Web interface for DeepSeek Harness | ![Version](https://img.shields.io/docker/v/m11s/deepseek-harness/latest?label=) |
| [m11s/chromium](https://hub.docker.com/r/m11s/chromium) | Headless Chromium for remote browser automation | ![Version](https://img.shields.io/docker/v/m11s/chromium/latest-cdp?label=) |
| [m11s/vllm-openai](https://hub.docker.com/r/m11s/vllm-openai) | vLLM with orjson for JSON serialization | ![Version](https://img.shields.io/docker/v/m11s/vllm-openai/latest-orjson?label=) |
| [m11s/timestral](https://hub.docker.com/r/m11s/timestral) | Time-series forecasting server | ![cpu](https://img.shields.io/docker/v/m11s/timestral/latest-cpu?label=CPU) <br> ![cuda](https://img.shields.io/docker/v/m11s/timestral/latest-cuda?label=CUDA) <br> ![rocm](https://img.shields.io/docker/v/m11s/timestral/latest-rocm?label=ROCm) <br> ![openvino](https://img.shields.io/docker/v/m11s/timestral/latest-openvino?label=OpenVINO) |

## Quick Start

```bash
docker pull m11s/rclone:latest-inotify
docker pull m11s/decap-cms:latest-s3
docker pull m11s/caddy:latest-cloudflare
docker pull m11s/s3-upload-proxy:latest
docker pull m11s/redis-http-proxy:latest
docker pull m11s/comfyui:latest-cuda
docker pull m11s/comfyui:latest-rocm
docker pull m11s/comfy-mcp:latest
docker pull m11s/deepseek-harness:latest
docker pull m11s/chromium:latest-cdp
docker pull m11s/vllm-openai:latest-orjson
```

Timestral is available in four runtime flavors:

```bash
docker pull m11s/timestral:latest-cpu
docker pull m11s/timestral:latest-cuda
docker pull m11s/timestral:latest-rocm
docker pull m11s/timestral:latest-openvino
```

These commands download the images. See the [Timestral runtime setup](timestral/README.md)
for model configuration and OpenVINO artifact requirements.

## Publishing

Images are maintained in the private monorepo and published here via CI.

See the [build workflow](.github/workflows/build.yaml) for image selection,
version sources, tags, and build platforms, and the
[lint workflow](.github/workflows/lint.yaml) for Dockerfile checks.
Image-specific configuration and usage are documented in each image's directory.

To request a rebuild, use **Run workflow** in the build workflow and select an
image or `all`. Timestral uses the same version-and-flavor publishing scheme as
the other images.

Run the tag resolver checks with
`python3 -m unittest discover -s scripts -p 'test_*.py'`.

## MCP catalog

CI publishes [`m11s/mcp-catalog:latest`](https://hub.docker.com/r/m11s/mcp-catalog)
from the version-controlled MCP server definitions. Docker Desktop users import
that OCI reference in **MCP Toolkit → Catalog → Import catalog**, then add an
approved server to a profile.
