# Isolated hardware acceptance

Run `timestral-candidates.yaml` manually on `main`. Download the
`timestral-acceptance-<variant>` identity artifacts. These are unpromoted test
images; use their immutable digest and source commit, never a moving tag.

Check the target's actual GPU memory and utilization, existing reservations,
device-plugin health, and container/device permissions before scheduling. A
time-sliced Kubernetes GPU slot does not reserve GPU memory. Run jobs sequentially
and leave tests pending when memory is insufficient; do not stop existing users'
workloads or add GPU architecture overrides.

Render a job with `render_job.py --variant cuda|rocm --image <digest-reference>
--source <commit> --node <explicit-node> --model 5M|209M`. Redirect its JSON to a
local file, inspect it, and run `kubectl --context <target> apply --dry-run=server
-f <file>` before applying. CUDA requires the existing `nvidia` RuntimeClass.
The probe uses the production image's nonroot identity. Use `--device-group` only
for a verified render/KFD device group when required by host permissions.

The ConfigMap contains the probe; its SHA256 is recorded in the Job and report.
The Job has no Service, host mounts, service-account token, secrets, or persistent
cache. Its dedicated policy admits only DNS and outbound HTTPS. It can download
public revision-pinned checkpoints and expires after 40 minutes. Existing
Timestral services, policies, model caches, and clients remain separate.

The probe starts the production official ModelServer. Its production loader
requires the expected vendor/architecture, GPU parameter residency and FP32
before Ready. A separate negative probe requires missing devices to fail. Ten
synthetic forecasting cases cover short/nonaligned/long histories, masks, grouped
rows, long horizons, numeric/categorical covariates and boolean options. Each is
compared over JSON REST, binary REST and gRPC to unchanged upstream CPU forecasting
in the same pinned framework build. Request IDs, all 21 quantiles, median, levels,
shapes, dtypes and finiteness are checked. The existing CPU acceptance thresholds
are retained (`rtol=atol=1e-5`); any failure needs investigation, not an automatic
tolerance increase. CPU-only image parity is separately established in native CI.

Save logs and the `ACCEPTANCE_REPORT` JSON before deleting only the three emitted
resources. Capture the actual Pod imageID and node alongside the report. A failed
job does not restart automatically. Failed or unavailable hardware stays pending;
a successful probe does not authorize stable tags, deployments, or client cutover.
These serial tests are correctness evidence, not sustained performance benchmarks.
