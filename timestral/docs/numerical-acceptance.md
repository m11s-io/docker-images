# Numerical acceptance

Decision: use device-native upstream behavior, with no CPU/GPU equivalence
promise. GPU candidates remain experimental and unpromoted. This selects option
(a) in the rollout plan; it does not adopt either failed cross-device budget.
The machine-readable decision is [numerical-acceptance.json](numerical-acceptance.json).

## Same-device serving correctness

For PyTorch, compare the network service with an independent invocation of the
unchanged pinned upstream forecaster on the same device, model revision, FP32
precision, inputs, masks, covariates and options. Keep rtol=atol=1e-5 for quantiles
and median, checking every element and every case. Quantile levels keep the
standard-client rtol=1e-6/atol=1e-7 check. Shapes, dtypes, finiteness, request ID,
model/revision/backend identity and parameter residency are separate gates.
Bitwise equality is reported where observed; it is not a universal guarantee.

The exact published CPU and ROCm 5M/209M images passed 30 protocol comparisons
per model/backend with zero measured error. ROCm acceptance is limited to the
tested gfx1201 host/container environment. Historical NVIDIA same-GPU diagnosis
also had zero error, but the latest published CUDA digest still awaits target
validation with sufficient VRAM. Unknown image/model/hardware/option identities
have no accepted scope. A passing build or a GPU slot is not acceptance.

## Cross-device compatibility

No cross-device numerical bound is accepted. Device-native means that switching
CPU, CUDA or ROCm can change forecasts, including deterministic differences that
grow in iterative forecasting. A client requiring CPU-equivalent forecasts must
stay on its validated CPU endpoint. Device selection must be explicit, with no
fallback, architecture override, silent precision change or model substitution.
Client owners must assess the intended workload before any eventual GPU cutover.

The original 120 comparisons had 12 failures at the unchanged CPU threshold.
The independent 216-case study rejected the proposed unit-floor budget on all
four model/vendor combinations. Its synthetic input-amplitude alternative also
failed NVIDIA 5M grouped long forecasts and is not a production scale estimator.
Zeros, near-zero values, input units, outliers, missingness and covariates prevent
turning either experiment into a general bound. Do not average failures away or
use the held-out set repeatedly to widen a threshold.

A future cross-device policy is a separate change: define scale from real
observed inputs, handle constant/all-zero/all-masked cases and units, specify
quantiles/median/levels separately, test independent held-out workloads and
retain raw original-threshold results. No new metric module is introduced here,
because this decision adopts no new error formula or cross-device threshold.

## OpenVINO conversion

OpenVINO is a separate bounded conversion scope: B=1, V=1, context<=256,
horizon<=320, no covariates, max_context=256 and per_shot_horizon_patches=5.
Use its model-specific pinned manifest and compare against independent upstream
CPU forecasting configured identically. Retain rtol=atol=1e-4 for quantiles and
median and the stricter quantile-level check above. This is not full-default
PyTorch equivalence. Mismatched bundles must fail before Ready and unsupported
capabilities must fail explicitly, without shortening or substituting requests.

Both exact published OpenVINO bundles passed 24 protocol comparisons, 12
capability rejections and a wrong-model/bundle initialization rejection per model.
Export/final-forecast publication evidence remains valid and is not repeated.

## Evidence and remaining gates

- [Published target validation](verification/2026-11-01-published-target-validation.md)
- [Same-GPU upstream diagnosis](verification/2026-11-01-upstream-device-drift.md)
- [Original hardware failures](verification/2026-11-01-hardware-acceptance.md)
- [Independent budget rejection](verification/2026-11-01-independent-device-budgets.md)
- [Immutable publication receipts](verification/2026-11-01-published-candidates.json)

This documents the numerical claim; it does not establish business forecast
quality, sustained performance, CUDA target availability, deployment acceptance
or client cutover. Stable GPU promotion remains forbidden. CPU/OpenVINO staged
preparation can proceed with their explicit scopes. Rollout, client migration
and retirement each retain their separate approval gates.
