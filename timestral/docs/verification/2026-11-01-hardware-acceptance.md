# Hardware acceptance, 2026-11-01

Status: **not accepted for promotion**. Runtime packaging is fixed; strict
CPU/GPU final-forecast parity at the full supported horizon remains a blocker.

| Backend / hardware | Model | Comparisons passed | Failure |
| --- | --- | --- | --- |
| CUDA / RTX 5060 Ti (sm_120) | 5M | 27 / 30 | horizon 1024, all transports |
| CUDA / RTX 5060 Ti (sm_120) | 209M | 27 / 30 | horizon 1024, all transports |
| ROCm / gfx1201 | 5M | 27 / 30 | horizon 1024, all transports |
| ROCm / gfx1201 | 209M | 27 / 30 | horizon 1024, all transports |

The [raw report](2026-11-01-hardware-acceptance.json) records immutable image,
source, model and probe identities, all measured errors, serial timings and
failed cases. Timings are diagnostic, not a sustained performance benchmark.

Both vendor/device checks and missing-device rejection passed. The production
loader checked FP32 GPU parameter residency before the official KServe server
became Ready. Short, nonaligned and long histories, masked observations, grouped
rows, numeric/categorical covariates and option cases passed over JSON REST,
binary REST and gRPC. Request IDs, all 21 quantiles, median, quantile levels,
shapes, dtypes and finiteness were checked. There were 120 comparisons total:
108 passed and 12 exceeded the unchanged `rtol=atol=1e-5` threshold.

These results do not justify claiming full CPU/GPU interchangeability, a shorter
accepted horizon, or stable GPU tags. Investigate the long-horizon difference
against unchanged upstream CPU and GPU implementations and establish a justified
numerical acceptance criterion before promotion. No tolerance was widened, no
forecast algorithm was changed, and no CPU fallback or architecture override
was enabled.

Actual hardware testing exposed and fixed missing runtime dependencies:
ROCm requires libatomic1; accelerator Triton JIT requires gcc/libc6-dev and
writable compilation caches. Those fixes are merged in PR #138. The corrected
candidate images were published by run 41243130854 from source
`016f45ff0ccb8213c282606be102de5efaa7161c`. CPU 5M/209M and experimental bounded
OpenVINO native acceptance passed independently in run 41241482093. The CPU
transport reference uses direct upstream forecasting with exact saved inputs
in the same image userland; the adapter and worker-thread diagnostic were
bitwise equal to direct upstream in that environment.

Only isolated nonroot Jobs, ConfigMaps and job-specific policies were created
for these tests. No deployment, service, stable alias, client endpoint, legacy
cache or model artifact was changed. Existing endpoint availability was affected
by an independently NotReady node during the final check; no repair or failover
of that infrastructure was attempted by this acceptance work.
