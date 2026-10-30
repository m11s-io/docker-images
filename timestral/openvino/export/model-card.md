---
license: apache-2.0
tags: [timestral, openvino, experimental]
---
# Timestral-5M direct OpenVINO profile candidate

Experimental FP32 neural profiles for source
`a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff` and checkpoint
`mistralai/Timestral-5M` revision `bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f`.

Use with unchanged upstream forecasting configured with max_context=256 and
per_shot_horizon_patches=5. Supported preview requests: one independent target
row, context<=256, horizon<=320, no covariates. Unsupported requests fail.
Both boolean forecast options remain upstream operations. No 209M, grouped-row,
full-default equivalence, stable promotion or benchmark claim is made here.

`manifest.json` identifies the new `timestral-openvino-profiles-v1` format and
checksums every artifact. Obtain its expected SHA256 independently from trusted
revision-pinned publication. The old fixed-block OVMS artifact is a different
format. See retained independent CI parity and protocol evidence before use.
