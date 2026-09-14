# m11s/comfyui

[ComfyUI](https://github.com/comfyanonymous/ComfyUI) built from source on an
NVIDIA CUDA runtime. The default image contains no community nodes; the GGUF
variant adds the pinned `ComfyUI-GGUF` loader.

## Tags

| Tag | Use |
| --- | --- |
| `latest` | Current generic ComfyUI image |
| `0.5.2` | Pinned generic image release |
| `latest-gguf` | Current image with the ComfyUI-GGUF node |
| `0.5.2-gguf` | Pinned GGUF image release |

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
