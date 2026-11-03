# Published candidate target validation

Status: available targets validated; CUDA pending. No promotion, rollout or
client cutover authorized.

This reuses the image and profile publication receipts in
[2026-11-01-published-candidates.json](2026-11-01-published-candidates.json).
The [target report](archived-details.md) separately records
actual Pod image IDs, model revisions, backend/device, probe identity, test run,
profile initialization identity and protocol results. Publication receipts remain
unchanged. No candidate was rebuilt or republished.

The probe independently invokes pinned upstream forecasting on the same device
as the production server. PyTorch quantiles/median retain rtol=atol=1e-5.
OpenVINO uses max_context=256 and per_shot_horizon_patches=5, with its established
rtol=atol=1e-4 conversion policy. Quantile levels use the existing standard-client
rtol=1e-6/atol=1e-7 threshold; the earlier CPU probe's measured level errors are
zero and also satisfy that tighter bound. This does not adopt a CPU/GPU numerical
compatibility policy or erase historical cross-device failures.

CPU 5M and 209M each passed 30 JSON REST, binary REST and gRPC comparisons; all
quantiles, medians and levels were bitwise equal to independent upstream.
OpenVINO 5M and 209M each passed 24 bounded protocol comparisons, 12 explicit
unsupported-request rejections across the transports, and production-loader
rejection of a mismatched model/bundle before readiness.
ROCm 5M and 209M each passed 30 same-GPU upstream comparisons with zero error
and rejected a hidden accelerator. Neither result accepts
CPU/GPU interchangeability.
CUDA remains pending: the intended NVIDIA target initially had only 745 MiB
free of 16311 MiB, with 100% utilization. The final check left 2065 MiB free
at 0% utilization, still without verified safe headroom for two inference
processes and their workspaces. Existing workloads were not stopped or moved.

The full Timestral and direct-runtime unit regression suite ran natively on
amd64 in the exact published CPU runtime, with test-only packages installed into
temporary storage: 153 passed, 44 skipped. Skips remain opt-in image/vendor tests;
actual target execution is reported separately. This is not a claim that the
frozen Linux environment can execute on local ARM.

An initial CPU probe failed a new gRPC metadata assertion after both REST forms
passed. The pinned KServe decoder preserves protobuf-valued gRPC parameters;
a protocol round-trip regression now verifies their decoding. An initial
OpenVINO initialization failed before Ready because copying directory metadata
onto a root-owned volume mount is forbidden to the nonroot process. The launcher
now copies into an owned child directory, while runtime profiles stay read-only.
These diagnostic failures do not establish a runtime forecast defect. Local raw
logs and Pod identities were saved before removing the failed test resources.

Independent review found no important issues. One deferred minor is stronger
independent enumeration of negative runtime capability cases: the probe currently
selects them using the production validator; separate unit tests assert its
individual bounds.

All 168 forecast comparisons passed. All emitted temporary resources were
removed after collecting results; all 12 plt nodes and three legacy Timestral
pods were Ready at the final check.

All tests use isolated nonroot Jobs, dedicated ConfigMaps/network policies,
revision-pinned external data, bounded ephemeral storage and no host mounts or
service-account token. Only OpenVINO initialization receives the existing
Vault-backed HF secret; the server/probe does not. Existing services, caches,
stable aliases and clients are unchanged. Timings are diagnostic, not sustained
benchmark measurements. Numerical acceptance and benchmarking remain subsequent
gates in the rollout plan.
