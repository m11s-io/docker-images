# Isolated hardware acceptance

Use the normal build workflow to publish the required Timestral flavor. Resolve
its source tag (`sha-<commit>-<flavor>`) to an immutable digest and use that
identity in validation jobs. The separate acceptance-tag workflow is retired.

Check the target's actual GPU memory and utilization, existing reservations,
device-plugin health, and container/device permissions before scheduling. A
time-sliced Kubernetes GPU slot does not reserve GPU memory. Run jobs sequentially
and leave tests pending when memory is insufficient; do not stop existing users'
workloads or add GPU architecture overrides.

Render a job with `render_job.py --variant cpu|cuda|rocm|openvino --image <digest-reference>
--source <commit> --node <explicit-node> --model 5M|209M`. Redirect its JSON to a
local file, inspect it, and run `kubectl --context <target> apply --dry-run=server
-f <file>` before applying. CUDA requires the existing `nvidia` RuntimeClass.
The probe uses the production image's nonroot identity. Use `--device-group` only
for a verified render/KFD device group when required by host permissions.

The ConfigMap contains the probe; its SHA256 is recorded in the Job and report.
The Job has no Service, host mounts, service-account token, or persistent cache.
OpenVINO alone references the existing `timestral-openvino-hf-token` secret in
its initialization container; the probe/server never receives that token. Pass
`--artifact-receipt <json>` containing the selected model's `openvino_profiles`
receipt from `timestral/docs/verification/2026-11-01-published-candidates.json`.
The complete receipt must match. Initialization downloads only that immutable
profile prefix, verifies it with the production verifier, and mounts it read-only.
Profile and download storage are bounded separately, including the 209M bundle. Its dedicated policy admits only DNS and outbound HTTPS. It can download
public revision-pinned checkpoints and expires after 40 minutes. Existing
Timestral services, policies, model caches, and clients remain separate.

The probe starts the production official ModelServer. Its production loader
requires the expected vendor/architecture, GPU parameter residency and FP32
before Ready. A separate negative probe requires missing devices to fail. Ten
synthetic forecasting cases cover short/nonaligned/long histories, masks, grouped
rows, long horizons, numeric/categorical covariates and boolean options. Each is
compared over JSON REST, binary REST and gRPC to independent unchanged upstream
forecasting on the same selected device in the pinned framework build. GPU
references verify FP32 parameter residency. This same-device correctness gate
does not accept CPU/GPU numerical equivalence; historical cross-device failures
remain separate evidence. OpenVINO instead uses an independent CPU reference
with max_context=256 and per_shot_horizon_patches=5, the established 1e-4
conversion tolerance, and bounded fixtures. It also checks production-loader
rejection of the other model identity before readiness and unsupported capability
errors on all three transports. Response model/revision/backend/artifact
identities are checked, including protobuf-valued gRPC parameters. Request IDs, all 21 quantiles, median, levels,
shapes, dtypes and finiteness are checked. The existing CPU acceptance thresholds
are retained (`rtol=atol=1e-5`); any failure needs investigation, not an automatic
tolerance increase. CPU-only image parity is also established in native CI. OpenVINO
conversion tolerance does not change any PyTorch threshold.

Save logs and the `ACCEPTANCE_REPORT` JSON before deleting only the three emitted
resources. Capture the actual Pod imageID and node alongside the report. A failed
job does not restart automatically. Failed or unavailable hardware stays pending;
a successful probe does not authorize stable tags, deployments, or client cutover.
These serial tests are correctness evidence, not sustained performance benchmarks.
