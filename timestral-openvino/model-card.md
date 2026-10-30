---
library_name: openvino
license: apache-2.0
base_model: mistralai/Timestral-5M
tags:
  - time-series
  - openvino
  - experimental
---
# Timestral-5M OpenVINO experimental neural block

This is a fixed-shape FP32 export of the single-block neural prediction path
from [Mistral AI Timestral](https://github.com/mistralai/timestral), under Apache-2.0.
It is experimental. It does not implement the complete Timestral forecasting API,
forecaster orchestration, multi-block refinement, covariates, or dynamic shapes.
It must not be treated as a drop-in replacement for the upstream forecaster.

## Contract

- `context`: FP32 `[1,128]` context values, with missing values replaced by zero.
- `observed`: BOOL `[1,128]` observation mask.
- `quantiles`: FP32 `[1,32,21]` raw-space neural-block predictions.
- Quantile levels: `quantiles.json`; CPU inference precision hint: `f32`.
- IR: `model/1/model.xml` and `model/1/model.bin`, without FP16 weight compression.

The source is pinned to `a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff`, and upstream
weights to `mistralai/Timestral-5M` revision
`bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f`.
The export applies guarded nonoverlapping-unfold and boolean-cummax compatibility
rewrites in an isolated source copy. The numerical reference is unmodified upstream.

## Validation and limitations

`validation.json` records OpenVINO CPU parity; `ovms-validation.json` records real
KServe v2 REST inference through pinned OVMS. Both cover seeded random, sinusoidal,
constant, scattered-missing and leading-missing examples across all 21 quantiles,
using `rtol=1e-4, atol=1e-4`. `validation-fixtures.json` contains synthetic inputs
and reference outputs. These checks demonstrate parity for these examples, not
forecast quality, arbitrary-input correctness or a performance improvement.

Reports record observed architecture/CPU and CI provenance. No native Intel
hardware or Intel performance validation is claimed. Follow the upstream model's
intended uses and limitations. No private or production time-series data is used.

`SHA256SUMS` covers every published file except itself. For deployment, pin the
immutable HF revision recorded by the publishing workflow, not the moving `main`.
The source license is included as `LICENSE`.
