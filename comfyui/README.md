# m11s/comfyui

[ComfyUI](https://github.com/comfyanonymous/ComfyUI) built from source on an
NVIDIA CUDA 13.4.2 runtime (Ubuntu 22.04), with Python 3.14.
Release `0.5.5` uses ComfyUI v0.39.0, torch 2.14.1, and torchvision 0.29.1
with CUDA 13.0 wheels. The default image contains no community nodes; the GGUF
variant adds the pinned `ComfyUI-GGUF` loader.

## Tags

| Tag | Use |
| --- | --- |
| `latest` | Current generic ComfyUI image |
| `0.5.5` | Pinned generic image release |
| `latest-gguf` | Current image with the ComfyUI-GGUF node |
| `0.5.5-gguf` | Pinned GGUF image release |

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
docker build -t m11s/comfyui:0.5.5 comfyui
docker build --build-arg COMFYUI_BASE=m11s/comfyui:0.5.5 \
  -f comfyui/Dockerfile.gguf -t m11s/comfyui:0.5.5-gguf comfyui
```

CI uses the generic build's exact digest for publishing and its locally loaded
image for dry runs. The standalone Dockerfile fallback remains pinned to the
previous published release until the new release digest is available.
