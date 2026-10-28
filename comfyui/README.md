# m11s/comfyui

[ComfyUI](https://github.com/Comfy-Org/ComfyUI) built from source on a Python
base with explicitly selected CUDA-enabled PyTorch wheels. The generic image contains
no community nodes; the GGUF variant adds the pinned `ComfyUI-GGUF` loader.

The [Dockerfile](https://github.com/m11s-io/docker-images/blob/main/comfyui/Dockerfile) is the source of truth for the upstream release,
base image, Python interpreter, PyTorch packages, and CUDA wheel index.
[Dockerfile.gguf](https://github.com/m11s-io/docker-images/blob/main/comfyui/Dockerfile.gguf) pins the generic parent and GGUF commit.
PyTorch supplies the CUDA runtime libraries; the image has no separate system
CUDA toolkit. The host NVIDIA container runtime supplies driver libraries.
Comfy Kitchen and AIMDO must install from prebuilt wheels; missing wheels fail
the build instead of compiling a different backend from source.
Audio dependencies follow the selected upstream requirements.

`requirements-cuda.txt` pins stable CUDA-enabled Torch and TorchVision wheels
from the aggregate official PyTorch index. It also supplies the pins used to constrain upstream installation.
Renovate groups these version updates with the ComfyUI release and base image;
newer CUDA variants are eligible automatically. Renovate auto merges these
updates after required GitHub image, runtime, lint and dependency-policy checks pass.
Nightly, prerelease, CPU and ROCm wheels are excluded from CUDA updates.
The inherited release cooldown is disabled only for these PyTorch wheel pins
because Renovate does not read upload timestamps from the HTML wheel index.
These direct pins are not a complete transitive dependency lock.

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

Both Dockerfiles run dependency, pinned-package, native CUDA extension loading,
audio-resampling, and CPU
startup checks before the build succeeds. The GGUF build also checks loader
registration. Failed checks prevent that image from being exported or published.
Validation runs in a disposable build stage, keeping startup state out of the
published image. These checks do not perform GPU inference.

CI uses the generic build's exact digest when rebuilding the GGUF variant.
For GGUF-only changes, it uses the pinned parent in `Dockerfile.gguf`.
