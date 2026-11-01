# Timestral Published Candidates to Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task by task, with one independent review before integration. Use TDD for behavior changes. Read the status and evidence before doing work; do not repeat completed exports, builds or experiments without a new reason. The user requested local `main`, normal protected integration, and terminal-only work (no browser).

**Goal:** Turn the published Timestral candidates into explicitly accepted, measured, safely deployable services, then migrate clients with a verified rollback.

**Architecture:** Keep the existing shared official KServe ModelServer and unchanged upstream forecasting. Treat image publication, same-device correctness, cross-device numerical compatibility, performance, deployment and client cutover as separate gates. Deploy accepted variants beside the old service; keep OpenVINO's narrower capabilities explicit.

**Tech Stack:** KServe V2 REST/gRPC, pinned upstream Timestral, PyTorch CPU/CUDA/ROCm, direct OpenVINO Runtime, uv, GitHub Actions, HF OIDC, Kubernetes/Argo CD, Vault/External Secrets.

**Spec:** `docs/superpowers/specs/2026-10-30-timestral-standard-serving-design.md`.

**Previous plan:** `docs/superpowers/plans/2026-10-30-timestral-standard-serving.md`. This document replaces its execution checklist for the remaining work; the architecture constraints remain binding. The subsequent user request added OpenVINO 209M alongside 5M. It did not authorize advertising unverified OpenVINO features or retiring the old service.

## Where we are now

**Implemented, tested and published candidates exist. The running legacy service has not been migrated. There are no stable-promotion or cutover claims.**

| Variant | Published image | Model evidence | Remaining acceptance limits |
| --- | --- | --- | --- |
| CPU | Yes | Native 5M/209M final forecasts and JSON REST/binary REST/gRPC passed against direct upstream | Exact deployment digest/target smoke test, sustained measurements and migration still needed |
| CUDA | Yes | 5M/209M actual NVIDIA inference; server versus independent upstream on the same GPU was bitwise equal | Cross-device numerical policy unaccepted; latest published digest needs target revalidation before promotion |
| ROCm | Yes | 5M/209M actual gfx1201 inference; server versus independent upstream on the same GPU was bitwise equal | Same numerical-policy gap; other AMD architectures and host combinations are not accepted |
| OpenVINO | Yes | Separate 5M and 209M bundles passed native export parity and actual-image JSON/binary REST/gRPC; both bundles published and remotely verified | Experimental: B=1, V=1, context<=256, horizon<=320, no covariates; no full-default equivalence claim |

### Completed work: do not rebuild it from scratch

- [x] One official KServe Python ModelServer, shared tensor contract, handler, readiness, metadata and redacted errors; no new application-owned `/forecast` route.
- [x] FP32 context, explicit observation mask, horizon, masked numeric/categorical covariates and boolean options; quantiles, median, levels and request IDs preserved.
- [x] Input/work budgets, single-slot admission, cancellation-safe execution, explicit device checks and no GPU-to-CPU fallback.
- [x] Four Dockerfiles and frozen environments. Images contain neither model weights nor credentials. Accelerator runtime fixes include ROCm `libatomic1`, required JIT compiler packages and writable JIT caches.
- [x] Direct OpenVINO neural execution, no OVMS in the target runtime, no neural PyTorch fallback. Scaling/refinement/forecast loops remain upstream.
- [x] Model-specific 5M/209M profile checks, exact manifest/checksum/revision verification, and rejection before Ready for incompatible artifacts.
- [x] Same-run profile export/final forecast/protocol gates, append-only content-addressed HF publication under the existing OIDC workflow identity, legacy artifacts preserved.
- [x] Four candidate image publications and two HF profile publications; all image digests inspected directly in the registry.
- [x] Hardware and numerical investigations recorded; temporary acceptance Jobs, ConfigMaps and job-specific policies removed.
- [x] PR #130 closed as superseded OVMS architecture; #141 merged as `6d68b10c3a544693fbea1f6fb0d0bc5cd0bf6262`.

### Exact published references

The machine-readable source of truth is `timestral/docs/verification/2026-11-01-published-candidates.json`. Publication source is `6d68b10c3a544693fbea1f6fb0d0bc5cd0bf6262`.

All images use repository `m11s/timestral`:

| Variant | Image digest |
| --- | --- |
| cpu | `sha256:74fc93989f8b71bc97e41cd61122114326de21e0779180f05b27dfc463ce56a1` |
| cuda | `sha256:ad9d5a3d65e1895cc03b22c28c3290b0230773d522f54041da94eed1a180ba67` |
| rocm | `sha256:0d30377978d0191831e1b2d146decb37feb0c791210207b588d919f351f58291` |
| openvino | `sha256:5719f642b6f750dd9d26585776c0949667d7aca2788ad460dc13416c0bbcb494` |

The existing private HF repository remains `m11s-org/Timestral-5M-OpenVINO-experimental` to preserve existing trust. Its historical name does not identify the model inside a versioned bundle.

| Model | HF commit | Bundle prefix / manifest SHA256 |
| --- | --- | --- |
| 5M | `4ef5a7e934791901667df7c69f3b902c025e290a` | `standard-v1/2365ee36bb28855be4417de39ad79fac73892fe2d0a98fb7e31e4f4352fdd2b1` |
| 209M | `0ed8d879c4b52b7e138b66cc98f8d91a45136b8c` | `standard-v1/9203e3c04af76fab1ffde055a9358b1417519c56d87f399d7a232afa57921ba1` |

Mount the selected prefix's `profiles/` as the runtime profile directory. Its final path component is the expected manifest SHA256. Match `MODEL_ID` and `MODEL_REVISION` exactly:

- 5M: `mistralai/Timestral-5M`, revision `bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f`.
- 209M: `mistralai/Timestral-209M`, revision `9874d252ab0aae16f7f7c999f98f98d6ad7d8365`.

Do not copy an earlier 5M export into a 209M deployment. Runtime images and model bundles are separately pinned.

### What the numerical tests mean

The comparison tests were written in this repository; they are not an official Mistral certification suite. They call the original pinned `TimestralForecaster.forecast()` directly and compare its outputs with the network service or another device.

1. Original hardware matrix: 120 CPU-versus-GPU comparisons, 108 passed, 12 exceeded `rtol=atol=1e-5`, exclusively the 1024-step case across three transports/four model-device combinations.
2. Controlled diagnosis: 96 server-versus-independent-upstream comparisons on the same GPU were **bitwise equal**, across eight horizons. CPU and GPU repeats were also individually bitwise equal. Direct upstream CPU/GPU calls reproduced the difference; no serving-adapter bug was identified in that experiment.
3. Independent follow-up: 216 cases across nine history families, scales 0.001/1/1000, horizons 160/1024, both models and vendors. The proposed `5e-4 * max(abs(CPU), 1)` budget failed all four combinations. An input-amplitude-based experimental metric also failed NVIDIA 5M grouped long forecasts. **Neither budget is adopted. Do not turn this proposal into a passing release gate.**
4. OpenVINO conversion uses the separately established `rtol=atol=1e-4` for quantiles/median; protocol evidence records it, and the publisher checks the policy and model identity. This is not a relaxation of CPU/CUDA/ROCm thresholds.

Evidence to read:

- `timestral/docs/verification/2026-11-01-hardware-acceptance.{md,json}`
- `timestral/docs/verification/2026-11-01-upstream-device-drift.{md,json}`
- `timestral/docs/verification/2026-11-01-independent-device-budgets.{md,json}`
- `timestral/docs/verification/2026-11-01-published-candidates.json`
- `timestral/docs/runtime-matrix.md`, `timestral/docs/migration.md`, `timestral/openvino/README.md`

Publication runs: image run **41328095351**, profile run **41328090420**. Both succeeded. The profile run includes fresh CPU5M/209M and OpenVINO5M/209M validation before both OIDC uploads. OpenVINO has 40 export/final-forecast comparisons plus 38 actual-image protocol cases per model.

Last local regression run: **139 passed, 44 skipped**, 15 legacy/publication tests and 10 packaging tests passed. Skips are opt-in actual-image/vendor tests, not new hardware proof.

## Immediate handoff / first action

PR **#143**, branch `docs/timestral-publication-results`, contains the publication receipts, independent-budget diagnostics/results and current status docs. At handoff preparation it was open with auto-merge enabled. This plan and the original plan/spec are being added to that same PR; do not create a competing Timestral PR or resurrect #130. Verify its current state before proceeding.

- [ ] Run `gh pr view 143 --json state,mergeCommit,statusCheckRollup` and inspect all results.
- [ ] If merged, `git fetch origin main` and fast-forward local main when possible; otherwise finish its required checks through ordinary protection. No force push or admin bypass.
- [ ] Read the references above and the original design. Confirm the publication receipts are present in the checkout.
- [ ] Run `git status --short` in each repository. Preserve unrelated DeepSeek edits, unrelated plans/notes, caches and any user's new work. Never stage the whole workspace.
- [ ] Inspect cluster/node/plugin health afresh. Prior restarts interrupted jobs and temporarily affected an engineering node; historical Ready status is not current evidence.

## Global constraints

- Variants stay exactly `cpu`, `cuda`, `rocm`, `openvino`; same official KServe V2 contract and shared handler. No OVMS revival, custom HTTP API, copied forecasting algorithm or upstream source patch.
- No silent substitution of model, device, precision, options or capabilities. No CPU fallback or architecture override. Existing GPU acceptance is only for the tested NVIDIA sm_120 and AMD gfx1201 environments.
- Keep weights/IR outside images. Use frozen locks, exact image digests and model/artifact commits. Keep `timestral-openvino.yaml` and existing HF trust identity intact.
- Heavy native/model tests run on amd64 CI or explicitly selected cluster hardware, not local ARM emulation.
- Keep `rtol=atol=1e-5` unchanged for existing PyTorch acceptance until an explicitly documented new policy is validated. Do not widen a tolerance merely to make known failures pass.
- Published candidates are not stable releases. No stable alias update, prod rollout, client cutover or legacy retirement is authorized by writing this plan.
- Preserve the old 209M image `m11s/timestral@sha256:18fdc4b87b50dbdc389cc528110e7d856b54aa657512fd21a869eee33131fd03`, its model revision and separate cache for rollback.
- Follow `kubernetes/registry/AGENTS.md`; confirm context, leave prod untouched, render catalogs and review Argo diffs. The existing Timestral Argo Application auto-syncs its resource directory: adding manifests there can deploy them immediately.
- Temporary tests must be bounded, nonroot, no host mounts/tokens, and cleaned up after logs, identities and results are saved. GPU time-slicing slots do not reserve VRAM.

## Review focus

1. Small/large measurement scales, zeros and grouped long forecasts must not be hidden by a unit-dependent error floor; Task 2 owns these tests.
2. A 5M/209M or HF revision/manifest mixup must fail before Ready, without fallback; Tasks 1 and 4 own exact-published-artifact tests.
3. OpenVINO must not receive full-default equivalence or speedup claims from a different model, forecast configuration, or neural fallback; Task 3 owns benchmark identity tests.
4. Cold starts, cancellation, concurrent requests and node restarts must not oversubscribe execution, leak credentials or lose a verified rollback; Tasks 3–5 own these tests.
5. Adding files to an auto-synced Argo directory must not accidentally replace the legacy endpoint before approval; Tasks 4–6 own separate paths/names and migration guards.

## File map for remaining work

Repository paths below are relative to `m11s-io-github/docker-images` unless marked Registry. Extend existing modules; do not duplicate forecasting or artifact verification.

| Area | Files / responsibility |
| --- | --- |
| Existing target smoke tests | `timestral/tests/hardware/{probe.py,render_job.py}`; exact image/device/protocol evidence |
| Existing numerical diagnostics | `timestral/tests/hardware/{drift.py,cross_device.py}` and their unit tests |
| Explicit numerical policy | Create `timestral/docs/numerical-acceptance.md`; create `timestral/tests/hardware/numerical_policy.py` only after a policy is selected |
| Matched forecasting configuration | Modify `timestral/serving/{upstream.py,kserve_model.py}` only if needed for the explicit bounded comparison preset in Task 3; create `timestral/tests/test_forecast_profile.py` and extend existing `timestral/tests/test_kserve_model.py` |
| Standard benchmark | Create `timestral/benchmarks/v2.py` and `timestral/tests/test_v2_benchmark.py`; retain the old benchmark as historical/legacy evidence |
| New staged deployment | Registry: `apps/timestral-standard/deployments/ai/resources/{runtimes,workloads,storage,secrets,policies}/`; separate from the existing auto-synced resources |
| New Argo entry | Registry: `template/timestral-standard.yaml`, generated `clusters/plt/timestral-standard-ai.yaml`; no automated child sync initially |
| GitOps regression tests | Registry: create `scripts/tests/test_timestral_standard.py`; retain existing `test_timestral_kserve.py` and `test_timestral_comparison.py` |
| Evidence | `timestral/docs/verification/` for portable numerical/image evidence; Registry `docs/verification/` for cluster-local details, redacted before any public reuse |
| Migration | `timestral/docs/migration.md`, Registry `apps/timestral-standard/README.md`; client files only after inventory identifies them |

## Task 1: Close integration and validate the exact published deployment inputs

**Interfaces:** Consume `2026-11-01-published-candidates.json`. Produce a target report keyed by image digest, model ID/revision, backend/device, artifact commit/prefix/manifest SHA, source commit and test run. Do not rewrite publication receipts as a promotion report.

- [ ] Finish the Immediate handoff checks and integrate PR #143 normally.
- [ ] Reuse `render_job.py` to render separate 5M and 209M tests using the latest published CPU/CUDA/ROCm digests. Generalize its device-independent parts for CPU/OpenVINO rather than copying a new job launcher. Extend `resources(variant, image, source, node, model, device_groups=(), artifact=None) -> list[dict]`; OpenVINO consumes a model-specific receipt from `openvino_profiles`, while other variants reject an artifact override.
- [ ] Add failing tests that reject a mutable tag, mismatched model/bundle, missing trusted manifest digest and missing/wrong hardware. Keep the previous rejection tests.
- [ ] Add the minimal CPU/OpenVINO job support, authenticated private-profile initialization through existing approved secret mechanisms, and explicit model selection. The diagnostic must make GPU-property/missing-GPU checks conditional on GPU backends; OpenVINO references must use `max_context=256`, `per_shot_horizon_patches=5` and the established conversion policy. Reuse `validate_preview_request()` for capability rejection rather than duplicating its bounds. Never place credentials in a ConfigMap/image/log.
- [ ] Run unit tests on the native CI environment: `uv run --frozen --project timestral/dependencies/cpu python -m pytest timestral/tests/test_openvino_profiles.py timestral/tests/hardware -q`. Expected: pass; hardware execution remains a separate test.
- [ ] Dry-run the exact manifests against `admin@plt`, inspect VRAM/RAM/CPU headroom, then run serially per target. For GPU, same-device upstream correctness and historical CPU-difference evidence must be reported separately; do not label the known cross-device failures passed.
- [ ] Test mismatched OpenVINO5M/209M bundles before Ready, missing accelerator rejection, actual JSON/binary/gRPC responses, loaded identity and parameter/device residency. Store Pod imageID and actual initialization revisions.
- [ ] Save results and remove only the emitted temporary resources. Commit tests/docs/evidence; no new publication is needed unless implementation changed.

**Done when:** deployment inputs are revalidated by exact digest/revision on the intended target, or unavailable targets are explicitly pending. Existing successful export/CI evidence is reused, not erased.

## Task 2: Decide a defensible numerical compatibility policy

**Interfaces:** Consume the three numerical studies above. Produce `timestral/docs/numerical-acceptance.md` with separate same-device correctness and cross-device compatibility decisions. A machine-readable policy must contain `status`, `scope`, `metric`, `threshold`, `evidence`, and `exclusions`; `status=accepted` is forbidden without validated evidence.

- [ ] Reproduce the independent study only as needed to confirm a changed framework, target or candidate. Do not rerun the original sine fixture expecting it to establish a general bound.
- [ ] Keep same-device server/upstream checks strict and preserve the bitwise-equality evidence. Investigate any newly observed same-device discrepancy as a serving defect before discussing tolerance.
- [ ] Choose explicitly between (a) documented device-native behavior with no CPU-equivalence promise, or (b) a scale-aware cross-device error policy justified for intended workloads. Record the choice and its consequences; do not claim the original full CPU-equivalence gate passed.
- [ ] Before implementing (b), define how scale is computed from real observed inputs, including all-zero/constant/masked inputs. Synthetic generator amplitude is not a production estimator. Specify quantiles, median and levels separately, with precise units and relative/absolute treatment.
- [ ] Write failing metric tests for scale 0.001/1/1000, zeros, near-zero outputs, outliers, all masked data, signed series, multiple variates and categorical/numeric covariates. Test that a failed output cannot be hidden by a mean over outputs or cases.
- [ ] Implement only the selected policy in `numerical_policy.py`, retaining the raw error metrics and original-threshold results. Default to unaccepted when identity/scope is unknown.
- [ ] Validate on independent held-out fixtures, both models/vendors, all supported options and decode boundaries. Run repeats to separate nondeterminism from deterministic drift. The held-out set must not be used repeatedly to widen the policy.
- [ ] Run the complete actual-image matrix under the explicit policy and obtain review. If it fails, keep GPU experimental and record the blocker; CPU/OpenVINO staged work can continue independently.
- [ ] Commit the decision and evidence. Never silently replace historical failed reports or update stable GPU aliases as a side effect.

**Done when:** the compatibility claim is explicit, justified and tested, or a documented blocker remains with no promotion. This task is not permission to change upstream algorithms or model precision.

## Task 3: Build a fair standard-protocol benchmark and measure candidates

**Interfaces:** `run_benchmark(config: dict) -> dict` in `timestral/benchmarks/v2.py`. Config pins endpoint, transport, model/image/artifact identities, forecasting profile, fixture, warmup count, window duration and concurrency. Output includes raw per-request timings/statuses plus success/busy/error counts, latency percentiles, throughput and measured resources.

- [ ] Write failing tests for percentile units, failed/busy requests excluded from successful throughput, request-ID correlation, identity/config mismatches and rejection of an empty successful sample. Add cancellation/concurrency tests against the real server's one-slot admission contract.
- [ ] Implement JSON REST, binary REST and gRPC clients using the existing pinned client environment. Do not benchmark Python direct calls and label them service latency.
- [ ] Establish two explicit comparison groups: unrestricted CPU/CUDA/ROCm; and the OpenVINO-compatible bounded profile. Never compare different model sizes or present bounded versus unrestricted forecasting as equivalent work.
- [ ] If runtime configuration is needed, add one named `bounded-v1` comparison preset mapping to upstream `max_context=256` and `per_shot_horizon_patches=5`, without changing existing CPU/GPU defaults. Reject an incompatible OpenVINO preset. Record resolved settings in response/report metadata and add load/identity tests before code changes.
- [ ] Run `uv run --frozen --project timestral/dependencies/cpu python -m pytest timestral/tests/test_v2_benchmark.py -q` on native CI. Expected: deterministic metric/identity tests pass.
- [ ] Run both 5M and 209M, same inputs/options/configuration, with 10 warmup requests and three 120-second measured windows at concurrency 1. Measure concurrency 2 separately as admission/backpressure behavior, not a promised 2-slot throughput mode.
- [ ] Capture CPU threads/limits, RSS/peak memory, VRAM, node load, throttling, cold-start/artifact initialization, image/model pins and raw timings. Confirm neural device/backend on each target. Record missing hardware as pending.
- [ ] Save a comparison report. Do not assert a winner or latency SLO without measured results; do not reuse old OVMS block speedups as final-service evidence.

**Done when:** same-model, same-operation sustained measurements exist for accepted scopes and can be reproduced from pinned config. No stable release requires an invented performance number.

## Task 4: Prepare separate plt GitOps definitions without automatic rollout

**Repository:** `kubernetes/registry`; read its `AGENTS.md` before edits.

**Interfaces:** Consume validated digests/model/profile pins and measured resources. Produce explicitly selected namespaced ServingRuntimes/InferenceServices in the separate `timestral-standard` app, plus an Argo diff and rollback record. The old `timestral` resources remain unchanged.

- [ ] Write failing `test_timestral_standard.py` checks for explicit runtime/model selection, immutable pins, separate resource names/cache, no prod catalog entry, no child automated sync, and preserved legacy resources.
- [ ] Add CPU and bounded OpenVINO5M/209M definitions first. GPU definitions may be prepared but must stay unscheduled/unpromoted until Task 2 and target checks allow them.
- [ ] Use nonroot UID/GID10001, no token automount, dropped capabilities, read-only root, bounded writable cache/tmp/JIT paths and verified external initialization. Size CPU/memory/storage from Task 3, including simultaneous download/verification and 209M profile footprint.
- [ ] Match model ID/revision, HF commit/prefix and trusted manifest SHA. Reference Vault-backed External Secrets through existing approved stores; never invent or commit a placeholder credential.
- [ ] Expose standard HTTP8080/gRPC8081 with correct model readiness. Require an HTTP gateway predecode body limit of 8MiB; the SDK alone does not establish that boundary. Preserve the server's positive bounded gRPC receive limit.
- [ ] Restrict ingress/egress, device requests, runtimeClass and node selectors explicitly. Device-plugin capacity alone does not prove safe shared GPU headroom. Keep CPU pinning disabled/two threads/one stream for the established OpenVINO comparison configuration.
- [ ] Add `template/timestral-standard.yaml` without automatic child sync. Run `make render-catalog`, `make check-rendered`, `make check-resource-layout`, and the affected unittest suite. Expected: no new failures; document unrelated baseline failures separately.
- [ ] Review `argocd app diff timestral-standard-ai` plus the source diff. Verify the existing app/endpoint/cache and prod are unaffected. Obtain independent review of the concrete manifests and rollback steps.
- [ ] Commit/push the reviewable GitOps change through normal protection. Do not merge into an already auto-synced legacy resource path to bypass the rollout gate.

**Done when:** concrete manifests, admission/render evidence, Argo diff and rollback are reviewable. No new service is considered deployed by writing manifests.

## Task 5: Authorize and verify a side-by-side plt rollout

**Interfaces:** Consume reviewed Task 4 resources. Produce a rollout report with actual loaded identities, standard endpoints, device, numerical scope, sustained results and rollback instructions.

- [ ] Present the exact plt diff/resource impact and rollback for rollout approval. A restart of critical infrastructure or client cutover is not included in this approval.
- [ ] Confirm current context and node/plugin health. Sync only the new app after approval; preserve the original209M endpoint and caches.
- [ ] Verify cold-start/readiness, model/device/image/artifact identity, exact-image REST/binary/gRPC results, capability rejection and malformed-request redaction through the intended gateway.
- [ ] Exercise request-size limits before decoding, cancellation/admission, model-load failures, missing/wrong artifact/device and a controlled pod restart. Do not restart shared servers for a Timestral test.
- [ ] Repeat Task 3 measurements through the deployed endpoints. Compare results with the isolated baseline and inspect throttling/node contention.
- [ ] Save evidence, including failures. Roll back only the new app if validation fails; do not repoint clients. Keep unavailable GPU promotion pending.

**Done when:** accepted-scope new services are observable and verified beside legacy, with rollback tested. Deployment alone does not authorize client migration.

## Task 6: Inventory clients, approve cutover, then retire legacy

**Interfaces:** Consume accepted endpoint/capability/rollback evidence. Produce a client inventory, per-client V2 translation, approved cutover and final supported-capability docs.

- [ ] Inventory managed configurations and obtain endpoint-owner traffic/unmanaged-caller evidence. The earlier repository scan found no configured product caller; that does not prove there are no clients.
- [ ] For each caller, pin model size/options/features and endpoint/rollback config. Write failing translation tests for masks, numeric/categorical covariates, booleans and response shape/ID/error handling before implementation.
- [ ] Implement the minimal V2 client/configuration changes using pinned standard clients. Reject incompatible OpenVINO requests; do not silently shorten context/horizon or substitute5M for209M.
- [ ] Verify the real client side by side against the selected accepted endpoint. Record readiness/errors, numerical policy, latency and rollback behavior.
- [ ] Present the concrete caller list, rollout order and rollback; obtain explicit cutover approval. Roll gradually and observe before proceeding.
- [ ] Update stable tags only for separately accepted image/model/hardware scopes. Maintain the distinction between device-native correctness and cross-device compatibility.
- [ ] Remove the old service/custom wrapper/obsolete dependencies only after caller and traffic evidence establishes they are unused and retirement is explicitly authorized. Do not remove upstream KServe's internal FastAPI dependency.
- [ ] Publish final capability, artifact, endpoint, numerical and rollback documentation. Keep narrower/experimental variants clearly marked.

**Done when:** migrated clients and rollback are verified, unsupported claims are excluded, and any legacy retirement is separately authorized and evidenced.

## Completion and non-goals

The immediate next implementation job is **Task 1**, followed by a numerical-policy decision and matched benchmarking. CPU/OpenVINO staged deployment preparation need not wait indefinitely for a general CPU/GPU equivalence claim, but GPU promotion must remain honest about its accepted scope.

This plan does not require expanding OpenVINO beyond its published preview to finish the staged rollout. Full batches/variates/covariates/context32768/horizon1024 for OpenVINO would be a separate export/profile/backend validation project, not a documentation change.

The project is not done merely because images exist or tests compare correctly on one device. Final completion requires accepted scopes, reproducible performance evidence, safely deployed services, verified real clients, explicit cutover and preserved rollback. Keep any unmet gate visible.
