# Timestral OpenVINO CPU Parity Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` inline, task by task. Keep the existing exporter, adapter, hardware probe and comparison script. One focused review before integration; no new orchestration framework.

**Goal:** Make direct OpenVINO support everything the normal CPU image supports for Timestral-5M and Timestral-209M, with no extra OpenVINO restrictions, then publish and measure it.

**Architecture:** Keep unchanged upstream forecasting and replace only neural block execution with OpenVINO. Extend the existing export inputs and dynamic shapes to preserve CPU grouping/covariate semantics; restore upstream defaults and shared request validation.

**Tech Stack:** Existing pinned Timestral, PyTorch reference, OpenVINO, KServe V2, native amd64 CI and existing publication/probe/comparison tools.

**Spec:** `docs/superpowers/specs/2026-11-02-timestral-openvino-cpu-parity-design.md`.

## Global constraints

- Both models must pass. No CPU fallback, copied forecasting loop, model substitution, precision reduction or widened numerical tolerances.
- No additional OpenVINO restrictions on batch, variables, context, horizon or checkpoint-supported covariates. Preserve existing CPU service budgets and upstream behavior exactly; this task does not remove shared API validation.
- CPU service budgets today: batch ≤8; total target/covariate rows ≤32; input context ≤32768; horizon ≤1024; tensor bytes ≤8 MiB; output elements ≤1,000,000. Check the committed CPU implementation before changing anything; match any intervening intentional CPU changes.
- Upstream defaults: `max_context=model.config.context_length`; `per_shot_horizon_patches=min(32, model.config.block_size)`. Do not guess checkpoint configuration values. The existing explicit `bounded-v1` option may remain for reproducing old experiments; it must not remain OpenVINO's only/default mode.
- Keep source/model/artifact/image identities independently pinned. Old bounded bundles and reports remain immutable historical evidence; introduce a new artifact format/namespace for the wider contract.
- Native amd64 handles conversion/model execution. Preserve unrelated local edits; start from current remote main in an isolated checkout at execution time. Do not reset/stash the shared dirty checkout.
- Existing legacy services stay intact. This plan authorizes implementation, validation and candidate publication, not deployment/caller migration or stable alias promotion. Reuse existing safe test capacity; pause another workload only with its separately authorized window and guaranteed restoration.

## Starting point

- Serving source measured previously: `c6d10649195102f3eab0b1a5cdce8b8af7166969`; results PR #161. All eight bounded rows completed, 3,600 requests, zero errors. These are not full-default OpenVINO evidence.
- Current exporter `timestral/openvino/export/profiles.py` hardcodes one row, zero group IDs, context 32..256 and five horizon graphs. It omits role and known-future inputs.
- `timestral/openvino/backend.py` repeats those restrictions and constructs the upstream forecaster with 256/5 overrides.
- `timestral/serving/artifacts.py` enforces the preview manifest and rejects batches, multiple variables, longer history/horizon and covariates. `serving/upstream.py` and profile metadata also assume bounded OpenVINO.
- The existing hardware probe skips/shrinks OpenVINO cases; passing it unchanged cannot establish the new objective.

## Review focus

1. Export traces must not freeze grouping IDs, row count, context length or horizon from the sample input (Tasks 1/2).
2. Multiple independent batches must remain isolated while variables within a group interact, including mixed covariate roles (Tasks 1/3).
3. Long input histories and partial/final decode blocks must behave exactly like CPU, including normal upstream truncation (Tasks 2/3).
4. Missing/categorical/known-future values and false forecast options must survive conversion without changing their meaning (Tasks 1/3).
5. Wrong or stale artifacts must fail before readiness; wider functionality must not silently execute PyTorch neural operations (Tasks 2/3).

---

### Task 1: Prove a complete neural export contract

**Files:** Modify `timestral/openvino/export/profiles.py`, `timestral/openvino/export/rewrites.py` only if conversion requires it, `timestral/openvino/tests/test_export.py`.

**Interfaces:** Preserve the upstream `predict_block(inputs, observed, group_ids, horizon_patches, role_ids=None, known_future=None, known_future_mask=None)` semantics. Graph outputs are finite FP32 `[rows, horizon_patches * patch_size, 21]`. Group/role IDs are INT64, observations/masks BOOL and neural values FP32. No hardcoded group IDs.

- [ ] Add failing conversion tests using a tiny deterministic upstream model: two independent groups, multiple interacting variables, context below/above 256, horizon patches above five, missing observations and supported covariates. Compare outputs against the unchanged upstream block with rtol=atol=1e-4; use the same exported graph for at least two distinct shapes/ID assignments to detect trace specialization.
- [ ] Run `uv run --frozen --project timestral/openvino/export python -m pytest timestral/openvino/tests/test_export.py -q` on native amd64. Record failures against the old single-row export.
- [ ] Extend conversion to both upstream graph branches: context-only and covariate execution, with dynamic row/context dimensions and real grouping/role/future inputs. First prove a tensor-valued/dynamic horizon works; if it cannot, use complete fixed-horizon coverage for every block size used by the CPU forecaster. Do not add arbitrary caps or a general graph cache/plugin system.
- [ ] Keep rewrites isolated to the conversion copy and mathematically equivalent. Any necessary new rewrite gets a focused reference-equivalence test; leave upstream source and runtime forecasting untouched.
- [ ] Run the conversion tests again. Record the chosen graph representation, traced inputs, supported dynamic dimensions and actual checkpoint defaults in the task ledger. Proceed only when all CPU-used branches are representable; a converter failure is unresolved work, never permission to narrow accepted inputs.
- [ ] Commit only export code and its tests after they pass.

### Task 2: Wire the full contract into the runtime

**Files:** Modify `timestral/openvino/backend.py`, `timestral/serving/artifacts.py`, `timestral/serving/upstream.py`, `timestral/serving/kserve_model.py`; tests in `timestral/openvino/tests/test_backend_ir.py`, `timestral/tests/test_openvino_profiles.py` and existing settings/metadata tests.

**Interfaces:** Keep `OpenVINOBlocks.predict_block(...)` from Task 1; extend `create_forecaster(artifact_directory, *, forecast_profile='upstream-default')`. Keep `verify_profiles(root, manifest_sha256, model_id, model_revision)` returning the verified manifest. New format name: `timestral-openvino-profiles-v2`; list/check the exact files and graph input/output contracts produced in Task 1.

- [ ] Write failing tests asserting default OpenVINO forecaster settings equal a CPU forecaster constructed from the same config; valid grouped/covariate/long requests reach the adapter; metadata reports actual resolved defaults. Assert old v1 bundles cannot be mistaken for full-capability v2 artifacts.
- [ ] Write real tiny-IR tests for changing row counts and grouping/roles, malformed graph types/names/shapes, wrong model/checksum, nonfinite outputs and attempted PyTorch neural loading. Graph acceptance must depend on its verified contract, not symbolic shape compatibility alone.
- [ ] Run focused tests and record their failures before implementation.
- [ ] Load/execute the Task 1 graphs with actual upstream block inputs and return CPU torch tensors for unchanged upstream processing. Remove `validate_preview_request` and its special subclass from the v2 execution path. Use the same capability properties, shared parser and defaults as CPU. Preserve explicit bounded-v1 only as an optional reproducibility configuration if retained elsewhere.
- [ ] Validate the v2 manifest and every graph signature before readiness. Compile reusable dynamic graphs once; do not compile a new model on each request or load reference neural weights. Replace startup enumeration of only eight bounded lengths with representative validation of each real graph branch.
- [ ] Run `uv run --frozen --project timestral/dependencies/cpu python -m pytest timestral/tests timestral/openvino/tests -q` on native amd64 with required OpenVINO runtime dependencies installed through the existing workflow. Required real-IR tests must execute, not silently skip; non-hardware skips remain explicit.
- [ ] Commit the passing runtime change; no publication yet.

### Task 3: Prove CPU-equivalent end-to-end behavior for both models

**Files:** Modify `timestral/openvino/export/profiles.py`, `timestral/tests/hardware/probe.py`, `timestral/tests/hardware/test_probe.py`, `timestral/tests/hardware/render_job.py` as needed; extend existing integration tests and `.github/workflows/timestral-standard.yaml`.

**Interfaces:** Existing export CLI `profiles.py --output DIR --model-size {5M,209M}` emits a verified v2 bundle plus independent-reference parity evidence. Existing hardware probe compares ordinary KServe endpoints against the unchanged CPU reference using upstream-default settings.

- [ ] Add a regression asserting the OpenVINO probe receives the same valid fixtures as CPU: remove backend-specific skips, context shrinking, horizon shrinking and expected rejection of otherwise CPU-valid cases.
- [ ] Add deterministic parity cases for B=2,V=2; mixed independent groups; batch 8; total rows 32; context 257/1103/32768 and around the checkpoint's normal context boundary; horizons 1/31/32/33/160/161/320/321/1024; numeric/categorical past and known-future covariates where each checkpoint permits them; sparse/leading missingness; nonnegative/signed inputs; all four option combinations. Cover boundary dimensions separately where combining them would make the reference unnecessarily expensive, plus representative combined cases. Test valid 32-row covariate mixtures and shared-parser rejection just beyond existing CPU budgets.
- [ ] Compare final quantiles and median at rtol=atol=1e-4 and unchanged quantile levels; retain per-case errors and resolved profiles. Verify group isolation by changing one batch while checking the other, and prove within-group interaction against the CPU reference. A CPU rejection of a checkpoint-unsupported feature must match on OpenVINO.
- [ ] Generate both real-model bundles on native amd64. Reference and OpenVINO execute in separate processes; the runtime worker must not load PyTorch neural weights. Fail the workflow on any missing branch, mismatch, unexpected skip or nonfinite output. Do not weaken tolerances or substitute the old bounded reference.
- [ ] Exercise HTTP JSON, HTTP binary and gRPC with both exact-image models. Retain request IDs, source/image/model/artifact identities and actual endpoint metadata. Verify incorrect bundles fail before readiness.
- [ ] Run affected full native regression/workflow tests, then one focused review of the lean combined diff. Fix correctness findings before integration; commit passing changes.

### Task 4: Publish full-capability candidates and receipts

**Files:** Modify `timestral/openvino/export/publish.py`, `timestral/openvino/export/model-card.md`, `.github/workflows/timestral-openvino.yaml` and their existing tests only where needed for v2; new versioned receipt under `timestral/docs/verification/`.

- [ ] Add failing publication tests for v2 manifest identity, required passing parity evidence and distinct artifact namespace. Keep existing main-only dispatch/OIDC authorization and immutable model/source checks.
- [ ] Publish both passing bundles under a new v2 namespace without overwriting v1. Record artifact commits and manifest digests independently. Update image/initialization fixtures to use the matching v2 pins.
- [ ] Integrate normally through required checks, freeze the resulting source, then use existing workflows to build/push the OpenVINO candidate once. Do not rebuild unrelated images or repeatedly chase unrelated main commits.
- [ ] Verify Docker registry manifests and actual native CPU Pod imageIDs; run the full Task 3 acceptance on the published image/bundles, save receipts/logs/raw errors and clean only emitted resources after saving evidence.
- [ ] Update `timestral/openvino/README.md`, `timestral/README.md` and model cards to describe CPU-equivalent capabilities and inherited shared budgets. Remove current-preview claims only when the new published artifacts actually pass. Keep old reports/receipts explicitly historical.
- [ ] Commit the checked receipts/documentation.

### Task 5: Refresh the speed/accuracy comparison

**Files:** Reuse `timestral/benchmarks/compare.py`, update `timestral/benchmarks/comparison.json`; new dated report `.md/.csv/.json` under `timestral/docs/verification/`. No new benchmark service/framework.

- [ ] Make the existing small client verify the requested resolved forecast profile/settings instead of hardcoding bounded-v1. Add focused tests that reject a bounded endpoint when upstream-default is requested and verify dataset/identity/retry protections remain intact.
- [ ] Freeze the same 150 M4 IDs and hashes, model revisions and request options. Compare CPU and OpenVINO for both models under identical upstream-default settings, 10 warmups and three measured passes. Retain held-out future truth scoring, all per-case predictions/timings, errors and raw checksums.
- [ ] Reuse old bounded rows only as historical results. For an updated four-backend table, run CUDA/ROCm with the same upstream-default settings in an authorized safe hardware window; do not combine new-default rows with old bounded rows as one fair ranking. Every required row must be complete before labeling the refreshed eight-row report complete.
- [ ] Include a short representative latency check for grouped input, context above 256, horizon above 320 and covariates on CPU/OpenVINO. These are performance measurements, separate from the broader correctness matrix; retain failures rather than selecting only easy cases.
- [ ] Report measured median/p95 latency, MASE/sMAPE/WQL, errors, hardware/resources, profile and model pins. Do not carry forward the earlier 21%/29% speed claim as a promise for the expanded/default implementation.
- [ ] Save raw evidence durably outside Git, verify checksums, remove test resources and restore any explicitly paused workloads. Commit the small report/config changes.

## Completion criteria

- [ ] Both 5M and 209M use real OpenVINO neural execution with CPU-equivalent supported inputs and upstream-default behavior.
- [ ] No OpenVINO-only single-series, 256-context, 320-horizon or no-covariate restriction remains for the new artifacts.
- [ ] Independent real-model/default parity, protocol checks, invalid-artifact rejection and full native regression pass.
- [ ] New artifacts/images are published with verified immutable identities; old bounded evidence remains recoverable.
- [ ] A refreshed comparison states actual speed and forecast quality under matched settings, without assuming earlier bounded performance transfers.
- [ ] Implementation remains the existing exporter + adapter + probe + small comparison client; no fallback or generic framework.

**First action at execution:** isolate current main, inspect exact checkpoint configs and run Task 1's native conversion tests. Establish complete graph coverage before spending time on publication or benchmarking.
