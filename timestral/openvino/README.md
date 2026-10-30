# Direct OpenVINO preview

Experimental, not an interchangeable stable fourth variant. The same KServe
ModelServer and shared handler use OpenVINO Core for neural execution, while
inheriting upstream Timestral scaling, refinement, encoding and forecast loops.
No OVMS process, Python node, MediaPipe graph or pyovms dependency is included.
No reference neural weights or fake model parameters are allocated at runtime.

The only candidate profile family is Timestral-5M revision
`bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f`, source
`a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff`, FP32. It uses explicit
max_context=256 and per_shot_horizon_patches=5. This differs from unrestricted
upstream defaults; compare final forecasts against that exact configuration.

Capabilities: B=1, V=1, 1<=T<=256, 1<=H<=320, no covariates. Grouped rows,
larger contexts/horizons, other model sizes and all covariates fail explicitly.
Both boolean options pass through upstream; their final-forecast acceptance
remains required. No neural PyTorch fallback exists.

New artifact format: `timestral-openvino-profiles-v1`, consisting of
`manifest.json`, `config.json`, `LICENSE`, `README.md` and `block-{1..5}.{xml,bin}`. The manifest records
model/source revisions, FP32, max_context, block size and SHA256 for every file.
Runtime additionally requires its expected manifest SHA256 from trusted,
revision-pinned external initialization. Reject extra/missing files, symlinks,
checksum/revision/profile mismatches before compilation. IR inputs must be
context f32[1,32..256] and observed boolean[1,32..256], with a quantiles
f32[1,H*32,21] output. Only patch-aligned contexts reach those profiles.

Compile settings: CPU, f32, two inference threads, one stream,
ENABLE_CPU_PINNING=false. Validate properties and actual final forecasts in the
pinned 2026.4.1 runtime image; previous OVMS timings are historical evidence,
not direct-runtime performance evidence.

PR #130's reusable direct backend is extracted here with stronger artifact/type
checks. Its throwaway export proof and the old fixed 128->32 publication format
are not promoted into this format. The isolated profile exporter and native CI acceptance job are implemented;
their execution, same-configuration final parity, actual-image REST/gRPC evidence
and separately authorized OIDC publication are still pending. Keep the existing `timestral-openvino.yaml`
workflow identity/trust unchanged until that new publication is validated.

Run `profiles.py` in the frozen `openvino/export` environment on native amd64.
Conversion-only rewrites occur in a fresh temporary source copy and fail on
source drift; reference and runtime workers import the unchanged source in
separate processes. The exporter checks all 21 final quantiles, medians, levels,
short/nonaligned/maximum contexts, missingness, multiple decode blocks and all
four boolean-option combinations before writing a manifest. CI retains the
report separately from runtime artifacts. This is a prepared validation path;
no successful native export or image acceptance is claimed until CI runs.

Converted outputs may retain symbolic dimensions even though every accepted
forecast has fixed row/horizon/quantile dimensions. Startup checks compatible
metadata, then executes every admitted patch-aligned context length (32 through
256) for each of the five profiles and rejects incorrect shapes/dtypes/nonfinite
results before Ready. Every subsequent neural result is checked again. CI retains
both the versioned candidate profiles and their evidence for later publication.
