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
quantile values outside the original budget; maximum original-budget ratio2.30).
The user approved the increased ceiling on 2026-11-03 after repeated CI measured
88/21504 values outside tolerance, ratio2.2982514 and maximum absolute error0.300293
in the 5M 1024-step blocks case, identically across all three transports.
Medians must still pass the original tolerance. No exception applies to209M,
other cases, wrong shapes, nonfinite outputs or incorrect identities. Forecasts
and the original tolerance remain unchanged; observed divergences stay visible.

For OpenVINO's `maximum-horizon` 1024-step validation case, the maintainer approved
an expanded 28M envelope on 2026-11-04 after
[run 41895638493](https://github.com/m11s-io/docker-images/actions/runs/41895638493).
At most 2.5% of all quantile values may be nonmedian violations, capped at 35 times
the original budget. At most 36/1024 median values may violate it, capped at 0.15
absolute error and 1.1 times the recorded median budget (atol=0.0001,
rtol=0.00014). These are acceptance exceptions, not strict-parity results.
The 123M envelope remains 0.5% nonmedian violations and 60 times the original
budget, with strict medians. Other cases and models retain their existing limits.

The [single comparison client](../benchmarks/README.md) measures speed and scores
real held-out observations. Keep matching profiles, cohort and exact pins for
comparisons. The earlier bounded report is historical; it does not establish
performance for expanded/default execution. Numerical acceptance alone does not
authorize deployment, client migration or retirement of old deployed resources.
