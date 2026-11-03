# Speed and forecast-accuracy comparison

One HTTP client script compares **5M and 209M on CPU, CUDA, ROCm and OpenVINO**.
All eight rows use the same frozen 150 M4 series, last up-to-256 observed training
values, official future test targets, no covariates, FP32 and upstream-default forecasting (checkpoint context and decode settings).
These are public benchmark cases, not guaranteed-unseen pretraining data or a
production-domain quality claim. The [previous bounded comparison](../docs/verification/2026-11-02-speed-accuracy.md) is historical; new default-profile rows require fresh measurements.

Prepare the fixed dataset before any model run:

```sh
python timestral/benchmarks/compare.py \
  --config timestral/benchmarks/comparison.json --prepare \
  --data-dir /tmp/timestral-m4 --output-dir /tmp/timestral-comparison
```

The config then records official-source file hashes and 50 deterministic IDs per
Hourly/Daily/Weekly group. Data stays outside the repository. Preparation refuses
to change a frozen cohort. Never use future test values as request inputs.

Fill each row's exact published image/source, actual Pod imageID, hardware and
reachable endpoint after validation. OpenVINO additionally pins its model-specific
artifact. The standard unversioned V2 route checks loaded revision/backend/default settings
on every response. Client and server run separately; the client needs the existing
frozen dev/Triton HTTP dependency environment, not model weights or KServe imports.

Use existing isolated manifests and the normal image entrypoint, then ordinary
`kubectl port-forward`/`exec`/`cp`. Save Pod identity before running; copy results
before deleting only those temporary resources. No custom launcher or collector.

```sh
python timestral/benchmarks/compare.py \
  --config timestral/benchmarks/comparison.json --only cpu-5M \
  --data-dir /tmp/timestral-m4 --output-dir /tmp/timestral-comparison
```

Each selected row runs 10 warmups and three sequential passes. Scores use the
first prediction once; repeats measure latency and output drift. Per-case JSON
contains predictions, timings, errors and MAE/MASE/sMAPE/pinball/WQL; summary JSON
and CSV retain all eight rows, including pending/incomplete rows. Undefined
scales are null, never a unit-dependent epsilon. Identical saved runs are reused;
a different identity/cohort/script requires a new output directory. Use
`--retry-incomplete --only <row>` after a failure; the prior failed JSON is
preserved before retry. Do not rank rows on
different surviving subsets. This is request latency on the fixed workload, not
a sustained-throughput SLO.

Fill OpenVINO artifact pins from the matching v2 publication receipt before
running. Null artifact pins intentionally prevent reuse of obsolete v1 bundles.
Detailed historical results are in the [evidence archive](../docs/verification/archived-details.md).
