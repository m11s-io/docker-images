---
license: apache-2.0
tags: [timestral, openvino]
---
# Timestral direct OpenVINO profiles

Model-specific FP32 neural graphs for unchanged upstream source
`a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff`. The exact 5M or 209M checkpoint
and immutable revision are recorded below and in the verified manifest.

The v2 adapter uses normal upstream forecasting defaults and the same supported
request capabilities as the CPU image: batches, grouped variables, longer
contexts/horizons, missing observations, and model-supported numeric/categorical
past and known-future covariates. Existing shared service budgets still apply.
Both forecast options and FP64 normalization remain unchanged upstream operations.
OpenVINO executes the learned neural operations; no PyTorch neural fallback exists.

`timestral-openvino-profiles-v2` contains dynamic context-only/covariate graphs.
`manifest.json` pins model/source revisions, FP32 and every artifact checksum.
Obtain the expected manifest SHA256 from trusted revision-pinned publication.
Old bounded v1 bundles are incompatible with this contract and remain historical.
See the independent final-forecast and actual-image protocol evidence alongside
each published bundle. These artifacts do not authorize a deployment/cutover.
