# m11s/comfyui

[ComfyUI](https://github.com/Comfy-Org/ComfyUI) built from source on a Python
base with explicitly selected CUDA-enabled PyTorch wheels. The generic image contains
no bundled community nodes. Install extensions such as ComfyUI-GGUF through
the Helm chart’s `customNodes` configuration.

The [Dockerfile](https://github.com/m11s-io/docker-images/blob/main/comfyui/Dockerfile) is the source of truth for the upstream release,
base image, Python interpreter, PyTorch packages, and CUDA wheel index.
PyTorch supplies the CUDA runtime libraries; the image has no separate system
CUDA toolkit. The host NVIDIA container runtime supplies driver libraries.
Comfy Kitchen and AIMDO must install from prebuilt wheels; missing wheels fail
the build instead of compiling a different backend from source.
Audio dependencies follow the selected upstream requirements.

`requirements-cuda.txt` pins stable CUDA-enabled Torch and TorchVision wheels
from the official PyTorch indexes. Renovate discovers newer CUDA variants through
the aggregate index; installation derives the complete channel index from the
Torch pin. The same file constrains upstream installation.
Renovate groups these version updates with the ComfyUI release and base image;
newer CUDA variants are eligible automatically. Renovate auto merges these
updates after required GitHub image, runtime, lint and dependency-policy checks pass.
Nightly, prerelease, CPU and ROCm wheels are excluded from CUDA updates.
The inherited release cooldown is disabled only for these PyTorch wheel pins
because Renovate does not read upload timestamps from the HTML wheel index.
A scoped Renovate manager compares the CUDA suffix numerically, including
CUDA-only changes within the same Torch release. Python local-version range
handling can otherwise treat different GPU variants as the same pin.
These direct pins are not a complete transitive dependency lock.

## Tags

Tags derive from `COMFYUI_REF`, with the leading `v` removed. The CUDA image adds `-cuda`. Dependency and packaging changes retain the upstream version and
produce new digests and source commit tags. Pin a digest for reproducible
release deployments.

| Tag | Use |
| --- | --- |
| `<upstream-version>-cuda` | Generic CUDA image for that upstream release |
| `latest-cuda` | Current generic CUDA image |
| `<upstream-version>-rocm` | AMD ROCm image for that upstream release |
| `latest-rocm` | Current AMD ROCm image |

## Usage

The image requires an NVIDIA GPU and the NVIDIA Container Toolkit on the host.
Persist models, input files, output files, and user configuration with mounts:

```bash
docker run --rm --gpus all -p 8188:8188 \
  -v "$PWD/models:/app/models" \
  -v "$PWD/input:/app/input" \
  -v "$PWD/output:/app/output" \
  -v "$PWD/user:/app/user" \
  m11s/comfyui:latest-cuda
```

Open `http://localhost:8188` after startup. Custom nodes are managed separately
from the application image; the Helm chart can install pinned repositories.

## Building and validation

Build the generic image:

```bash
docker build -t m11s/comfyui:local comfyui
```

The Dockerfile runs dependency, pinned-package, native CUDA extension loading,
audio-resampling, and CPU startup checks before the build succeeds.
Failed checks prevent image publication.
Validation runs in a disposable build stage, keeping startup state out of the
published image. These checks do not perform GPU inference.

## GPU release checks

Before promoting a candidate image on an NVIDIA node:

- Compare `nvidia-smi` driver support with the candidate's `torch.version.cuda`.
- Run a CUDA tensor operation and synchronize it; check that Kitchen's native
  CUDA backend is available.
- Run representative quantized ComfyUI and GGUF workflows on the target GPU.
- Review startup/backend logs and output correctness before production promotion.

GitHub's CPU runners validate packaging and startup; these release checks require
an actual NVIDIA GPU.

## AMD ROCm image

`Dockerfile.rocm` targets Radeon AI PRO R9700 (`gfx1201`, 32 GiB per GPU)
with ROCm 10.1.0, PyTorch 2.14.0 and Python 3.14 on Ubuntu 26.04. The base
is AMD's digest-pinned PyTorch image. `requirements-rocm.txt` records its exact
Torch/TorchVision/ROCm identities, including AMD's matching TorchVision
`0.29.0a0` build. These pins and the inherited ROCm library pins constrain
ComfyUI dependency installation. The container uses UID/GID 10001.

Sources: [AMD release notes](https://rocm.docs.amd.com/en/latest/about/release-notes.html)
and [PyTorch installation](https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/frameworks/pytorch/install.html).
ROCm 10.1 is the current documented stack; PyTorch 2.15 is newer than the
2.14.0 pairing validated in AMD's 10.1 matrix.

GitHub Actions builds and publishes this backend on main. `comfyui-rocm` is
also available in manual workflow selection. Tags are `<upstream-version>-rocm`
and `latest-rocm`. Pull-request builds validate without publishing.
Publication verifies packaging and CPU startup; AMD GPU inference acceptance
remains a separate hardware check.
Custom nodes are installed separately for either backend.

The shared validator checks the selected GPU backend, exact installed pins,
`pip check`, audio resampling and CPU HTTP startup. For ROCm it reports Kitchen
HIP extension loading; CPU CI cannot prove native GPU dispatch or inference.
CUDA retains its mandatory native Kitchen extension check. Validation state
stays in a disposable stage. Only explicit backend tags are assigned to new builds; unsuffixed and `-gguf` legacy aliases are not updated.

The intended Talos AMD node is an established host baseline. Container device
allocation and inference still require testing with the built candidate. Use
`amd.com/gpu`, AMD node selection, separate storage and the existing non-root
security policy; no privileged mode or relaxed seccomp settings are added.

## OS package pins

Direct apt dependencies in both backend Dockerfiles use exact distribution
versions. Renovate reads the matching Debian Bookworm or Ubuntu Resolute
repositories, including updates and security pockets. These direct pins do not
lock apt's transitive dependencies or retain packages removed from live mirrors;
image builds fail if a pinned version disappears rather than silently choosing
another version. Refresh pins through reviewed dependency updates.
