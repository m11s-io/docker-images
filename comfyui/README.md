# m11s/comfyui

[ComfyUI](https://github.com/Comfy-Org/ComfyUI) built from source with an NVIDIA
CUDA runtime and explicitly selected PyTorch wheels. The generic image contains
no community nodes; the GGUF variant adds the pinned `ComfyUI-GGUF` loader.

The [Dockerfile](Dockerfile) is the source of truth for the upstream release,
base image, Python interpreter, PyTorch packages, and CUDA wheel index.
[Dockerfile.gguf](Dockerfile.gguf) pins the generic parent and GGUF commit.
PyTorch bundles its own CUDA libraries, independently of the container base.
Audio dependencies follow the selected upstream requirements.

## Tags

Tags derive from `COMFYUI_REF`, with the leading `v` removed. The GGUF variant
adds `-gguf`. Dependency and packaging changes retain the upstream version and
produce new digests and source commit tags. Pin a digest for reproducible
release deployments.

| Tag | Use |
| --- | --- |
| `<upstream-version>` | Generic image for that upstream release |
| `<upstream-version>-gguf` | The same release with GGUF support |
| `latest` | Current generic image |
| `latest-gguf` | Current GGUF image |

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
when your workflow requires the ComfyUI-GGUF custom node.

## Building and validation

Build the generic image first, then pass it explicitly as the GGUF parent:

```bash
docker build -t m11s/comfyui:local comfyui
docker build --build-arg COMFYUI_BASE=m11s/comfyui:local \
  -f comfyui/Dockerfile.gguf -t m11s/comfyui:local-gguf comfyui
```

Both Dockerfiles run dependency, pinned-package, audio-resampling, and CPU
startup checks before the build succeeds. The GGUF build also checks loader
registration. Failed checks prevent that image from being exported or published.
Validation runs in a disposable build stage, keeping startup state out of the
published image. These checks do not perform GPU inference.

CI uses the generic build's exact digest when rebuilding the GGUF variant.
For GGUF-only changes, it uses the pinned parent in `Dockerfile.gguf`.
