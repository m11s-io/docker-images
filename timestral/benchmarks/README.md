# Standard V2 service benchmark

`v2.py` measures network inference over JSON REST, binary REST and gRPC with
`tritonclient==2.73.0` from the existing frozen CPU dev/client lock. It does not
call a forecaster directly. There are no measured speedup or SLO claims yet.

## Comparison identity

Each config pins the model/revision, backend, immutable image/source, actual Pod
image ID receipt, forecast profile and resolved upstream settings. OpenVINO also
pins the artifact commit/prefix/manifest. Every response must match loaded model,
revision, backend, forecast settings and request ID; outputs must have correct
shapes, FP32 storage and finite values. An identity/output mismatch invalidates
the window, even if other requests succeeded.

Use the complete `comparison_key`, which includes model, revision, source,
profile, resolved settings, transport and fixture hash. A profile label alone is
not a comparison key. Never combine 5M and 209M or different fixtures into one
speedup. `upstream-default` CPU/CUDA/ROCm measurements are a separate group from
`bounded-v1` CPU/CUDA/ROCm/OpenVINO measurements.

`TIMESTRAL_FORECAST_PROFILE=bounded-v1` explicitly selects upstream
max_context=256 and per_shot_horizon_patches=5. Existing PyTorch defaults remain
unchanged; OpenVINO resolves its default to bounded-v1 and rejects an explicit
upstream-default request. PyTorch still uses its normal tensor capability limits;
choosing a forecasting preset is not an OpenVINO capability claim. The preset
changes runtime code, so benchmark it only in newly built and validated pinned
candidate images. Earlier published images do not expose this metadata or the
PyTorch preset and must not be relabeled as supporting it.

## Accounting

The isolated schedule uses 10 warmups and three 120-second windows at concurrency
1 per transport/profile/model. Concurrency 2 is measured in one separate
120-second window per transport as admission/backpressure behavior. The service
still owns one execution slot. Each worker has its own connection, and clients
run separately from the server process (the SDKs' protobuf symbols cannot safely
share a process).

Raw request IDs, start offsets, durations, status and error types are retained.
Only successful requests contribute to latency percentiles and successful
throughput; busy and error counts remain visible. Throughput divides by actual
elapsed measurement plus drain time, never a shortened nominal window. An empty
successful sample or exhausted raw sample budget cannot produce an accepted
measurement. The default budget is 250000 raw requests per window, bounded at
1000000 when explicitly configured.

CPU/RSS/thread counters describe the server process; cgroup memory/CPU limits
and throttling include the client in the same container. Node load includes
other workloads. GPU sampling occurs inside the serving process only after it
initializes its own device: framework peaks are cumulative for the server
lifetime, and free/total counters describe the whole assigned physical device.
The wrapper invokes the normal `serving` entry point and changes no inference or
admission code. Latency logging is disabled explicitly; its setting is recorded.
Cold readiness is measured once per profile; the second profile reuses that
Job's model cache. Artifact initialization timestamps come from the collector's
actual Pod receipt. These are shared-host measurements, not isolated hardware SLOs.

## Reproduce on explicitly selected plt hardware

Inspect node/plugin health, reservations and actual VRAM first. Leave unavailable
targets pending. Run serially on each node; separate collectors may run on
independent nodes. Do not stop existing workloads or modify the legacy service.

1. Export the existing locked client environment:

   ```sh
   uv export --frozen --project timestral/dependencies/cpu --only-group dev \
     --no-emit-project --no-annotate --output-file /tmp/timestral-clients.txt
   ```

2. Write the selected OpenVINO model's published receipt to a JSON file when
   applicable; use the existing trusted model-specific profile publication.
   Render with explicit image/source/node/model and one or both comparison
   profiles. OpenVINO accepts only bounded-v1:

   ```sh
   python timestral/benchmarks/render_job.py --variant cpu \
     --image m11s/timestral@sha256:REPLACE_WITH_VALIDATED_DIGEST \
     --source REPLACE_WITH_SOURCE_COMMIT --node REPLACE_WITH_SELECTED_PLT_NODE \
     --model 5M --profile upstream-default --profile bounded-v1 \
     --client-requirements /tmp/timestral-clients.txt > /tmp/timestral-bench.json
   ```

   The placeholders above must be replaced; mutable or malformed identities are
   rejected. For OpenVINO add `--artifact-receipt <model-receipt.json>`. Device
   groups may be supplied only for verified render/KFD permissions.

3. Review the concrete JSON. `collect.py` uses explicit admin@plt, performs a
   server dry-run, applies only the emitted isolated resources, and sends the
   actual Pod imageID/initialization receipt before measurement starts:

   ```sh
   python timestral/benchmarks/collect.py --manifest /tmp/timestral-bench.json \
     --output-dir /tmp/timestral-benchmark-results
   ```

   Repeat `--manifest` for serial tests on the same node. Jobs have a two-hour
   deadline, nonroot/read-only-root security, no host mounts/token, bounded
   ephemeral storage and only the existing initialization secret mechanism.

4. The collector copies the completed result archive while the Pod is still
   alive, verifies every checksum and expected archive path/type, then signals
   collection and removes only that manifest's resources. A failed verification
   retains the resources within their bounded lifetime for recovery. Raw files,
   Pod identity and logs remain local; redact cluster details before public reuse.

Report raw results and failures before drawing comparisons. Keep missing targets,
source/preset changes, node contention and numerical-policy exclusions visible.
No command here promotes images, deploys a service or migrates a caller.
