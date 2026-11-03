# OpenVINO with normal CPU capabilities

## Objective

Timestral-5M and Timestral-209M on direct OpenVINO must accept the same valid
KServe V2 requests and use the same forecasting defaults as the normal PyTorch
CPU image. No additional OpenVINO restrictions on batch, variables, history,
horizon or model-supported covariates. This supersedes the bounded-preview
requirements of the earlier OpenVINO design, not its historical evidence.

The user explicitly requested CPU-equivalent functionality and a lean implementation.

## Meaning of parity

- Use the same pinned upstream source, model revisions, FP32 and unchanged
  `TimestralForecaster` algorithms. Defaults come from the checkpoint/upstream,
  not the current OpenVINO override of context 256 / five horizon patches.
- Support batches, grouped variables, missing observations, numeric and
  categorical past/known-future covariates wherever that checkpoint supports
  them, both forecast options and multi-block decoding.
- Preserve existing shared CPU API validation: batch ≤8, total target/covariate
  rows ≤32, input context ≤32768, horizon ≤1024, tensor bytes ≤8 MiB and output
  elements ≤1,000,000. These are existing service budgets, not new OV limits.
  Upstream's normal trained-context truncation remains identical on both.
- Unsupported checkpoint features and invalid requests fail as on CPU. No
  special OpenVINO rejection for a CPU-valid request, silent clipping, splitting
  of interacting variables, precision substitution or PyTorch neural fallback.
- Same protocol, shapes, quantile levels and metadata; forecasts pass the
  existing OpenVINO conversion tolerance (rtol=atol=1e-4). Do not widen it to
  obtain a pass. Numerical parity is distinct from forecast accuracy.

## Approach

Extend the existing direct OpenVINO neural-block adapter and exporter. Keep
forecast preparation, scaling, categorical handling, autoregression and output
processing inherited from upstream. Export graph inputs for actual grouping,
roles and known future values instead of hardcoding a single target row.
Use dynamic dimensions for CPU-valid shapes; graph branches may be separated
where upstream has genuinely different context-only/covariate paths.

A native conversion check must establish which dimensions/branches survive
conversion without specialization. Dynamic horizon is preferred; if conversion
requires fixed block horizons, cover the complete upstream-used range inside
the artifact, without a public restriction or wrong padding semantics. Choose
the simplest passing representation based on that check.

Rejected: merely raising preview caps (still incomplete), removing checks over
unchanged artifacts (incorrect), PyTorch fallback (not direct OpenVINO), a new
generic export/runtime framework (unnecessary).

## Delivery

Version new artifacts separately from the old bounded bundles, verify their
identity and graph contract, validate both checkpoints against independent
CPU references through all three transports, publish immutable candidates,
then refresh speed/accuracy results for the new default behavior. Old bounded
results remain historical. No deployment or caller cutover is included.
