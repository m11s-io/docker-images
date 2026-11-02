# Numerical scope

Serving correctness and forecast accuracy are different checks. PyTorch service
outputs are checked against independent unchanged upstream on the same device
with rtol=atol=1e-5. OpenVINO uses its established bounded conversion tolerance
rtol=atol=1e-4 for quantiles/median. Quantile levels use rtol=1e-6/atol=1e-7.

There is no general CPU/GPU equivalence promise: the earlier proposed error
budgets failed independent validation. Keep raw results and explicit model,
image, framework and hardware identities. Unknown/new images need validation;
no tolerance is widened for promotion. OpenVINO is required for both model sizes,
within its declared B=1/V=1, context<=256, horizon<=320, no-covariate bounds.

The [single comparison script](../benchmarks/README.md) scores real held-out
future observations. Those quality scores and endpoint timings, not upstream
parity alone, establish the measured model/backend tradeoff. See the historical
[target evidence](verification/2026-11-01-published-target-validation.md) and
[rejected cross-device budgets](verification/2026-11-01-independent-device-budgets.md).
No stable promotion, rollout or client cutover follows from this document.
