# Timestral speed and forecast accuracy — 2026-11-02

Objective: compare Timestral 5M and 209M on all four required backends through the standard KServe V2 interface, using real future observations as forecast targets. All eight correctness checks and comparison rows completed.

| Backend | Model | p50 ms | p95 ms | MASE ↓ | sMAPE % ↓ | WQL ↓ | Errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cpu | 5M | 17.12 | 25.74 | 2.027954 | 5.915960 | 0.037318 | 0 |
| cpu | 209M | 320.72 | 416.65 | 1.946965 | 5.371626 | 0.034720 | 0 |
| cuda | 5M | 10.84 | 13.82 | 2.027954 | 5.915960 | 0.037318 | 0 |
| cuda | 209M | 21.11 | 26.22 | 1.946965 | 5.371627 | 0.034720 | 0 |
| rocm | 5M | 11.03 | 13.02 | 2.027953 | 5.915961 | 0.037318 | 0 |
| rocm | 209M | 23.71 | 26.60 | 1.946967 | 5.371626 | 0.034720 | 0 |
| openvino | 5M | 13.51 | 18.69 | 2.027955 | 5.915960 | 0.037318 | 0 |
| openvino | 209M | 227.68 | 355.48 | 1.946967 | 5.371627 | 0.034720 | 0 |

209M reduces macro MASE by 3.99% and WQL by 6.96% versus 5M on this cohort (CPU scores). Backend score differences are tiny numerical differences; they do not establish an accuracy winner between runtimes.
Lowest measured median latency: cuda 5M (10.84 ms). See both latency columns when selecting a model; this is one fixed workload on the hardware below, without repeated independent runs or confidence intervals.

## Protocol and limits

- Frozen public M4 cohort: 50 Hourly, 50 Daily, 50 Weekly series; official train/test split, file hashes and IDs in the accompanying JSON. No future test observations entered requests. Public benchmark data may have appeared in pretraining.
- Same FP32 requests: B=1, V=1, last up-to-256 training values, no covariates, bounded-v1 (context 256, five horizon patches), both boolean options true. Official forecast horizons: 48 / 14 / 13. MASE uses the full training history and official seasonal frequency.
- Each row: 10 warmups, three sequential passes, 450 successful measured requests. Accuracy uses the first pass once and averages each frequency equally. All rows have the identical 150-case cohort; zero request errors and zero undefined metric values.
- Latency includes the standard HTTP request and output decoding, excludes scoring, downloads and model startup. Client and server share the container and CPU budget. These measurements do not establish sustained throughput, concurrency capacity, cold-start latency or a production SLO.
- CPU and OpenVINO: plt-eng-1, Intel Core i7-13700T, two model threads, container CPU limit 3. CUDA: plt-gpu-2, RTX 5060 Ti (sm120), ComfyUI temporarily paused. ROCm: plt-gpu-3, gfx1201; one allocated AMD GPU. Different hardware means backend latency differences are not software-only comparisons.
- OpenVINO requires B=1, V=1, context ≤256, horizon ≤320 and no covariates. Unsupported requests are rejected; this bounded comparison does not prove full-default feature parity.
- All eight exact-image correctness probes passed against independent upstream references, including HTTP JSON/binary and gRPC. OpenVINO wrong-bundle/capability rejection and GPU missing-device rejection also passed. Numerical agreement is separate from the forecast-quality scores above.

## Reproduction and evidence

- Frozen serving source: `c6d10649195102f3eab0b1a5cdce8b8af7166969`. Image/model/artifact pins, actual Pod imageIDs and per-frequency metrics are in the JSON; all metrics are in the CSV.
- Raw predictions, timings, Pod identities, logs, exact temporary manifests and publication receipts are retained outside Git at `/Users/al/Work/repo/m11s/.superpowers/evidence/timestral-2026-11-02-c6d1064`. Each final row’s SHA256 is in the JSON/CSV.
- Reproduce using the committed `timestral/benchmarks/compare.py` and retained comparison configuration with the exact images and ordinary temporary serving Pods. Client dependencies come from the frozen CPU lock. Dataset file hashes are verified before requests.
- Results support model/backend selection on this cohort. No service migration, stable-tag promotion or production cutover is implied.
