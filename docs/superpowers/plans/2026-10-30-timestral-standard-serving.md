# Timestral Standard Serving Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement task by task, with one independent review before merge/deployment. Follow TDD for behavior changes. This document is a plan; it does not authorize executing a new rollout merely by being written.

**Goal:** Serve upstream Timestral through standard KServe V2 on CPU, CUDA and ROCm, with a separately validated OpenVINO variant and no maintained custom HTTP API.

**Architecture:** One model contract and shared upstream forecasting adapter; official KServe Python ModelServer for all four variants, with a directly invoked OpenVINO neural backend for the Intel variant. OVMS is excluded from the target architecture. Hardware-specific images package dependencies, not weights. GitOps selects runtime/image, model revision and device resources.

**Tech Stack:** KServe Python SDK/ModelServer, upstream Timestral, PyTorch CPU/CUDA/ROCm, direct OpenVINO Runtime, uv locks, GitHub Actions, Hugging Face artifacts, KServe ServingRuntime/InferenceService and Argo CD.

**Spec:** `docs/superpowers/specs/2026-10-30-timestral-standard-serving-design.md`

## Global Constraints

- Agreed image variants: `cpu`, `cuda`, `rocm`, `openvino`. Dockerfiles use those suffixes. Tags: version-<variant>, sha-<commit>-<variant>, and latest-<variant> only after acceptance.
- Product root: `timestral/`. Keep one shared `.dockerignore`, explicit per-Dockerfile COPY statements, no weights/caches/credentials in the context.
- Standard API: KServe V2 REST and gRPC. Do not add custom `/forecast`, custom FastAPI routes or hand-written HTTP serving. Upstream KServe's internal FastAPI dependency is fine.
- Use unchanged pinned upstream Timestral; no third_party edits, fork, global monkey-patch or copied forecasting algorithm.
- Never silently substitute model size, inference precision, device or forecasting features. Unsupported requests fail explicitly. GPU failure must not fall back to CPU.
- Preserve the existing 209M service until same-model final forecasts, client migration and rollout checks pass. Do not reuse 5M block speedups as full 209M forecast claims.
- CPU/CUDA/ROCm use one shared model implementation and upstream full forecasting. OpenVINO changes only verified neural execution, preserving final forecast semantics.
- Model artifacts and runtime images are independently pinned by immutable revisions/digests. Runtime selection is independent of 5M/28M/123M/209M size.
- Use runtime-compatible Python. Verify published KServe release dependencies against the inspected 0.21.0 source (>=3.10,<3.14). Resolve Python 3.12 as the initial shared candidate, subject to compatible CUDA/ROCm vendor images. Verify the direct OpenVINO wheel supports the selected Python version; no embedded OVMS Python ABI is involved. Do not force 3.15.2 through unsupported requirements.
- Run heavy image/model tests in GitHub CI or explicitly selected cluster hardware, not local ARM emulation. Hardware validation is required before promoting CUDA/ROCm/OpenVINO.
- GitOps changes follow kubernetes/registry/AGENTS.md: render catalogs, validate resource layout, review Argo diff, confirm context, use Vault/External Secrets and leave prod untouched initially.

## Review Focus

- A request accepted by two variants must mean the same final forecasting operation, including refinement, symmetric averaging, clipping and covariate encoding.
- Model artifacts/runtime imports must not accidentally use PyTorch neural execution in an OpenVINO performance claim, or CPU in a GPU claim.
- Malformed/oversized tensors, NaNs, wrong masks, unsupported covariates and incompatible artifacts must fail predictably without exposing secrets or series data.
- GPU architecture, driver, framework and Python compatibility must be proven on actual hardware; package installation and torch.cuda.is_available alone are insufficient.
- Concurrent standard-server requests must respect bounded admission/model execution and preserve request/response ordering; cancellation must not oversubscribe a running model.

## Target source structure

```text
timestral/
  Dockerfile.cpu
  Dockerfile.cuda
  Dockerfile.rocm
  Dockerfile.openvino
  .dockerignore
  serving/
    contract.py              standard-tensor validation and result representation
    upstream.py              unchanged Timestral loading and forecast invocation
    kserve_model.py          official Model lifecycle/predict binding
    __main__.py              official ModelServer entry point
  dependencies/
    cpu/{pyproject.toml,uv.lock}
    cuda/{pyproject.toml,uv.lock}
    rocm/{pyproject.toml,uv.lock}
  openvino/
    backend.py               direct OpenVINO neural execution for shared handler
    export/                  isolated conversion/parity/publication tools
    tests/
    pyproject.toml,uv.lock
  tests/                     shared unit/protocol/equivalence/device contracts
  benchmarks/                standard-client workload and evidence collection
  docs/                      architecture, capabilities and migration guide
```

Do not duplicate the current experimental `ovms/` code into `openvino/`; extract reusable export/backend code after auditing PR #130. Do not carry over OVMS Python-node bindings, MediaPipe graphs, pyovms dependencies or the OVMS base image. Preserve the publishing workflow filename `timestral-openvino.yaml` because external HF trust pins it. Folder renaming must not change issuer/repository/branch/workflow claims. Historical experiment evidence stays in docs; no benchmark result is a production capability declaration.

## Task 1: Audit current candidate and choose compatible runtime pins

**Files:** `timestral/docs/runtime-matrix.md`, `timestral/docs/migration.md`; inspect current Dockerfiles/locks, PR #130 and local read-only upstream sources.

**Interfaces:** A runtime matrix records exact server/framework/Python/device/image pins, artifact format and validation status for each variant; it is the authority for later Dockerfiles.

- [ ] Record current branch/PR/CI state before editing. Earlier CPU/CUDA images use custom FastAPI; PR #130 packages only a bounded 5M OVMS candidate. Do not merge or deploy that candidate as a completed architecture migration.
- [ ] Verify official KServe package/version against local commitabc6c47ab4af588e40c67372b4835122234f6f74. Inspect `python/kserve/kserve/model.py`, `model_server.py`, `protocol/infer_type.py`, and official custom_model examples; use public InferRequest/InferResponse APIs.
- [ ] Confirm built-in HuggingFaceTimeSeriesModel still lacks Timestral support; if upstream adds it, evaluate using it instead of maintaining our binding.
- [ ] Resolve immutable CPU/CUDA/ROCm base images and framework wheels against actual cluster GPU models. Record exact ROCm-supported architectures and host driver/device-plugin prerequisites; do not assume all AMD GPUs work.
- [ ] Resolve runtime-compatible Python and locks without overriding upper bounds. Reject a proposed release when published package metadata differs materially from inspected source; record the selected source/release explicitly.
- [ ] Write migration sequencing, rollback images and preserved original endpoint/model revisions. Commit the reviewed matrix and pins before implementation.

## Task 2: Define one versioned forecasting tensor contract

**Files:** `timestral/serving/contract.py`, `timestral/tests/test_contract.py`, `timestral/docs/protocol.md`, standard REST/gRPC fixture files.

**Interfaces:** `parse_forecast(request: InferRequest) -> ForecastInputs`; `encode_forecast(result: ForecastResult, request_id: str, model_name: str) -> InferResponse`. Keep pure array validation separate from the shared KServe binding and backend execution.

- [ ] Write failing tests for required/missing/duplicate/unknown tensor names, dtype/rank errors, mixed booleans in numeric input, invalid horizons, missing masks, budget violations and output metadata ordering.
- [ ] Specify required tensors: context FP32[B,V,T], observation_mask BOOL[B,V,T], prediction_length INT64[1]. Masked values use finite placeholders; convert missingness internally using upstream arguments, never JSON NaN.
- [ ] Specify optional numerical past/known covariates FP32[B,C,T] and FP32[B,C,T+H], categorical equivalents FP64 to preserve upstream code precision, and matching BOOL masks for each present covariate tensor. Reject masks without their tensor; convert masked covariate values to upstream missing-value representation. Do not invent new categorical encoders.
- [ ] Specify optional symmetric_averaging and clip_nonnegative BOOL[1] tensors, defaulting to upstream true. Outputs: quantiles FP32[B,V,H,21], median FP32[B,V,H], quantile_levels FP32[21]. Model/revision identity is available through standard metadata/documented response parameters.
- [ ] Retain initial work budgets from the existing API:8MiB request, batch8, total rows32, context32768, horizon1024, output elements1000000. Enforce limits before expensive allocation/inference; document any tighter hardware/runtime capability separately.
- [ ] Implement the pure contract, preserve request IDs, map invalid/unsupported/busy conditions to appropriate standard runtime errors. Do not create a new error HTTP endpoint.
- [ ] Run unit tests; validate fixtures through official V2 encode/decode paths for JSON and binary REST/gRPC. Commit only after malformed cases and all 21 quantiles are checked.

## Task 3: Replace custom HTTP serving with official KServe ModelServer

**Files:** `timestral/serving/{upstream,kserve_model,__main__}.py`, `timestral/tests/test_kserve_model.py`, selected CPU dependency lock.

**Interfaces:** `TimestralModel(kserve.Model)` implements load/readiness and predict using InferRequest/InferResponse. `UpstreamForecaster.load(settings)` pins upstream source/weights and selected device; `forecast(ForecastInputs) -> ForecastResult` invokes unchanged upstream forecast().

- [ ] Write failing lifecycle, request-ID, numerical result, device mismatch, invalid model, initialization failure and concurrent-admission tests.
- [ ] Load upstream TimestralForecaster from pinned weights without copying preprocessing, encoding, clipping or autoregressive/refinement code.
- [ ] Implement the official Model lifecycle and public V2 predict interface; start with ModelServer().start([model]) using documented server flags. The server supplies HTTP/gRPC, health and metadata endpoints.
- [ ] Bound execution/admission deliberately: one loaded model per worker, one inference slot initially; serialize model execution without blocking the server event loop. A cancelled request must not release capacity before its underlying computation stops. Test the actual SDK's supported execution/error behavior.
- [ ] Preserve redacted errors, model-cache handling and request budgets from the current API where applicable. Do not import or run our old FastAPI app.
- [ ] Compare final forecasts against unchanged upstream on the same model/revision/options. Cover short/nonaligned/long histories, missing data, batches/variates, multiple decode blocks, covariates, categorical encoding and both boolean options. Check median and quantile levels as well as quantiles.
- [ ] Add `timestral/tests/integration/test_triton_client.py` using pinned `tritonclient.http` and `tritonclient.grpc` against the actual KServe image. Verify readiness, model metadata, inference request IDs, tensor names/shapes/dtypes and numerical outputs for both transports; test HTTP binary tensors if used by existing clients. Record supported client versions and explicitly exclude unimplemented Triton extensions from compatibility claims.
- [ ] Run real standard REST and gRPC tests against the server. Commit once the CPU reference contract and Triton client inference compatibility are proven.

## Task 4: Package CPU, CUDA and ROCm using the same handler

**Files:** `timestral/Dockerfile.{cpu,cuda,rocm}`, `timestral/dependencies/{cpu,cuda,rocm}/`, shared `.dockerignore`, variant build/device tests and CI jobs.

**Interfaces:** All three images launch the same `serving` module and expose the Task 2 contract. Device-specific dependencies/base layers differ; handler and upstream forecasting source do not.

- [ ] Write failing image contracts for the official KServe entry point, immutable sources, shared handler COPY paths, nonroot execution, hardware wheel selection, no baked-in weights/tokens and no custom /forecast route.
- [ ] Build CPU with CPU PyTorch; CUDA with a matched NVIDIA CUDA/PyTorch stack; ROCm with a matched AMD ROCm/PyTorch stack. Use separate frozen locks when needed, a shared source tree and a single shared Docker ignore file.
- [ ] Accept explicit device configuration. For CUDA/ROCm require the expected framework backend, accelerator identity and requested device; fail startup when unavailable. ROCm's PyTorch CUDA-compatible API naming is not proof of an NVIDIA device.
- [ ] Run actual CPU inference in CI. On dedicated NVIDIA/AMD runners or controlled cluster jobs, run real final forecasts, confirm device residency and compare to CPU/upstream within an explicitly justified tolerance. Installation-only smoke tests cannot promote a GPU image.
- [ ] Exercise unsupported AMD architectures and missing drivers as clear startup failures. Do not add broad GPU overrides or host-driver installation to images to conceal unsupported hardware.
- [ ] Keep hardware acceptance reports and digests; publish/promote only accepted variants. Commit the three images and tested routing without changing cluster deployments yet.

## Task 5: Complete the OpenVINO variant behind the same contract

**Files:** Extract reusable candidate export/backend code from `timestral/ovms/` into `timestral/openvino/`; replace `Dockerfile.ovms` with `Dockerfile.openvino`; extend shared `timestral/serving/{upstream,kserve_model,__main__}.py` for explicit backend selection; update export profiles/manifest, tests, workflow paths and docs.

**Interfaces:** The same `TimestralModel` and ModelServer entry point from Task 3 serve all variants. Explicit backend selection loads `timestral/openvino/backend.py`, which uses `openvino.Core` to compile and execute verified profiles directly. Shared request validation and upstream forecasting produce the same `ForecastResult` and `InferResponse`; the backend owns no HTTP/gRPC server.

- [ ] Audit candidate evidence and retain reusable export/parity tests. Remove OVMS-specific serving glue from the target: Python-node API, MediaPipe graphs, server flags, pyovms and OVMS image dependencies. Existing fixed 128->32 exports are experimental, not complete forecasting artifacts.
- [ ] Write failing parity/capability tests before extending profiles. Current proof supports only5M, one series, context<=256 with explicit max_context256 and per_shot_horizon_patches5. Do not advertise this as equivalent to full upstream defaults or209M.
- [ ] Load configuration directly without allocating reference neural weights or fake parameters. Use an explicit CPU device contract. Preserve upstream scaling/refinement and forecasting algorithms; retaining PyTorch for those operations is allowed, while neural fallback is forbidden.
- [ ] Determine export coverage needed for the accepted common feature matrix: model sizes, grouped/multiple rows, contexts, horizons and covariates. Add only verified dynamic dimensions/profiles, fail unsupported cases, and test final forecasts against same-model upstream.
- [ ] Preserve FP32 initially. Configure the directly compiled OpenVINO model with an initial two inference threads, one stream and ENABLE_CPU_PINNING=false on the shared node. Validate supported properties against the pinned OpenVINO package; benchmark this direct-runtime configuration rather than inheriting OVMS performance claims.
- [ ] Package `Dockerfile.openvino` with the same official KServe server/entry point and compatible Python as the other variants, adding direct OpenVINO runtime dependencies and the backend. Test actual-image REST/gRPC through the shared handler, prove OpenVINO neural execution with no PyTorch neural fallback, and reject invalid IR names/types/shapes, profiles, checksums or revisions before Ready.
- [ ] Publish new versioned HF profile artifacts through existing OIDC only after validation, independently of runtime image publication. Do not overwrite the old artifact contract silently.
- [ ] Keep OpenVINO explicitly experimental with a capability matrix until accepted baseline feature coverage and same-model final-forecast parity pass. A preview must not be presented as an interchangeable fourth stable variant.

## Task 6: Integrate naming, build selection and publication

**Files:** `.github/workflows/build.yaml`, existing Timestral export workflow, hardware/image validation workflows, `scripts/image_tags.py` callers/tests, Timestral README and docs.

**Interfaces:** Variant names are exactly cpu/cuda/rocm/openvino throughout Dockerfiles, selectors and tags. No serving-runtime/hardware naming mixture in public variants; runtime details are documented separately.

- [ ] Write failing routing tests: shared serving edits validate all applicable variants; backend-only edits validate their consumer; `.dockerignore`, lock, Dockerfile and export-profile changes trigger required validation.
- [ ] Update build matrix and manual dispatch choices. Keep existing CPU/CUDA tag compatibility during migration, but publish changed serving contracts first under immutable candidate/version tags. Do not silently repoint latest-cpu/latest-cuda for incompatible clients.
- [ ] Retain the exact `timestral-openvino.yaml` filename for HF trust; update paths/concurrency only when consistent with pinned claims. Give id-token:write only to the publishing job, never ordinary validation.
- [ ] Keep heavy export dependencies separate from serving dependencies; avoid duplicated export/contract code and stale generated config. Remove obsolete prototypes only after their coverage is replaced; preserve useful historical evidence in docs.
- [ ] Scan every public staged/history artifact for credentials and private infrastructure details. Runtime images may not contain model-cache data, tokens or private series.
- [ ] Run all relevant unit/protocol tests, actionlint (account for existing runner-label support), Dockerfile lint and real-image checks. Obtain independent review; resolve important findings before publishing stable tags.

## Task 7: Add standard KServe deployment definitions and hardware acceptance

**Repository:** `kubernetes/registry`; follow its AGENTS.md. Files: appropriate Timestral ServingRuntime/InferenceService resources, ExternalSecrets, storage/policies and contract tests; update catalog templates only when needed and render generated catalogs.

**Interfaces:** All four variants run the same KServe Python ModelServer and shared model handler, selecting backend/device/resources explicitly. OpenVINO uses its direct-runtime image and pinned profile bundle; there is no OVMS process or service. Every InferenceService uses the same model name and V2 contract, with supported capabilities declared honestly.

- [ ] Create namespaced ServingRuntime definitions where reusable; separate model identity from runtime/image selection. Use explicit runtime selection rather than ambiguous automatic format matching.
- [ ] Keep weights/IR in revision-pinned external storage with verified initialization. Use Vault-backed secrets only where needed; avoid secrets in Docker layers or committed manifests.
- [ ] Configure standard readiness, nonroot security, disabled token automount, bounded storage/memory, network policies and accelerator requests. Schedule NVIDIA/AMD workloads to nodes compatible with validated vendor images/device plugins; Intel CPU selection is explicit.
- [ ] Review resource headroom and Argo diffs; run render/layout/admission checks, distinguishing baseline failures from regressions. Initial changes affect plt only.
- [ ] Deploy new services alongside the existing 209M endpoint. Verify actual loaded model, device, image digest and final predictions via REST/gRPC on each hardware target; keep unavailable hardware marked pending.
- [ ] Benchmark same-model final forecasting using matching requests, resource budgets and concurrency over multiple sustained and sequential windows. Preserve raw timings, correctness checks, client/server throttling, node load and model options.

## Task 8: Migrate clients, retire obsolete API and finish documentation

**Files:** Timestral migration/capability docs, affected client configuration, obsolete API code/tests and build entries only after acceptance.

- [ ] Inventory clients of custom /forecast and map their existing requests/options to the standard V2 contract. Preserve required features, errors and observability; verify request/response examples with real clients.
- [ ] Select an accepted candidate model/runtime without changing model size silently. Confirm rollback image/model/artifact pins and the old service remain available during migration.
- [ ] Roll clients gradually to the new standard endpoint; observe readiness, errors, latency and result parity. Retire the old service only after accepted migration evidence and explicit cutover authorization.
- [ ] Remove the custom FastAPI wrapper/obsolete dependencies and duplicated benchmark prototypes only once unused. Do not remove upstream KServe's own FastAPI dependency or delete reusable reference tests accidentally.
- [ ] Document final stable image tags, supported hardware/features, artifact formats, protocol schema and known limitations. Keep preview/unsupported variants out of the stable equivalence claim.
- [ ] Save independent review findings, hardware acceptance, final benchmarks and rollback instructions; verify no unrelated changes are included.

## Execution order and completion criteria

Tasks 1–4 establish the portable standard-serving baseline. Task 5 is a distinct Intel optimization deliverable and must not delay or redefine baseline forecasting semantics. Tasks 6–8 integrate and migrate only accepted variants. Reuse existing candidate work where correct; do not redo successful evidence or treat it as broader support than tested.

Done means: standard REST/gRPC clients can make the same documented forecasting request on each promoted hardware variant; outputs match upstream for the selected model/options within justified tolerances; device execution is demonstrated; images are reproducible and contain no weights/secrets; and legacy clients have an approved migration/rollback path. Packaging success, one 5M block benchmark, or an available GPU alone is not completion.

## Plan-only handoff

This plan supersedes further architectural expansion of the bounded OVMS candidate. Existing experimental deployments remain untouched. Review the runtime/contract decisions before implementation; source inspection and current proofs are evidence, not permission to present unsupported runtime versions or hardware as working.
