# m11s/comfyui

[ComfyUI](https://github.com/comfyanonymous/ComfyUI) built from source on an
NVIDIA CUDA 13.4.2 runtime (Ubuntu 22.04), with Python 3.14.
Image `0.40.0` follows ComfyUI v0.40.0, with torch 2.14.1 and torchvision 0.29.1
using CUDA 13.0 wheels. The default image contains no community nodes; the GGUF
variant adds the pinned `ComfyUI-GGUF` loader.

Publish tags derive from `COMFYUI_REF` in the Dockerfile, with the leading `v`
removed. The GGUF variant adds `-gguf`. Dependency and packaging changes retain
the upstream version and produce new digests and source commit tags. Existing
`0.5.6` and `0.5.6-gguf` tags remain available as legacy releases.

## Tags

| Tag | Use |
| --- | --- |
| `latest` | Current generic ComfyUI image |
| `0.40.0` | Pinned upstream ComfyUI release |
| `latest-gguf` | Current image with the ComfyUI-GGUF node |
| `0.40.0-gguf` | The same ComfyUI release with GGUF support |

## Usage

The image requires an NVIDIA GPU and the NVIDIA Container Toolkit on the host.
Persist models, input files, output files, and user configuration with mounts:

```bash
docker run --rm --gpus all -p 8188:8188 \
  -v "$PWD/models:/app/models" \
  -v "$PWD/input:/app/input" \
  -v "$PWD/output:/app/output" \
  -v "$PWD/user:/app/user" \
  m11s/comfyui:latest
```

Open `http://localhost:8188` after startup. Use `m11s/comfyui:latest-gguf`
when your workflow requires the ComfyUI-GGUF custom node. Source and license:
[m11s-io/docker-images](https://github.com/m11s-io/docker-images).

## Building the GGUF variant

Build the generic image first, then pass it explicitly as the GGUF parent:

```bash
docker build -t m11s/comfyui:0.40.0 comfyui
docker build --build-arg COMFYUI_BASE=m11s/comfyui:0.40.0 \
  -f comfyui/Dockerfile.gguf -t m11s/comfyui:0.40.0-gguf comfyui
```

CI uses the generic build's exact digest when rebuilding the generic image.
For GGUF-only digest updates, CI builds from this file's pinned parent image.
Standalone builds also default to the digest-pinned generic `0.40.0` release.
