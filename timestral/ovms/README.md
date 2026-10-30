# OVMS forecasting variant

Build from the `timestral` context with `Dockerfile.ovms`:

```sh
docker build -f timestral/Dockerfile.ovms -t timestral-ovms:test timestral
```

The image extends pinned OVMS with the adapter and unchanged pinned upstream
Timestral source. Its Python3.12 dependency lock is separate from the existing
CPU/CUDA API environment. No FastAPI endpoint or model weights are included.

Mount the validated five-profile forecast artifact (config.json and block-1
through block-5 XML/BIN pairs) at `/models/forecast`. This is a new artifact
contract; the existing fixed128-to32block bundle is insufficient.

The standard KServe model name is `timestral`. Inputs are context FP32[1,1,T],
observation_mask BOOL[1,1,T] and prediction_length INT64[1]. Current bounds are
history1..256, forecast1..320, one series, no covariates. Missing values use the
mask and finite context values. Symmetric averaging and nonnegative clipping
are enabled using upstream behavior. Outputs are quantiles, median and
quantile_levels. This is bounded5M support, not a209M service replacement.

The dedicated CI workflow builds the actual derived image and tests final
forecasts against unchanged upstream through standard REST. Publication and
cluster replacement are separate from this validation workflow.
