# m11s Docker Images

[![Build and push](https://github.com/m11s-io/docker-images/actions/workflows/build.yaml/badge.svg)](https://github.com/m11s-io/docker-images/actions/workflows/build.yaml)
[![Docker Hub](https://img.shields.io/badge/Docker_Hub-m11s-2496ED?logo=docker&logoColor=white)](https://hub.docker.com/u/m11s)
[![Lint](https://github.com/m11s-io/docker-images/actions/workflows/lint.yaml/badge.svg)](https://github.com/m11s-io/docker-images/actions/workflows/lint.yaml)
[![MCP catalog](https://img.shields.io/badge/MCP-Catalog-7C3AED)](docs/mcp-catalog.md)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## CI layout

Each image's `image.json` defines its build variants, tags and watched paths.
GitHub workflow entry points stay in `.github/workflows/`; image-specific
procedures live beside their images in `ci/` directories. Run these scripts from
the repository root. The workflows retain job dependencies, permissions, tool
setup and artifact upload/download steps; ordinary builds use the organization's
shared container workflow. When adding a CI script, include its path in the
image manifest's `watch` patterns so changes trigger the relevant checks.

| Image | Description | Version |
|-------|-------------|---------|
| [rclone](rclone/README.md) | rclone with filesystem event monitoring | [![Version](https://img.shields.io/docker/v/m11s/rclone/latest-inotify?label=)](https://hub.docker.com/r/m11s/rclone) |
| [decap&#8209;cms](decap-cms/README.md) | Decap CMS with an S3 media library | [![Version](https://img.shields.io/docker/v/m11s/decap-cms/latest-s3?label=)](https://hub.docker.com/r/m11s/decap-cms) |
| [caddy](caddy/README.md) | Caddy with Cloudflare DNS support | [![Version](https://img.shields.io/docker/v/m11s/caddy/latest-cloudflare?label=)](https://hub.docker.com/r/m11s/caddy) |
| [s3&#8209;upload&#8209;proxy](s3-upload-proxy/README.md) | HTTP file uploads to S3-compatible storage | [![Version](https://img.shields.io/docker/v/m11s/s3-upload-proxy/latest?label=)](https://hub.docker.com/r/m11s/s3-upload-proxy) |
| [redis&#8209;http&#8209;proxy](https://github.com/m11s-io/redis-http-proxy) | Redis over HTTP with token authentication | [![Version](https://img.shields.io/docker/v/m11s/redis-http-proxy/latest?label=)](https://hub.docker.com/r/m11s/redis-http-proxy) |
| [comfyui](comfyui/README.md) | ComfyUI for NVIDIA and AMD GPUs | [![CUDA](https://img.shields.io/docker/v/m11s/comfyui/latest-cuda?label=CUDA)](https://hub.docker.com/r/m11s/comfyui)<br>[![ROCm](https://img.shields.io/docker/v/m11s/comfyui/latest-rocm?label=ROCm)](https://hub.docker.com/r/m11s/comfyui) |
| [comfy&#8209;mcp](comfy-mcp/README.md) | MCP server for controlling ComfyUI | [![Version](https://img.shields.io/docker/v/m11s/comfy-mcp/latest?label=)](https://hub.docker.com/r/m11s/comfy-mcp) |
| [deepseek&#8209;harness](deepseek-harness/README.md) | DeepSeek Harness web interface | [![Version](https://img.shields.io/docker/v/m11s/deepseek-harness/latest?label=)](https://hub.docker.com/r/m11s/deepseek-harness) |
| [chromium](chromium/README.md) | Headless Chromium with remote control | [![Version](https://img.shields.io/docker/v/m11s/chromium/latest-cdp?label=)](https://hub.docker.com/r/m11s/chromium) |
| [vllm&#8209;openai](vllm-openai/README.md) | vLLM with orjson for JSON serialization | [![Version](https://img.shields.io/docker/v/m11s/vllm-openai/latest-orjson?label=)](https://hub.docker.com/r/m11s/vllm-openai) |
| [timestral](timestral/README.md) | Time-series forecasting server | [![cpu](https://img.shields.io/docker/v/m11s/timestral/latest-cpu?label=CPU)](https://hub.docker.com/r/m11s/timestral) <br> [![cuda](https://img.shields.io/docker/v/m11s/timestral/latest-cuda?label=CUDA)](https://hub.docker.com/r/m11s/timestral) <br> [![rocm](https://img.shields.io/docker/v/m11s/timestral/latest-rocm?label=ROCm)](https://hub.docker.com/r/m11s/timestral) <br> [![openvino](https://img.shields.io/docker/v/m11s/timestral/latest-openvino?label=OpenVINO)](https://hub.docker.com/r/m11s/timestral) |
