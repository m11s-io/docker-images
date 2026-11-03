# Full OpenVINO versus CPU divergence assessment

Both models completed the full existing expanded export matrix (78 option/case combinations), plus four option combinations for a sinusoidal series with context 65 and horizon 1024. Every case ran over HTTP JSON, HTTP binary and gRPC. Numerical mismatches were measured without early termination. No tolerance, precision, input limit or forecast algorithm was changed to make the assessment pass.

| Model | Cases | Requests | Quantile values¹ | Outside original tolerance | Affected cases | Median values outside |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 5M | 82 | 246 | 339,570 | 336 (0.099%) | 4 | 0 |
| 209M | 82 | 246 | 339,570 | 0 (0.000%) | 0 | 0 |

¹ Counts use one copy of each forecast, not three copies from transports. All 492 requests returned valid finite FP32 outputs of the expected shapes and identities. Forecasts were byte-identical across all three transports. Quantile levels were identical to CPU. Original quantile/median acceptance: `abs(actual-reference) <= 0.0001 + 0.0001*abs(reference)`; level acceptance unchanged at rtol=1e-6/atol=1e-7.

## Observed differences

- **5M:** all 78 original cases stayed within tolerance on plt-eng-1. The four added periodic 1024-step cases exceeded it: 104/21,504 quantile values with symmetry off and 64/21,504 with symmetry on, for each clipping choice. All medians stayed within tolerance; maximum median absolute difference was 0.00004866.
- In those affected 5M cases, maximum absolute quantile differences were 0.39844 without symmetry and 0.19995 with symmetry. Their reference values were approximately 4473.10 and 2293.33 respectively (about 0.009% relative at those locations). The largest absolute difference across all 5M cases was 0.79590 against 8972.03, still within the original combined tolerance.
- **209M:** all 82 cases stayed within the original tolerance. Maximum absolute quantile difference was 0.11426 against -6143.34 (about 0.00186%); maximum median absolute difference was 0.000005238.
- Pure relative maxima were 4.92% for 5M and 5.78% for 209M at reference magnitudes 0.00008379 and 0.000006571. Near-zero denominators inflate these percentages; retain the absolute allowance rather than judging those percentages alone. Per-case maximum/mean/p99 absolute and relative measurements, reference magnitudes, and violation counts are in the JSON/CSV.

## Separate CI evidence

- Native hardware for the complete matrix: plt-eng-1, Intel Core i7-13700T; PyTorch 2.13.0+cpu/OpenVINO 2026.4.1, two threads. Both default model settings were context32768/decode32. The matrix used staged source on the existing runtime userland, not a newly published image.
- [5M CI](https://github.com/m11s-io/docker-images/actions/runs/41513808156/job/125512467224) stopped on 2/21,504 quantile values in a 1024-step export case: maximum failing difference 0.958984 against 8973.5508 (0.010687% relative). This runner-specific failure is additional evidence; CI did not run the remaining export cases or image protocol checks after it failed.
- [209M CI](https://github.com/m11s-io/docker-images/actions/runs/41513808156/job/125512467140) passed its complete export matrix and all 38 actual-image protocol tests. Do not claim 5M CI passed or silently relax its gate.

## Scope and interpretation

Divergence is concentrated in a small fraction of 5M long-horizon quantile values on these inputs; all tested median forecasts remained inside the original tolerance. These synthetic-reference comparisons measure numerical agreement, not forecast accuracy against future truth. They do not establish a production error bound or full-domain equivalence. The old bounded M4 accuracy report remains historical; no new accuracy result is inferred here.

The implementation assessed is PR #163’s normalized-neural graph approach (commit c13973c plus a readiness-only malformed-graph check). The uncommitted output-transform experiment was discarded before this assessment. Upstream FP64 preprocessing remains unchanged; learned neural layers execute in OpenVINO. Full per-request reports and raw quantile predictions are retained at `/Users/al/Work/repo/m11s/.superpowers/evidence/timestral-openvino-cpu-parity/divergence`; their checksums and exact artifact/model identities are in the JSON. No output was discarded because it exceeded tolerance.

## Acceptance decision

The user accepted the documented small 5M tail divergence after reviewing the
full untuned assessment. The original strict rtol/atol and violation counts remain
reported. A separately named exception accepts only reviewed 5M 1024-step cases,
with no more than 0.5% tail values outside the original budget and a maximum
original-budget ratio of 2.30 (initial native maximum 2.08457). On 2026-11-03 the
user accepted the increased ceiling after repeated CI measured 88/21504 values
outside tolerance, ratio2.2982514 and maximum absolute error0.300293 in the 5M
1024-step blocks case across JSON, binary HTTP and gRPC. Median values must still
meet the original budget. Other models/cases and invalid outputs receive no
exception. This is numerical acceptance, not a forecast-accuracy claim.
