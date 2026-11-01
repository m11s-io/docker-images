# Standard-serving runtime audit

Status: candidate, not promoted. Audited 2026-10-30. This matrix governs the
new standard-serving dependencies; the existing `/forecast` images remain intact
until client acceptance. No hardware variant is interchangeable by assertion.

## Server and source selection

Use official KServe source commit `abc6c47ab4af588e40c67372b4835122234f6f74`
(`python/kserve`, declares 0.21.0), not the published 0.21.0 wheel. Inspection
covered `model.py`, `model_server.py`, `protocol/infer_type.py` and
`python/custom_model/model_grpc.py`. Use public InferRequest/InferResponse and
ModelServer APIs. The built-in HuggingFaceTimeSeriesModel dispatches only TimesFM;
it cannot serve Timestral at this commit.

The [published metadata](https://pypi.org/pypi/kserve/0.21.0/json) differs
materially: urllib3>=2.7.0 vs source>=2.8.0, aiohttp>=3.13.4 vs>=3.14.3,
pyjwt>=2.13.0 vs>=2.14.0,<2.15.0, and missing source OpenTelemetry dependencies.
Reject that wheel for this migration. Install the immutable official source,
retain its bounds and resolve a frozen lock. Never apply dependency overrides.
Both declare Python >=3.10,<3.14.

Timestral source remains `a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff`, version
1.0.0. The adapter invokes upstream forecast unchanged. Weights remain external,
identified separately by repository and 40-character commit.

| Variant | Candidate Python/base | Framework | Device | Artifact | Acceptance |
| --- | --- | --- | --- | --- | --- |
| cpu | CPython 3.12.16 / bookworm | torch 2.14.1+cpu | explicit cpu | upstream config + safetensors | pending image/transport/forecast evidence |
| cuda | same | torch 2.14.1+cu130 | explicit cuda:N, NVIDIA | upstream config + safetensors | pending final forecasts on target |
| rocm | same, wheel-supplied userspace | torch 2.14.1+rocm7.2 | explicit cuda:N, HIP gfx1201 | upstream config + safetensors | experimental; host compatibility pending |
| openvino | same | OpenVINO 2026.4.1; torch 2.6.0+cpu for upstream algorithms | explicit CPU | verified versioned FP32 profile bundle | experimental; model-specific 5M/209M candidates, native acceptance required |

Immutable shared candidate base:
`python:3.12.16-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337`.
Resolved from the official multi-platform index; runtime images target amd64.
The CUDA cp312 amd64 wheel SHA256 is
`5359b255ac68c0cabb8293952b38e00f0d1a570815cd87f19b61af702c071410`;
ROCm is `fc35e48fd83329f5d60ab925951d138edb5a6fce84323600703637fbc693541c`.
These prove availability, not execution. Frozen locks are the complete dependency
inventory once resolved. Export dependencies stay separate from serving.

## Hardware audit and prerequisites

Read-only target inspection found NVIDIA GeForce RTX 5070 Ti, compute capability
12.0, driver 595.91.07; the CUDA image must contain sm_120 support. Kubernetes
advertises NVIDIA devices through its existing device plugin. Require NVIDIA
container runtime and matched host driver; no driver installation in the image.

AMD KFD topology reports gfx_target_version 120001 (gfx1201), PCI device 0x7551,
two devices. The existing AMD device plugin advertises devices, but logs topology
parsing errors. This is not acceptance. Initially allow only gfx1201; reject all
other targets until separately validated. Require compatible amdgpu/KFD host
module, /dev/kfd and assigned /dev/dri render nodes with correct permissions,
AMD device plugin, and ROCm userspace/host compatibility. Talos host compatibility
with this candidate is unproven. No HSA_OVERRIDE_GFX_VERSION or CPU fallback.
See [AMD's versioned compatibility matrix](https://rocm.docs.amd.com/en/docs-7.2.0/compatibility/compatibility-matrix.html).
A supported LLVM target alone does not establish support for an arbitrary host OS.

## Existing candidate and evidence limits

Checkout started at ce02f44 with unrelated local edits. Local main diverged from
origin/main (1 ahead, 21 behind); no merge/reset was performed. PR #130 is open at
c8b9f2229fe9459b6e89dc0d96d995978040be26. Its OVMS image validation failed;
export validation and ordinary Timestral tests passed. That candidate is a
bounded 5M experiment, not the completed architecture. No candidate was merged,
published or deployed by this audit.

Reusable candidate code: direct block execution, scaler binding, bounded final
forecast parity and artifact verification. Exclude Python-node bindings,
MediaPipe graph, pyovms and OVMS runtime. Preserve historical experiment evidence
and the `timestral-openvino.yaml` OIDC workflow identity.

ROCm resolution selected the official 7.2 wheel with Triton ROCm 3.8.0 from
the same index. The proposed 7.14 wheel requires a separately distributed SDK
graph; no dependency overrides were applied to force it through.

CUDA execution explicitly selects IEEE FP32 through the
[PyTorch 2.14 precision API](https://docs.pytorch.org/docs/2.14/notes/cuda.html).
Forced TF32 environment overrides are rejected; device forecasts still need
measured parity on the actual target before acceptance.
