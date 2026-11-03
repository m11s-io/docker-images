# Timestral runtime matrix

All four images run the official KServe ModelServer and the shared V2 model
binding. There is no custom HTTP API, copied forecasting loop or CPU fallback.

| Flavor | Python/base | Neural execution | Model data |
| --- | --- | --- | --- |
| cpu | 3.13.18 / Debian bookworm | PyTorch 2.14.1+cpu | external upstream checkpoint |
| cuda | same | PyTorch 2.14.1+cu130 | external upstream checkpoint |
| rocm | same | PyTorch 2.14.1+rocm7.2 | external upstream checkpoint |
| openvino | same | OpenVINO 2026.4.1 | external model-specific v2 graphs |

OpenVINO retains PyTorch 2.13.0+cpu for unchanged upstream normalization,
categorical handling and refinement. It does not load PyTorch neural weights.
Export tooling has a separate environment and is not included in runtime images.
All five frozen environments are checked in CI. Installed dependency versions
and hashes are recorded in their locks; image/model/artifact pins are independent.

KServe source: `abc6c47ab4af588e40c67372b4835122234f6f74` (`python/kserve`).
Its metadata supports Python >=3.10,<3.14, lists Python3.13 and tests3.13 upstream.
Use this official source pin rather than silently substituting a wheel with
different dependency/security requirements. Timestral source remains
`a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff` (1.0.0).

GPU devices must match the packaged framework and native wheel architecture.
CUDA requires the NVIDIA runtime/device plugin and framework support for the
selected compute capability. The validated AMD target is gfx1201; ROCm requires
its existing device plugin, KFD/render devices and host compatibility. Missing
accelerators or architecture overrides fail startup. Host drivers are not installed
inside these images.

Current code and runtime pins are distinct from historical validation pins.
The [bounded comparison](verification/2026-11-02-speed-accuracy.md) and
[full OpenVINO divergence assessment](verification/2026-11-02-openvino-full-divergence.md)
state their exact scope. Python3.13 builds and the expanded OpenVINO v2 artifacts
require their own native CI/publication evidence; earlier results are not proof
for an untested new image. Deployment and caller migration are separate steps.
