# Isolated hardware acceptance

Use the normal build workflow's immutable image digest and source commit.
Check actual memory, utilization, device-plugin health and permissions before
scheduling. A GPU allocation is not a VRAM reservation. Do not stop unrelated
workloads or substitute a different device to make a test pass.

Render with `python timestral/tests/hardware/render_job.py --variant
cpu|cuda|rocm|openvino --image <digest> --source <commit> --node <node>
--model 5M|209M`. Inspect the JSON and server dry-run before applying it.
CUDA uses the existing NVIDIA RuntimeClass; ROCm uses verified assigned devices.

OpenVINO additionally requires `--artifact-receipt FILE`, containing a reviewed
publication receipt from the v2 publication workflow: repository, immutable HF
revision, model_id, `standard-v2/<manifest_sha256>` path, manifest_sha256 and
`validated-cpu-parity` status. Old v1 receipts are incompatible. Expected hashes
must come from trusted publication, not from an untrusted bundle itself.
The supplied receipt must exactly match the model's `artifact` entry in the
checked-in [comparison configuration](../../benchmarks/comparison.json).
After v2 publication, verify its provenance and commit the reviewed receipt there
before rendering jobs. An empty entry rejects all supplied receipts; v1 pins
are not substitutes.
The init container downloads only the pinned prefix, verifies every file/model
identity using the runtime verifier, and mounts profiles read-only. It alone
receives the existing HF token; the server/probe does not.

Jobs run nonroot, without a service-account token, host mounts or persistent
model cache. Only emitted Job/ConfigMap/network-policy resources are created.
DNS/HTTPS egress and temporary storage/deadlines are bounded. Existing service
resources and their caches remain separate.

The probe uses unchanged upstream defaults for all backends and identical
fixtures. It checks actual devices/FP32, all21 quantiles, medians, levels,
shapes, finite outputs, identities and HTTP JSON/binary/gRPC behavior. GPU
references use the same device; OpenVINO uses an independent CPU reference and
checks wrong-model bundle rejection before readiness. See
[the numerical policy](../../docs/numerical-acceptance.md) for strict tolerances
and the separately recorded measured5M exception. No request is skipped merely
because it was unsupported by an older OpenVINO profile.

Save logs, `ACCEPTANCE_REPORT`, actual Pod imageID and node before deleting only
the emitted resources. Failed/unavailable cases remain visible. These checks
establish correctness, not sustained throughput or rollout authorization.
