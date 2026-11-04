# Direct OpenVINO serving

Timestral-5M, Timestral-28M, Timestral-123M, and Timestral-209M use the same KServe V2 API, supported requests
and upstream-default forecasting configuration as the normal CPU image.
OpenVINO executes the learned neural operations. Scaling (including FP64
statistics), categorical encoding, refinement and forecast loops remain unchanged
upstream CPU operations, without loading PyTorch neural weights or falling back.

There are no additional OpenVINO single-series, context-256, horizon-320 or
no-covariate restrictions. Batches, grouped variables, missing observations,
numeric/categorical past and known-future covariates and both forecast options
are supported wherever the selected checkpoint supports them. The existing
shared CPU API budgets still apply; see [protocol](../docs/protocol.md).
Defaults come from each checkpoint (currently context 32768 and up to 32 horizon
patches). There is no bounded compatibility preset.

## Artifacts

This runtime requires `timestral-openvino-profiles-v2`: `manifest.json`,
`config.json`, `LICENSE`, `README.md`, `context.{xml,bin}` and
`covariates.{xml,bin}`. Two dynamic graphs cover the context-only and covariate
neural paths. Real group/role IDs, shapes and upstream normalization values
are inputs; graph conversion must not specialize them to the example request.

Pin the expected manifest SHA256 and HF artifact commit independently of the
image digest. All file hashes, model/source revisions and FP32 precision are
checked before compilation. Graph signatures, representative execution and all
subsequent output shapes/dtypes/finiteness are verified. A bundle for one model
cannot serve the other. OpenVINO CPU compilation uses FP32, two threads, one
stream and disabled CPU pinning.

Old published v1 bundles and their bounded benchmark/acceptance receipts remain
historical; they cannot initialize this v2 runtime. Use matching v2 publication
receipts. No deployment or caller cutover follows from artifact publication.

## Validation and publication

Run `export/profiles.py --model-size 5M|28M|123M|209M --output DIR` in the frozen
`openvino/export` environment on native amd64. Conversion uses a fresh isolated
source copy with guarded rewrites; independent reference/runtime workers import
unchanged pinned upstream. All four models must pass full-default final forecasts,
including batches, grouped variables, long contexts/horizons, numeric/categorical
covariates, missingness and forecast options at the established conversion
tolerance (rtol=atol=1e-4). Actual images must then pass HTTP JSON/binary and gRPC
checks against the same CPU defaults. A passing bounded reference is insufficient.

`serving/divergence.py` records explicit model-specific exceptions at horizon
1024 while retaining the original strict error measurements. The 28M median
exception permits at most 11/1024 values outside the original budget, with
rtol=0.00014, atol=0.0001 and an absolute error cap of 0.0065. Other model medians
and other horizons remain strict. Export logs print each case's measurements,
and the final parity report records rejected cases before failing publication.
Across observed CI runners, 28M permits at most 1% nonmedian values outside the
original budget, capped at 20 times that budget; 123M permits at most 0.5%,
capped at 60 times the budget. These exceptions apply only to maximum-horizon
1024 cases. The median absolute cap applies only to original-budget violations.
The separate 28M sinusoidal protocol `blocks` case at horizon 1024 has its own
measured envelope: at most 5% of quantiles outside the original budget, at most
50 times that budget, absolute quantile error at most 1.8, and at most 6.25% of
medians outside the original budget with absolute median error at most 0.2.

Successful main-branch OpenVINO image builds automatically call
`.github/workflows/timestral-openvino.yaml` for verified OIDC profile publication.
The publisher reuses the same run's successful forecast and protocol evidence,
rechecks the shared numerical policy, and resolves the image using its source
commit tag. PRs and `skip_push` builds do not publish profiles. Manual publication
remains available on `main` when an image exists for that commit; alternatively,
dispatch Build and push with `image=timestral-openvino` and `skip_push=false` to
build and publish the image and profiles together.

Each `timestral-standard-publication-<size>` artifact records the image digest,
model revision, HF commit, profiles path and manifest checksum. After all four
models publish, `timestral-openvino-release-<source-sha>` collects those receipts
in `timestral-openvino-release.json` for deployment. A model publication failure
fails the release while allowing the other models to finish; existing remote
bundles are never overwritten. New releases append `standard-v2/<manifest-sha256>/profiles/` and
matching evidence. Existing remote v1/legacy files are preserved. The historical
HF repository name remains for trust compatibility; each manifest records its
actual model identity. Refresh the speed/accuracy report for matching default
settings; earlier bounded speedups are not promises for the expanded runtime.
