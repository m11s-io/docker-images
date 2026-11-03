# Timestral forecasting server

One official KServe Python ModelServer and shared Timestral handler, with variant
names `cpu`, `cuda`, `rocm`, `openvino`. The handler calls unchanged, pinned
upstream forecasting. Images contain code and dependencies; weights and IR stay
external and revision pinned. Standard ports: REST 8080, gRPC 8081.

Four validated runtime flavors are published with the same naming scheme:

| Flavor | Version tag | Moving tag |
| --- | --- | --- |
| CPU | `1.0.0-cpu` | `latest-cpu` |
| CUDA | `1.0.0-cuda` | `latest-cuda` |
| ROCm | `1.0.0-rocm` | `latest-rocm` |
| OpenVINO | `1.0.0-openvino` | `latest-openvino` |

Release tags follow `TIMESTRAL_VERSION`; source tags use `sha-<commit>-<flavor>`.
Serving and dependency changes rebuild these aliases with a new digest. Pin a
source tag or digest for an immutable deployment. The normal build workflow
publishes all four flavors. Earlier acceptance-build receipts remain historical
validation records.

These images use KServe V2, replacing the old `/forecast` API. See the
[V2 contract](docs/protocol.md), [runtime matrix](docs/runtime-matrix.md), and
[validation results](benchmarks/README.md) for configuration and device behavior.

## Published candidates

Use the [published tags and immutable digests](docs/verification/2026-11-01-published-candidates.json)
for CPU, CUDA, ROCm and OpenVINO, plus the matching model/artifact revisions.
`candidate-standard-v1-*` names are local CI build labels, not published release
aliases.

## Configuration

Set `MODEL_ID` explicitly when selecting a model other than the preserved default
`mistralai/Timestral-209M`. `MODEL_REVISION` is required and must be its immutable
40-character commit. `HF_HOME` is a writable external cache (default
`/models/huggingface`); inject `HF_TOKEN` only at runtime if needed. Never bake
weights, caches or tokens into images. `TORCH_NUM_THREADS` defaults to 2.

`TIMESTRAL_BACKEND` is cpu/cuda/rocm/openvino and must match the packaged framework.
`MODEL_DEVICE` is cpu or explicit cuda:N (including PyTorch's HIP API for AMD).
Missing accelerators, wrong vendor/framework, unsupported architectures and device
mismatches fail startup. There is no automatic CPU fallback. One worker and one
model inference slot are enforced; a cancelled caller cannot oversubscribe it.

OpenVINO selects `MODEL_ID=mistralai/Timestral-5M` or `mistralai/Timestral-209M`, its matching documented
revision, `TIMESTRAL_FORECAST_ARTIFACTS` pointing to a read-only profile bundle and
`TIMESTRAL_ARTIFACT_MANIFEST_SHA256` from its independently pinned publication.
OpenVINO export and publication live under `openvino/export/`; the legacy
OVMS exporter has been removed. Existing historical HF artifacts are preserved. See
[OpenVINO runtime](openvino/README.md) for artifact and validation requirements.

## Protocol and validation

Send the [JSON fixture](tests/fixtures/forecast-v1.json) to
`/v2/models/timestral/infer` with `Content-Type: application/json`. Standard
metadata and readiness are served by KServe. Tensor names, masks, covariates,
limits, binary encodings, response identity and SDK/client limitations are in
[protocol.md](docs/protocol.md). HTTP deployment acceptance requires a gateway
that bounds actual request bodies, including chunked uploads, to 8 MiB before
SDK decoding.

Native amd64 CI owns heavy builds and checkpoint tests. The integration suite
uses pinned Triton HTTP/gRPC clients against the actual image and an
unchanged same-model upstream reference. CPU and device numerical evidence,
image digests and hardware acceptance remain separate gates. Triton extensions
beyond the tested standard inference operations are not promised.


## Validation records

Earlier image digests and the two model-specific OpenVINO HF bundle
revisions are recorded in [publication receipts](docs/verification/2026-11-01-published-candidates.json).
The OpenVINO image supports either 5M or 209M with its matching verified bundle;
both passed native export, final-forecast and JSON/binary REST/gRPC checks.
Those v1 receipts describe the older bounded runtime; see the OpenVINO v2 documentation for the expanded implementation.
These receipts describe earlier acceptance builds; current tags follow the release scheme above.

The previous bounded-image comparison is retained in the
[2026-11-02 report](docs/verification/2026-11-02-speed-accuracy.md).
The expanded OpenVINO v2 runtime requires matching v2 bundles and new acceptance
receipts; old bounded bundles do not initialize it.

All backends use normal upstream forecasting defaults. There is no retained
bounded compatibility preset. Historical comparisons identify their old source
commit and settings; use the current [benchmark runbook](benchmarks/README.md)
for fresh default-profile measurements.
