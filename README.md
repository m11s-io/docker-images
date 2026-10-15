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
```

## Publishing

Images are maintained in the private monorepo and published here via CI on push to `main`.

Each image build publishes its version tag, its existing `latest` alias, and a
`sha-<12-character Git commit>` tag. Rclone's commit tags end in `-inotify`,
and Caddy's end in `-cloudflare`;
ComfyUI's GGUF variant uses `-gguf` so it has separate version and commit tags.
Commit tags identify the source revision; rebuilds of the same revision can
replace them, so use an image digest when you need immutable content.

Image jobs in `.github/workflows/build.yaml` declare one version source:

- `version`: our explicit image release version, independent of runtime updates.
- `version_source: version-arg` with `version_ref`: an application release argument
  in the Dockerfile (S3 Upload Proxy and DeepSeek Harness). DeepSeek strips
  the `dsh-v` release prefix.
- `version_source: base-image` with `version_ref`: the tag from a named Dockerfile
  `FROM` image (rclone), with an optional `tag_suffix`.
- `version_source: base-arg` with `version_ref`: the tag from a Dockerfile image
  argument (vLLM's `VLLM_BASE_IMAGE` or Caddy's `CADDY_BASE_IMAGE`). Caddy strips
  `-alpine` and adds `-cloudflare` to its application version.

Renovate updates the Dockerfile pins and annotated application arguments; rclone,
vLLM, Caddy, S3 Upload Proxy, and DeepSeek publish the corresponding upstream
version automatically. DeepSeek release updates include the pinned source commit;
the build rejects a release whose commit does not match. Caddy builds the explicit
release with a pinned Cloudflare plugin. Digest updates retain the version alias and
publish a new commit tag. Invalid or ambiguous version sources fail before
publishing. Changes to the shared tag resolver rebuild all images. Image folders
are watched for changes, excluding Compose YAML files (`compose*.yaml`,
`compose*.yml`, `docker-compose*.yaml`, and `docker-compose*.yml`), Markdown files,
and `docs/` folders. These exclusions apply both to workflow triggers and image
selection, so updating a deployment digest or renaming documentation does not
rebuild an image. New build inputs in an image folder trigger builds automatically;
keep build inputs outside the excluded paths. A workflow-only change runs
validation without rebuilding images. Use **Run workflow** to select an image
(or `all`) whenever an explicit rebuild is needed.

DeepSeek Harness, Chromium CDP, and Comfy MCP use Docker's pinned reusable
GitHub Builder workflow to build AMD64 and ARM64 on native runners and assemble
the manifests. Their preparation job selects only changed images (or the manual
selection), uses the same tag resolver, and keeps the same version, latest, and
commit tags. AMD64-only images remain in the generic matrix. Cache scopes are
separate for each image, ComfyUI's GGUF variant, and each native platform.

Run the tag resolver checks with
`python3 -m unittest discover -s scripts -p 'test_*.py'`.

## MCP catalog

CI publishes [`m11s/mcp-catalog:latest`](https://hub.docker.com/r/m11s/mcp-catalog)
from the version-controlled MCP server definitions. Docker Desktop users import
that OCI reference in **MCP Toolkit → Catalog → Import catalog**, then add an
approved server to a profile. The catalog currently contains `comfy-mcp`.
