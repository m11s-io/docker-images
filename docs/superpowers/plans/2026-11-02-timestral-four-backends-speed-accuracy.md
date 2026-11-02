# Timestral Four Required Backends and Model Comparison Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` inline. This replaces the previous rollout execution plan. Keep the work small: one shared serving implementation, one comparison script, existing operational tools, one focused review before integration. Do not restart the previous benchmark-framework work.

**Goal:** Deliver working Timestral-5M and Timestral-209M services through the same standard KServe V2 interface on **CPU, CUDA, ROCm and OpenVINO—all required**; produce a reproducible comparison of their **forecast accuracy against real future observations and speed on the same workloads**, then migrate safely from the legacy service.

**Architecture:** Keep the official KServe ModelServer, shared handler and unchanged upstream forecasting. Use direct OpenVINO for its neural execution. Reuse the existing image, artifact verification and isolated hardware-test paths; compare endpoints with one small standard-client script.

**Tech Stack:** Existing pinned Timestral/KServe, PyTorch CPU/CUDA/ROCm, direct OpenVINO, Triton HTTP client, NumPy, existing GitHub Actions and plt GitOps.

**Spec:** `docs/superpowers/specs/2026-10-30-timestral-standard-serving-design.md`, amended to make OpenVINO required and the final speed/accuracy comparison explicit.

## Starting point: what exists and what is missing

| Area | Current evidence | Missing |
| --- | --- | --- |
| Serving | Four Dockerfiles, shared official V2 handler, external model weights, no fallback | Finish a lean reviewed integration; validate the final pinned dependency/image snapshot |
| Model sizes | 5M and 209M implemented | Complete the same comparison for both sizes on every required backend |
| Published candidates | Four images and both OpenVINO bundles recorded in `timestral/docs/verification/2026-11-01-published-candidates.json` | Fresh images only where retained serving changes require them; do not overwrite historical receipts |
| Target correctness | CPU/OpenVINO/ROCm, both sizes: **168 protocol comparisons passed** on the earlier published images | CUDA target run; revalidation where final dependencies/runtime differ |
| Newer implementation | Local native regression **186 passed, 44 skipped**, before subsequent dependency updates | Final-source CI and actual-image checks after trimming PR #148 |
| OpenVINO | Both sizes passed within B=1, V=1, context<=256, horizon<=320, no covariates | Required final-source validation, measurement and deployable definitions for both sizes |
| Accuracy | Same-device upstream agreement and cross-device drift studies | **Actual forecast-quality scores against held-out future values** |
| Speed | Diagnostic timings only | A fair, repeatable endpoint comparison; no measured winner yet |
| Integration | PR #148 open; auto-merge disabled; contains excessive benchmark machinery | Trim it before merge; automatic publication watcher is stopped |
| Deployment | Legacy services remain running; no standard-service client migration | Four-backend staged definitions, approved side-by-side rollout, verified rollback and caller migration |

Later base changes include cooldown lock resolution and an OpenVINO PyTorch update. Earlier evidence remains valid for its recorded pins; it is not proof for newer images. Recheck PR/main at execution time rather than relying on this status table.

## Global constraints

- Required variants are exactly `cpu`, `cuda`, `rocm`, `openvino`; required model sizes are 5M and 209M. The comparison has **eight rows**, not six with OpenVINO or CUDA omitted.
- No custom forecasting API, copied forecasting algorithm, upstream source patch, silent precision/model/device substitution or CPU fallback. No OVMS revival.
- Weights/IR stay outside images. Pin runtime digests, model revisions and OpenVINO artifact commits/manifests independently. Preserve the existing HF trust identity and published bundles.
- Same-device PyTorch correctness keeps rtol=atol=1e-5; OpenVINO conversion keeps its established rtol=atol=1e-4 for quantiles/median. Quantile levels keep rtol=1e-6/atol=1e-7. These are **not forecast-accuracy scores**.
- No general CPU/GPU equivalence promise. Score device-native forecasts against truth and retain any numerical differences; do not widen a tolerance to hide failures.
- Common-domain comparison: B=1, V=1, no covariates, context<=256, horizon<=320, FP32, `max_context=256`, `per_shot_horizon_patches=5`, both boolean options true. OpenVINO is required in this comparison. These bounds do not establish full-default feature parity.
- Keep PyTorch defaults unchanged outside the explicit comparison preset. Reject unsupported OpenVINO requests. A real caller outside its bounds needs explicit backend expansion/validation, not silent request shortening.
- Heavy model execution runs on native amd64 CI or explicitly selected hardware; no local ARM emulation. Leave unavailable hardware visibly pending; never stop other workloads to make room.
- Keep legacy endpoints/caches and the recorded rollback image intact. No stable alias update, rollout, client cutover or retirement without its separate approval.
- Registry changes follow `kubernetes/registry/AGENTS.md`, affect plt only, use separate resources and initially have no automated child sync. Adding files to the legacy auto-synced resource directory is forbidden.

## Keep the implementation lean

**Keep:** shared serving code, necessary bounded-preset/identity changes, existing artifact verifier and hardware probe, useful correctness tests, publication receipts and raw evidence.

**Remove from PR #148's new work:** `benchmarks/collect.py`, `render_job.py`, `run_isolated.py`, `server_process.py`, the generic `v2.py` harness and framework-specific tests. Keep their history recoverable; do not delete user work or historical experiments. Replace only the new comparison machinery with:

- `timestral/benchmarks/compare.py`: dataset preparation, standard HTTP requests, straightforward timing/scoring, CSV/JSON output.
- `timestral/tests/test_compare.py`: metric arithmetic, data isolation and response identity checks.
- One `timestral/benchmarks/comparison.json` containing pinned dataset/case selection and endpoint/image/model/profile identities.
- One short runbook and final Markdown report. Use ordinary `kubectl`, existing manifests and `kubectl cp`; no custom collector protocol, telemetry agent, orchestrator or policy engine.

One protocol—JSON REST—is sufficient for the performance/accuracy comparison. Preserve existing JSON/binary/gRPC **correctness** coverage. Do not multiply the performance experiment across three transports and both concurrency levels. Concurrency/cancellation correctness already has targeted tests.

## Fixed comparison protocol

### Real held-out observations

Use the official M4 train/test split, pinned to repository commit `6c1067e5a57161249b17289a565178dc7a3fb3ca`:

- `Dataset/Train/{Hourly,Daily,Weekly}-train.csv`
- `Dataset/Test/{Hourly,Daily,Weekly}-test.csv`
- `Dataset/M4-info.csv` for series IDs, official horizons and MASE frequency.

Select 50 valid series per frequency by ascending SHA256 of `timestral-compare-v1/<series-id>`; freeze the resulting 150 IDs and downloaded-file SHA256s **before running models**. Use only the last up-to-256 training observations as model context, with explicit observation masks. Future test values are used only by the scorer. Remove CSV padding, not real zeros. Fail/report missing or invalid selected cases; do not silently replace cases after seeing results.

Use the official horizon (Hourly 48, Daily 14, Weekly 13) and frequency metadata. MASE scaling uses the available **training** history, never future values. This is a deliberately small public-benchmark comparison of this serving configuration; it is not the full M4 ranking or a claim that the pretrained models never saw these public data. Add a representative private holdout later if supplied; do not describe public results as production-domain accuracy.

Primary source and scoring reference: [official dataset description](https://github.com/Mcompetitions/M4-methods/blob/6c1067e5a57161249b17289a565178dc7a3fb3ca/README.md), [official MASE/sMAPE evaluation](https://github.com/Mcompetitions/M4-methods/blob/6c1067e5a57161249b17289a565178dc7a3fb3ca/Benchmarks%20and%20Evaluation.R). Download data externally; do not commit dataset copies.

### Accuracy and speed

- Point accuracy: median forecast **MAE, MASE and sMAPE**. MASE is the primary cross-series point score; lower is better.
- Quantile accuracy: mean pinball loss and weighted quantile loss `2 * mean_over_quantiles(sum_over_horizon(pinball)) / sum(abs(truth))`; lower is better. Evaluate all 21 returned levels.
- Compute per-series scores first, then equal-weight means per frequency; headline macro-score weights the three frequencies equally. Do not let one large-unit series dominate the result.
- For zero MASE scale or zero WQL denominator, report undefined as JSON null plus its count and retain MAE/raw pinball; no artificial epsilon floor or NaN JSON. sMAPE contributes zero only when truth and prediction are both zero.
- Use 10 untimed warmup requests per endpoint/model, then three sequential passes over the identical frozen case order at concurrency 1. Time the real request through NumPy output decoding; calculate scores outside the timer. Score the first prediction once; use repeats for timing and record repeat-output drift separately.
- Report p50/p95 latency and sample/error counts per frequency and overall. Collect cold readiness separately. Do not call this fixed-workload measurement a sustained-throughput SLO.
- Record actual Pod imageID, loaded model/revision/backend/profile, artifact identity, hardware, CPU threads/limits and a before/after load snapshot. Label RAM/VRAM observations accurately; do not present client RSS or whole-device usage as server peak allocation. No new monitoring subsystem.

## Review focus

1. Future-value leakage or changing the cohort after seeing scores: Task 2 pins the split, inputs and selected IDs.
2. Calling upstream agreement “accuracy”: Tasks 2/4 score real targets and keep serving parity separate.
3. Comparing different model sizes, profiles or case sets as equivalent: Tasks 1/3 reject identity/config mismatch; Task 4 separates rows and frequencies.
4. Hiding zeros, failed requests, missing CUDA or OpenVINO cases in averages: Tasks 2/4 retain undefined/error counts and incomplete rows.
5. Accidental legacy replacement or rollout through auto-sync: Task 5 uses separate app/resources and explicit rollout/cutover gates.

## Task 1: Trim and finish the serving change

**Files:** PR #148's changed serving/tests/CI/docs; remove the new benchmark framework files listed above. Preserve Task 1's historical receipts/probes. Modify the current PR through normal commits, not a competing PR.

- [ ] Audit the actual PR head and base. Preserve unrelated local edits and other actors' commits; record the final dependency pins. Keep automatic merge/publication off until the lean diff is reviewed.
- [ ] Retain only the shared serving changes required for the four backends and matched `bounded-v1` operation. Preserve default-constructor, incompatible-OpenVINO and response-identity tests. Remove framework-only tests with the removed framework. Remove `benchmarks.v2` imports from `tests/integration/test_triton_client.py` using a small local parameter-decoding assertion; remove the framework-dependent client add-on from `test_server_admission.py` while retaining its real HTTP/gRPC cancellation/admission checks. Keep existing full transport correctness tests.
- [ ] Avoid duplicate CPU builds for the same image: reuse a model job's image for default and bounded checks where straightforward. Do not make CI optimization a separate project or weaken required checks.
- [ ] Run native `uv run --frozen --project timestral/dependencies/cpu python -m pytest timestral/tests timestral/openvino/tests -q` and affected workflow contracts. Expected: no new failures; skips are explicitly non-hardware evidence. Leave protected integration until Task 2 is ready; review the complete lean diff once before merging.

**Done:** the framework is removed from the new PR diff, necessary serving changes remain, and the small comparison script can be added without carrying the old machinery.

## Task 2: Implement the single comparison script

**Files:** create `timestral/benchmarks/compare.py`, `timestral/tests/test_compare.py`, `timestral/benchmarks/comparison.json`; replace the new benchmark runbook with concise operator commands.

**Interfaces:** `load_cases(manifest: dict) -> list[dict]`; `score_case(history, truth, median, quantiles, levels, seasonality: int) -> dict`; `evaluate(config: dict, cases: list[dict]) -> list[dict]`. A case has `id`, `frequency`, `history`, `truth`, `seasonality`; model request construction receives history and horizon, never truth. CLI: `python timestral/benchmarks/compare.py --config <json> --output-dir <dir>`.

- [ ] Write failing tests for known arithmetic, zeros/constant/signed data, missing inputs, split isolation, fixed cohort, wrong loaded revision/profile and failed-case retention. An upstream-equal forecast with truth error must still get a nonzero forecast-error score. Example arithmetic: history `[1,2,3]`, truth `[4]`, median `[3]`, quantile `[[3]]` at level `[0.5]`, seasonality 1 gives MAE=1, MASE=1, sMAPE=200/7 and WQL=0.25.
- [ ] Run the focused tests and observe the missing/incorrect behavior. Implement the small script using the existing pinned HTTP client and NumPy. Use the standard unversioned inference route with explicit JSON content type; verify loaded revision/profile in responses. Do not import KServe's protobufs into the client process.
- [ ] Export client requirements from the **final pinned source's** frozen lock. Run native `uv run --frozen --project timestral/dependencies/cpu python -m pytest timestral/tests/test_compare.py -q`, then the relevant full suite. Expected: correct scores/identity rejection and no regressions. Commit only task files.

**Done:** one reproducible command produces raw per-case predictions/timings and summary CSV/JSON; no model run or quality claim is faked by unit tests.

## Task 3: Freeze inputs and validate all required backends

**Files:** use existing Dockerfiles/workflows, `timestral/tests/hardware/{probe.py,render_job.py}` and versioned receipts under `timestral/docs/verification/`.

- [ ] Integrate the lean PR through ordinary protection. Freeze one source/dependency snapshot. Publish new candidates once only if retained serving changes require them; verify digests directly in the registry. Do not restart the experiment for unrelated later commits. Reuse existing profile bundles unless actual new-runtime compatibility checks fail.
- [ ] Recheck context, node/plugin health, CPU/RAM/disk reservations and actual GPU headroom. Obtain a safe NVIDIA hardware window if necessary; do not evict workloads, lower safety budgets to force scheduling or substitute CPU.
- [ ] Validate exact-image 5M/209M on CPU/CUDA/ROCm/OpenVINO using existing probes and independent upstream references. Verify bounded settings, loaded identities, actual devices, FP32, all three transports, unsupported requests, wrong bundle and missing-device rejection. Save failures and actual imageIDs; clean only emitted test resources.

**Done:** all eight required combinations are validated, or an explicit hardware/runtime blocker remains. **CUDA is required; “pending” is not completion.** OpenVINO must pass with the exact selected bundles and final dependency stack.

## Task 4: Run the comparison and produce the decision report

**Files:** final `timestral/benchmarks/comparison.json`; create `timestral/docs/verification/<date>-speed-accuracy.{md,csv,json}`. Keep large raw outputs outside source control, with checksums and reproduction commands.

- [ ] Run bounded temporary serving Pods/Jobs using the existing manifests and normal image entrypoint. Use ordinary port-forward/exec/copy commands; save the actual Pod identity before requests. Freeze dataset IDs, settings and hardware facts. No custom collector service/protocol.
- [ ] Execute the fixed comparison protocol for all eight rows. Stop for an identity/configuration error; keep ordinary request failures visible. Reuse results for completed identical pins; rerun only changed or invalid measurements. Remove temporary resources after copying results.
- [ ] Verify every row uses the same cohort/profile/options, and every accuracy score has real held-out truth. Report by frequency plus the equal-weight headline summary. A failed/missing row remains in the table and makes completion status incomplete. Do not rank rows on different surviving subsets or average failed cases away; completion requires valid predictions/timings for the selected cohort on every required row.
- [ ] Publish one concise table: backend, model, hardware, p50/p95 latency, MASE, sMAPE, WQL, error/undefined counts and capability limits. Add a simple latency-versus-MASE plot if it clarifies the tradeoff. State fastest and best-scoring choices **on this cohort/hardware**, with the actual differences; do not assert universal or statistically significant wins.

**Done:** the user can answer “what speed and forecast-quality difference do 5M versus 209M and each required backend give us?” from measured data, not parity tests or synthetic timing claims.

## Task 5: Deploy beside legacy, then migrate safely

**Repository:** `kubernetes/registry`; read its `AGENTS.md` again before edits. **Files:** separate `apps/timestral-standard/deployments/ai/resources/`, `template/timestral-standard.yaml`, rendered plt catalog, focused existing-style tests and a short rollback/readme.

- [ ] Prepare definitions for all four required backends and both supported model sizes, with explicit selection, measured resource sizes, immutable image/model/artifact pins, separate cache/names, Vault-backed initialization, nonroot/read-only-root/no-token security and restrictive networking. Include the 8MiB HTTP predecode gateway limit and bounded gRPC receive size. New child app has no automated sync; no prod entry or legacy-resource edits.
- [ ] Test/render/admission-check the concrete definitions; run `make render-catalog`, `make check-rendered`, `make check-resource-layout` and affected tests. Review Argo/source diffs and rollback. Obtain rollout approval for these exact plt resources before syncing.
- [ ] Verify standard endpoints and loaded identities through the intended gateway beside legacy. Confirm readiness, error/capability/body limits and rollback. Reuse the small comparison script for a focused deployed-endpoint check; rerun full measurements only if the deployment changes the measured configuration.
- [ ] Inventory actual callers/traffic, implement only their necessary V2 translations, verify against real callers, then obtain explicit cutover approval. Keep legacy until caller evidence supports retirement and it is separately authorized. No assumption that a repository scan proves zero clients.

**Done:** the required four-backend serving setup is deployed and verified under its declared capabilities, clients have an approved migration/rollback, and the final report refers to real deployable pins.

## Final acceptance

- [ ] CPU, CUDA, ROCm and OpenVINO are working required backends; 5M and 209M are accounted for on each.
- [ ] The eight-row speed/accuracy report exists, using one frozen real-data cohort and matched forecasting settings, with raw evidence and no missing required rows.
- [ ] Upstream serving correctness, forecast quality and speed are reported as separate facts.
- [ ] OpenVINO limits and any application incompatibility are explicit; no full-feature-equivalence claim is inferred from the bounded comparison.
- [ ] Standard services and rollback are verified; migration/retirement gates are respected; unrelated work and prod remain untouched.
- [ ] The implementation stays small: no bespoke benchmark Job framework, collector protocol, telemetry service or generalized numerical-policy engine.

**Immediate next action:** trim PR #148 and replace its benchmark framework with the single real-data comparison script. Do not resume the stopped publication watcher or the superseded full benchmark matrix.
