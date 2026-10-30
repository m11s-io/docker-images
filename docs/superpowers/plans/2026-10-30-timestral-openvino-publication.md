# Timestral OpenVINO Publication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export, validate and publish the experimental neural block to the private `m11s-org/Timestral-5M-OpenVINO-experimental` repo through GitHub Actions OIDC.

**Architecture:** An isolated Python export project produces immutable artifacts and a validation report. A validation job exercises upstream parity and real OVMS HTTP inference. A dependent main-only publishing job downloads exactly those artifacts, verifies checksums and publishes through repo-scoped OIDC.

**Tech Stack:** Python 3.12, uv frozen lock, PyTorch 2.6.0 CPU, OpenVINO 2026.4.1, OVMS 2026.4.1, huggingface_hub >=1.19.0 pinned in the lock, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-29-timestral-openvino-experimental-design.md`

## Global Constraints

- Upstream source commit `a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff`; model `mistralai/Timestral-5M` revision `bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f`.
- FP32 context `[1,128]`, BOOL observed `[1,128]`, FP32 quantiles `[1,32,21]`, CPU precision hint FP32.
- Compare unmodified upstream with IR at `rtol=1e-4, atol=1e-4`; require finite outputs and every quantile.
- Pin export dependencies separately from production Timestral; preserve all unrelated working-tree changes.
- No stored HF write token; only publish job gets `id-token: write`; publish only on main after validation.
- No full forecasting API, cluster changes or performance claims. Record actual CPU architecture/vendor.
- HF destination and exact publisher binding already provisioned. Preserve private visibility and existing branch checks.

## Review Focus

- Upstream drift: compatibility substitutions must match exact expected source and counts or fail.
- Missing observations: scattered and leading missing examples must match unmodified upstream across all quantiles.
- Conversion success without usable serving: real KServe REST response must match expected tensor and parity tolerance.
- Artifact substitution: publish only the validated bundle, reject path traversal/symlinks/unexpected files and checksum changes.
- Credential exposure: no token in files, logs or artifacts; main-only publishing and job-scoped OIDC permission.

### Task 1: Reproducible export and parity validation

**Files:** Create `timestral-openvino/pyproject.toml`, `uv.lock`, `export.py`, `tests/test_export.py`.

**Interfaces:** `export.py --output DIR` produces `model/1/model.xml`, `model/1/model.bin`, `config.json`, `quantiles.json`, `validation.json` and validation input/reference fixtures. `patch_source(source: Path, destination: Path) -> None` patches only the isolated export copy. `validate_outputs(reference, actual) -> dict` rejects shape, dtype, finiteness or parity failures.

- [ ] Write failing tests for guarded source rewrites, drift rejection, shape/nonfinite/parity rejection and missing-data cases; run with unittest and confirm failures.
- [ ] Fetch source at exact commit; lock Python3.12 dependencies including torch CPU2.6.0, OpenVINO2026.4.1 and HF CLI. Resolve actual package availability before committing pins; never silently substitute a version.
- [ ] Load source model via `timestral.loading.load_model` with the exact model revision. Run original and patched modules in separate processes so import caches cannot invalidate the reference.
- [ ] Trace a fixed-shape wrapper around the no-covariates single-block prediction, naming inputs/output explicitly. Guard both nonoverlapping unfold replacements and boolean cummax replacement with exact source matches; verify expected upstream entry-point signature.
- [ ] Export FP32 IR with compression disabled; compare native OpenVINO CPU output with unmodified upstream on seeded random, sinusoidal, constant, scattered-missing and leading-missing inputs. Store per-case errors and CPU/package/source provenance.
- [ ] Run unit tests and actual conversion/parity validation; all cases must pass. Commit only this isolated project.

### Task 2: Real OVMS serving and publication bundle

**Files:** Create `timestral-openvino/validate_ovms.py`, `package.py`, `README.md`, `model-card.md`, `tests/test_package.py`, `tests/test_ovms.py`.

**Interfaces:** `validate_ovms.py --bundle DIR --url URL` validates KServe v2 readiness and inference against saved reference fixtures with bounded startup/request timeouts; writes `ovms-validation.json`. `package.py --bundle DIR` builds the allowlisted publication folder and `SHA256SUMS`. `package.py --verify DIR` fails on changed, missing or unexpected files.

- [ ] Write failing tests for malformed OVMS responses, wrong shapes/nonfinite values, checksum corruption, path traversal and symlinks. Confirm they fail before implementation.
- [ ] Run pinned OVMS2026.4.1 by resolved immutable image digest, mounting exported IR read-only; request actual `/v2/models/model/infer`, including BOOL observed input, and compare all outputs to upstream references.
- [ ] Assemble IR, source config, quantile metadata, source license/attribution, model card and both validation reports. Include source/model/CI commit provenance; exclude source checkpoints, caches and credentials.
- [ ] Model card explicitly describes the fixed-shape experimental neural block and missing full forecasting orchestration. Record real hardware; claim Intel validation only on confirmed native Intel hardware.
- [ ] Run unit and container integration tests, verify the final bundle manifest, and commit.

### Task 3: Validated artifact workflow and first publication

**Files:** Create `.github/workflows/timestral-openvino.yaml`, `timestral-openvino/tests/test_workflow.py`.

**Interfaces:** PR and dispatch validation produces a checksummed Actions artifact named `timestral-openvino-validated`; publish job consumes that artifact and `vars.HF_TIMESTRAL_OPENVINO_REPO`, returning an immutable HF commit SHA in the job summary.

- [ ] Add failing workflow contract tests: validation lacks write credentials; publish requires validation and main; only publish has id-token write; repository variable required; checksums verified before upload; concurrent publication serialized.
- [ ] Add manual dispatch and path-filtered PR triggers with SHA-pinned actions. Validation uses Python3.12/frozen export lock, records actual hardware, runs Tasks1-2, then uploads only the allowlisted bundle.
- [ ] Publish runs only for manual dispatch on `refs/heads/main`, after successful validation, with `contents: read` and `id-token: write`; set `HF_OIDC_RESOURCE` from the configured variable. Use pinned HF library OIDC authentication and upload in one commit, recording returned commit SHA without exposing token.
- [ ] Run all project tests and actionlint; scan staged files/history for credentials/private paths. Obtain one fresh review of the whole change and resolve important findings.
- [ ] Open a PR preserving existing required checks. After merge authorization and passing CI, merge and dispatch `timestral-openvino.yaml` on main. Verify job success, returned HF commit and remote manifest. Never bypass validation to test upload.

## Current state and execution ruling

Registry installation, private model repo, exact trusted publisher and Actions variable are complete and verified. The exporter and workflow do not exist on GitHub main; an immediate dispatch is impossible. No model has been uploaded. Use an isolated branch/worktree; the current docker-images checkout has unrelated edits.

The user authorized workflow preparation and a first validated upload. Review this implementation plan before beginning the new exporter/serving implementation. No renewed approval is needed for already-authorized HF setup or temporary token use; CI uses OIDC.

## Execution ledger

- 2026-10-30: Isolated branch created from origin/main; all 38 baseline tests pass outside sandbox.
- Task1 red: four exporter safety tests fail for missing functions. Green: guarded rewrites, synthetic missing-data fixtures and numerical gate pass.
- Task2 red: OVMS response and bundle integrity tests fail for missing functions. Green: response shape/type/finiteness and manifest corruption/missing/extra/symlink/traversal tests pass.
- Task3 red: workflow and publish environment tests fail for missing functionality. Green: main-dispatch-only publication and exact OIDC destination tests pass; nine total new tests.
- Ruling: Move full conversion/OVMS execution to GitHub CI at user direction. Local ARM emulation is redundant; CI will supply the actual integration evidence before merge/publication. No successful export or model upload is claimed yet.
- Heavy checks will run on the PR through the new workflow, with no HF write credentials.
