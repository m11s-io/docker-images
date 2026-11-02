# Numerical scope

Serving correctness, forecast accuracy against future truth and endpoint speed
are separate checks. All backends use normal upstream defaults and the shared
KServe V2 request contract. OpenVINO has no additional request-shape or covariate
restrictions; checkpoint capabilities and shared service budgets still apply.

PyTorch service outputs are compared with unchanged upstream on the same device
at rtol=atol=1e-5. OpenVINO records strict quantile/median agreement at
rtol=atol=1e-4; quantile levels use rtol=1e-6/atol=1e-7. There is no general
CPU/GPU bitwise-equivalence promise.

The [full untuned assessment](verification/2026-11-02-openvino-full-divergence.md)
records the user-accepted 5M 1024-step tail exception separately from strict
results. Only reviewed cases qualify, within the measured envelope (<=0.5% of
quantile values outside the original budget; maximum original-budget ratio2.1).
Medians must still pass the original tolerance. No exception applies to209M,
other cases, wrong shapes, nonfinite outputs or incorrect identities. Forecasts
and the original tolerance remain unchanged; observed divergences stay visible.

The [single comparison client](../benchmarks/README.md) measures speed and scores
real held-out observations. Keep matching profiles, cohort and exact pins for
comparisons. The earlier bounded report is historical; it does not establish
performance for expanded/default execution. Numerical acceptance alone does not
authorize deployment, client migration or retirement of old deployed resources.
