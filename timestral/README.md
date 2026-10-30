# Timestral standard serving candidate

One official KServe Python ModelServer and shared Timestral handler, with variant
names `cpu`, `cuda`, `rocm`, `openvino`. The handler calls unchanged, pinned
upstream forecasting. Images contain code and dependencies; weights and IR stay
external and revision pinned. Standard ports: REST 8080, gRPC 8081.

**Acceptance is pending.** Existing `/forecast` deployments and legacy
`latest-cpu` / `latest-cuda` aliases must remain available during migration.
No candidate is promoted merely because it builds. See the
[runtime matrix](docs/runtime-matrix.md), [V2 contract](docs/protocol.md) and
[migration/rollback gates](docs/migration.md).

| Variant | Execution | Current status |
| --- | --- | --- |
| cpu | upstream PyTorch CPU | candidate; real-image numerical acceptance pending |
| cuda | upstream NVIDIA CUDA 13.0 | candidate; actual target forecast acceptance pending |
| rocm | upstream HIP/ROCm 7.2, gfx1201 only | experimental; host/device acceptance pending |
| openvino | direct OpenVINO CPU neural profiles, upstream forecasting | experimental bounded 5M; new artifact and image acceptance pending |

The old wrapper and reference tests remain until an authorized client cutover.
[Legacy API documentation](docs/legacy-api.md) describes the preserved historical
contract, not the new Dockerfiles.

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

The OpenVINO preview requires `MODEL_ID=mistralai/Timestral-5M`, its documented
revision, `TIMESTRAL_FORECAST_ARTIFACTS` pointing to a read-only profile bundle and
`TIMESTRAL_ARTIFACT_MANIFEST_SHA256` from its independently pinned publication.
The old OVMS block artifact is not this new artifact format. See
[OpenVINO preview](openvino/README.md) for strict capability limits.

## Protocol and validation

Send the [JSON fixture](tests/fixtures/forecast-v1.json) to
`/v2/models/timestral/infer` with `Content-Type: application/json`. Standard
metadata and readiness are served by KServe. Tensor names, masks, covariates,
limits, binary encodings, response identity and SDK/client limitations are in
[protocol.md](docs/protocol.md). HTTP deployment acceptance requires a gateway
that bounds actual request bodies, including chunked uploads, to 8 MiB before
SDK decoding.

Native amd64 CI owns heavy builds and checkpoint tests. The integration suite
uses pinned Triton HTTP/gRPC clients against the actual candidate image and an
unchanged same-model upstream reference. CPU and device numerical evidence,
image digests and hardware acceptance remain separate gates. Triton extensions
beyond the tested standard inference operations are not promised.
