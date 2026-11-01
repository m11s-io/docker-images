# Upstream CPU/GPU drift diagnosis, 2026-11-01

The serving adapter is not the source of the observed long-horizon discrepancy
on the tested hardware and fixtures. The official server is **bitwise identical**
to independent unchanged upstream forecasting on the same GPU across all tested
horizons and all three transports. Independent upstream CPU and GPU forecasts
reproduce the cross-device difference. Both paths are individually bitwise
repeatable in these runs.

## Controlled experiment

Pinned candidate images and model revisions are unchanged from the
[hardware evaluation](2026-11-01-hardware-acceptance.md). No source rewrite,
architecture override, fallback or tolerance change was used. CPU and GPU
references instantiate `TimestralForecaster` directly; neither invokes our
serving adapter. The server loads a separate GPU model in its production process.
All three paths receive identical FP32 input arrays, masks, horizon and options.
CUDA uses the production IEEE FP32 precision policy. Both references are repeated
at every horizon. Quantiles, median and levels are checked separately.

Four model/device combinations (5M/209M on RTX 5060 Ti/gfx1201) were tested at
horizons 32, 64, 128, 256, 320, 512, 768 and 1024. Each server result was compared
with the independent same-GPU reference over JSON REST, binary REST and gRPC:
96 comparisons, all bitwise equal. CPU and GPU repeatability comparisons were
also bitwise equal. The [raw report](2026-11-01-upstream-device-drift.json)
contains exact identities and every metric.

| Model/device | First tested horizon exceeding CPU threshold | Maximum scaled error over all tested horizons |
| --- | --- | --- |
| 5M / NVIDIA | 256 | approximately 1.75e-4 |
| 5M / AMD | 320 | approximately 3.28e-4 |
| 209M / NVIDIA | 320 | approximately 2.62e-5 |
| 209M / AMD | 256 | approximately 2.68e-5 |

Scaled error is `abs(GPU - CPU) / max(abs(CPU), 1)`, evaluated elementwise;
the table uses the maximum across outputs and horizons. These thresholds describe
this fixture, not a universally safe horizon. The maximum is not necessarily at
horizon 1024: the upstream algorithm also depends on the requested horizon.

## Interpretation and acceptance policy

The experiment isolates device-dependent upstream numerical execution, but does
not identify a particular kernel or prove a universal floating-point error bound.
Long-horizon output magnitudes can grow substantially (the 5M fixture reaches
approximately 6850), so an absolute error alone is misleading. Relative error
alone is unstable near zero. Report both absolute and scaled errors.

Keep the same-device serving correctness gate strict (`rtol=atol=1e-5`); all
measured same-device errors here are zero. Treat cross-device compatibility as a
separate gate. A **provisional** cross-device budget of
`abs(GPU - CPU) <= 5e-4 * max(abs(CPU), 1)` covers this measured fixture while
bounding drift to 0.05% for magnitudes above one and 0.0005 below one. This is an
empirical candidate criterion, not a theorem or a promised model-accuracy bound.

Do not enable that budget or promote GPU images from these data alone. Validate
it on independent, diverse histories/scales/missingness/covariates, both model
sizes and sustained runs, then rerun the complete acceptance matrix under an
explicitly adopted numerical policy. Tighten or reject the proposal if those
checks fail. In particular, an absolute floor of one is expressed in input units
and requires review for the intended data scales. The existing CPU-parity gate
and failed hardware evaluation remain unchanged; no stable tags or cutover are
authorized by this diagnostic.
