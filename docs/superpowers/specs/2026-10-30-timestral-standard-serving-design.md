# Timestral standard serving across hardware variants

## Agreed goal

Deploy Timestral through KServe on general CPU, NVIDIA GPU and supported AMD GPU,
with an optional Intel CPU optimization. Use standard serving protocols and
upstream forecasting algorithms; do not maintain a separate HTTP API or fork
Timestral. Variant names are `cpu`, `cuda`, `rocm`, `openvino`.

## Architecture

KServe owns deployment, readiness, routing and accelerator resource allocation.
All four images use the official KServe Python ModelServer with one shared
Timestral Model handler. CPU/CUDA/ROCm execute upstream Timestral/PyTorch with
hardware-specific framework builds and device selection. The OpenVINO variant
calls OpenVINO directly from its neural backend while preserving upstream
forecasting. OVMS is not part of the target architecture. Clients use the same
KServe V2 REST/gRPC tensor contract across all variants.

A thin model handler is unavoidable in the inspected upstream versions: KServe's
Hugging Face time-series implementation handles TimesFM, not Timestral. Standards
mean upstream server/protocol and minimal model integration, not absence of model
code. Upstream KServe itself uses FastAPI internally; that dependency is allowed.
Our own FastAPI routes, custom HTTP plumbing and copied forecasting algorithms
are not part of the target.

Images contain the server, pinned upstream code, hardware dependencies and thin
integration. Model weights/exported IR remain separately versioned artifacts.
Kubernetes drivers, device plugins, node selection and secrets are infrastructure.

## Scope and constraints

- Verify standard inference compatibility using actual Triton HTTP/gRPC clients;
  do not promise compatibility with Triton-specific extensions.
- One `timestral` project, Dockerfile per variant, one shared `.dockerignore`.
- Separate dependency locks where runtime Python/framework requirements differ.
- No edits to `.third_party/kserve` or `.third_party/timestral`.
- Reference inspected KServe commit abc6c47ab4af588e40c67372b4835122234f6f74,
  SDK version 0.21.0, Python requirement >=3.10,<3.14. Release/source parity must be
  verified before selecting a production package. Python 3.15.2 is not compatible
  with this SDK declaration; never override package constraints silently.
- Select a Python version supported by both KServe and the direct OpenVINO
  package. Preserve explicit ENABLE_CPU_PINNING=false as an initial shared-CPU
  setting and validate it with the direct OpenVINO runtime on target hardware.
- Existing 209M `/forecast` remains available during migration. The existing 5M
  block and bounded full-forecast experiments do not establish 209M parity.
- AMD support is conditional on the actual GPU architecture and compatible ROCm
  driver/container stack; no silent CPU fallback or unsupported-device claims.
- Changes to serving behavior, hardware, model size and protocol are validated
  separately. Public tags never imply feature parity that has not been proven.

## Alternatives considered

Keep custom FastAPI: already works, but perpetuates a separate API and server.
Use Triton everywhere: standard API, but adds another server/backend integration
and ROCm-specific builds without a demonstrated need. Selected baseline is the
KServe Python runtime for every variant. OVMS was useful for earlier experiments,
but adds a second serving framework without demonstrated benefit here; use
OpenVINO directly for Intel optimization.
