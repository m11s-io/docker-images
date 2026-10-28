# ComfyUI ROCm Support Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task. Read repository instructions before editing. This is a handoff document; no implementation or rollout has been authorized by the request to write it.

**Goal:** Publish maintainable AMD ROCm ComfyUI images and provide a deployable Helm/GitOps configuration, with GPU inference validated on the intended AMD hardware.

**Architecture:** Keep CUDA and ROCm as separate image variants with the same ComfyUI source release. Reuse the Helm chart's existing image, resources, scheduling, and security settings. Build ROCm generic first, then establish GGUF compatibility before publishing its ROCm variant.

**Tech Stack:** Docker BuildKit, PyTorch ROCm, ComfyUI, ComfyUI-GGUF, GitHub Actions, Renovate, Helm, Argo CD, Talos, AMD Kubernetes device plugin.

**Spec:** The requirements and decisions below capture the user's request and the source inspection performed on 2026-10-28.

## Global Constraints

- Assign only explicit backend tags to new builds: `-cuda`, `-cuda-gguf`, `-rocm`, and `-rocm-gguf`, with corresponding backend-specific latest and commit tags. Do not assign legacy unsuffixed or `-gguf` aliases. Preserve the existing NVIDIA deployment until a separately reviewed image-reference update.
- Preserve `modelDownload.enabled: true` and `modelDownload.prune: true` in the existing deployment. The user explicitly corrected an attempted change to these settings.
- Build images in GitHub Actions; do not start substantial local image builds.
- Use stable, officially supported ROCm/PyTorch combinations for the exact AMD GPU. Do not assume that the newest ROCm release has matching PyTorch wheels.
- Pin base-image digests, source refs, and Python dependencies; maintain them with Renovate using the repository's current conventions.
- Keep the container non-root. Do not introduce privileged mode, blanket host-device mounts, or disable security controls without evidence that a narrower solution is insufficient.
- Do not edit generated or vendored `.third_party` source. It may be read to understand behavior.
- Inspect current branches, open changes, and repository instructions. Preserve unrelated work. The inspected docker-images checkout had older CUDA pins than the deployed image; do not copy them into new work without reconciliation.
- Prepare image and chart changes for review. Actual publication, deployment, storage changes, and merging must follow the user's authorization and repository workflow.
- Candidate publication and hardware deployment require authorization too. PR validation must remain publication-free; passing CI does not authorize candidate rollout or supported release tags.

## Review Focus

1. ROCm wheels accidentally replaced by CUDA/CPU dependencies during requirements installation: verify installed package versions and `torch.version.hip` after all installs.
2. Non-root GPU access: verify device permissions on the actual AMD node, rather than assuming image group names imply matching host GIDs.
3. CUDA-specific extension paths: prove GGUF execution and record selected accelerated/fallback backends; startup alone is insufficient.
4. Node-local model storage: never attach the existing NVIDIA node's local PVC to an AMD node or allow pruning to affect another instance's models.
5. CI success without GPU execution: distinguish import/CPU-startup checks from actual AMD inference evidence.

## Repositories and Files

Workspace root: `/Users/al/Work/repo/m11s`.

| Repository | Files and responsibility |
| --- | --- |
| `m11s-io-github/docker-images` | `comfyui/Dockerfile`, new `comfyui/Dockerfile.rocm`, `comfyui/Dockerfile.gguf`, `comfyui/verify_image.py`, `comfyui/README.md`: backend images, extension layer, validation, documentation |
| Same | `.github/workflows/build.yaml`, `scripts/test_comfyui_validation.py`, `renovate.json`, plus current runtime-contract/build helpers discovered during Task 1: build/publish routing and update automation |
| `m11s-io-github/helm-charts` | `charts/comfyui/values.yaml`, `templates/deployment.yaml`, `templates/model-download-job.yaml`, existing chart tests, README and Chart.yaml: documented AMD settings and only necessary chart changes |
| `kubernetes/registry` | `apps/amd-device-plugin/base/values.yaml`, `deployments/gpu/values.yaml`: existing AMD infrastructure to inspect, not replace |
| Same | `apps/comfyui/base/values.yaml`, `apps/comfyui/deployments/ai/values.yaml`, deployment registration/generator conventions: existing NVIDIA deployment to preserve and pattern for a separate AMD deployment |

## Task 1: Establish Hardware and Current Source Baseline

- [ ] Read applicable AGENTS.md files and check git/worktree status and relevant open PRs/MRs in all three repositories. Use an isolated implementation checkout.
- [ ] Reconcile the latest ComfyUI image work with the checkout. At investigation time, live ComfyUI reported `torch 2.14.1+cu132`, `torch.version.cuda == 13.2`; the inspected local Dockerfile still installed `cu130`. Do not treat either snapshot as the current source of truth without checking.
- [ ] Identify the intended AMD GPU model, architecture (`gfx*`), VRAM, node, kernel/amdgpu driver, and allocatable CPU/memory. Use read-only discovery where access exists; ask the user only for facts unavailable from the environment.
- [ ] Inspect the existing AMD device plugin and verify its node advertises `amd.com/gpu`. Verify `/dev/kfd` and GPU render-device access and the host device GIDs. Check official AMD hardware and PyTorch support matrices.
- [ ] Record a concrete compatibility tuple: GPU architecture, ROCm version, base image/digest, Python version, torch/torchvision versions and wheel index. Verify wheel artifacts actually exist for the selected Python/platform.
- [ ] Inspect ComfyUI's ROCm branches and the exact pinned ComfyUI-GGUF/comfy-kitchen dependency code. List CUDA-only optional paths and supported alternatives. Do not claim that all currently used model quantizations work on AMD.

**Deliverable:** Compatibility decision with source links and the exact target hardware. An unsupported target or missing wheel combination blocks that target, not permission to use architecture-spoofing workarounds silently.

## Task 2: Generic ROCm Image and Backend-Aware Validation

**Interface:** CUDA generic builds use `-cuda`; new `m11s/comfyui:<ComfyUI-version>-rocm` denotes the generic ROCm image.

- [ ] Add `comfyui/Dockerfile.rocm` with the compatibility tuple from Task 1, the same pinned ComfyUI release, existing directory layout, UID/GID 10001, persistent paths, listener, and entrypoint behavior. Use `python` from the selected virtual environment rather than coupling shared layers to Python 3.14.
- [ ] Install ROCm torch/torchvision explicitly, then constrain them throughout upstream requirements installation. Remove CUDA-specific base, architecture settings, and compiler assumptions from the ROCm variant.
- [ ] Extend `check_dependencies()` in `verify_image.py` with an explicit backend contract (`cuda` or `rocm`), supplied consistently by each image. ROCm requires `torch.version.hip` to be nonempty; CUDA requires `torch.version.cuda` to be nonempty. Preserve exact constraint and pip dependency checks.
- [ ] Add focused tests to `scripts/test_comfyui_validation.py` for ROCm acceptance, incorrect-backend rejection, and dependency replacement detection. Preserve existing CUDA coverage.
- [ ] Retain the CPU startup and HTTP readiness validation for GPU-less CI. Ensure image validation leaves no startup/user-state artifacts in the final image.
- [ ] Add minimal generic ROCm routing to `.github/workflows/build.yaml` now: change filters, manual selection, backend-specific cache scope, and publication-free PR builds. Add focused routing tests preserving CUDA behavior. Task 4 extends this working route; it is not a prerequisite for this task's GitHub build.
- [ ] Run the repository's relevant validation tests and GitHub build for both generic backends. Record versions emitted from the built image. Commit this deliverable separately.

## Task 3: GGUF ROCm Variant

**Interface:** Publish `m11s/comfyui:<ComfyUI-version>-rocm-gguf` only after its dependency paths are established; derive it from the exact generic ROCm image built in the same workflow.

- [ ] Make the GGUF layer backend-neutral where possible. Its current hardcoded `python3.14`, compiler settings, and default CUDA base must not leak into the ROCm build. Use `-cuda-gguf` for CUDA GGUF tags.
- [ ] Use the same pinned ComfyUI-GGUF source release for both backends unless a documented compatibility issue requires otherwise. Inspect whether its dependencies install CUDA-only binaries or invoke CUDA-only APIs.
- [ ] Make the GGUF image run backend-specific dependency validation and verify `UnetLoaderGGUF` registration. Add regression coverage for base-image selection and backend identity.
- [ ] Extend Task 2's CI route to build GGUF from that run's generic ROCm image. For PR and manual `skip_push` builds, load the generic image under a run-specific local tag and use the existing Docker-builder/local-image pattern to pass it as `COMFYUI_BASE`; do not require a registry digest for an unpublished image. Test that neither build publishes and that GGUF cannot resolve to the CUDA default. Record the generic image ID and resulting GGUF image ID.
- [ ] Prepare a candidate hardware-test path before attempting AMD execution: after authorization, use GitHub Actions to publish immutable commit/run-specific candidate tags for generic and GGUF, pass the published generic digest as `COMFYUI_BASE`, and record both resulting digests. Candidates must be excluded from supported release tags, `latest` aliases, and automated deployment image selection. Deploy candidates by digest to an isolated AMD test instance using Task 5's naming/storage rules. Prepare the render and resource diff before requesting rollout approval; remove test resources after testing only within authorized cleanup scope.
- [ ] On AMD hardware, test the GGUF operations and representative quantization types actually required by the intended workflows. Record any fallback, unsupported format, or missing acceleration explicitly. Do not assert NVIDIA FP4/NVFP4 model portability without proof.
- [ ] If the generic image works but GGUF cannot meet the contract, deliver generic ROCm support and document the GGUF blocker rather than advertising an unverified variant. Commit the deliverable separately.

## Task 4: GitHub Builds, Publishing, and Renovate

- [ ] Complete release routing, change filters, and runtime-contract helpers around the generic and GGUF CI routes introduced in Tasks 2 and 3. Preserve CUDA generic/GGUF behavior and use only the explicit backend tag scheme.
- [ ] PR builds validate without publishing using Task 3's local-image handoff. Candidate publication uses Task 3's authorized candidate route; supported release tags require the relevant AMD acceptance evidence from Task 6. Publication uses the repository's existing authorized release flow. For published builds, pass the just-built generic ROCm digest into its GGUF build; never accidentally inherit the CUDA generic image. Validate the resulting release digest on hardware if it differs from the accepted candidate.
- [ ] Use distinct build-cache scopes for backend/variant combinations. Ensure manual image selection can request ROCm builds and generic changes rebuild dependent GGUF variants.
- [ ] Extend Renovate rules to track the ROCm base/digest, wheel index, and compatible package pins using existing manager conventions. Group coupled updates and apply existing approved automerge rules only when required checks cover the new variants. Do not independently advance an index beyond published matching wheels.
- [ ] Validate Renovate configuration and add focused workflow/runtime-contract coverage for ROCm tag generation, dependency ordering, and CUDA regression behavior. Run the relevant CI checks, then update image documentation with tags and support limits. Commit separately.

## Task 5: Helm Configuration and Separate AMD Deployment

- [ ] Confirm the existing chart renders AMD values correctly before adding new template abstractions. It already exposes `image`, `runtimeClassName`, arbitrary resources, node selectors/tolerations, and pod security settings.
- [ ] Add an AMD values example and Helm tests: ROCm image; `runtimeClassName: ""`; `amd.com/gpu: "1"` in requests and limits; AMD node selection; existing GPU-tier toleration; no NVIDIA resource request or RuntimeClass. Preserve the current CUDA example/tests.
- [ ] Verify whether existing podSecurityContext settings support any required supplemental device groups. Use observed host GIDs and device-plugin behavior; do not assume fixed `video`/`render` GIDs. Add template support only if the chart cannot already express the necessary setting.
- [ ] Prepare a separate GitOps AMD deployment using repository registration conventions. Give it separate service/route identity and model/output/user PVCs. Preserve the existing NVIDIA deployment and its model-download/prune settings.
- [ ] Register the AMD deployment in a separate namespace, `comfyui-amd`, and set its deployment values to `fullnameOverride: comfyui-amd` to override the shared `fullnameOverride: comfyui`. Give its ComfyUI/MCP routes distinct hostnames and reference only its own PVCs and namespace-local resources. Render both releases and assert that the AMD resources cannot select or reference the NVIDIA instance's workloads or PVCs.
- [ ] Update `template/comfyui.yaml` so the AMD Application depends on `amd-device-plugin` while the existing NVIDIA Application retains `nvidia-device-plugin`; preserve shared gateway/storage dependencies. Make the choice explicit in deployment metadata or separate templates according to generator capabilities. Run `make render-catalog`, `make check-rendered`, and `make check-resource-layout`; verify the generated AMD namespace/dependencies and unchanged NVIDIA registration.
- [ ] Keep downloads and pruning enabled for the AMD instance's own model volume. Curate its model list for hardware-supported formats; do not blindly copy NVIDIA-specific checkpoints. Check the Job's image, placement, device requirements, and storage access separately from the inference pod.
- [ ] Verify CPU/memory capacity for ComfyUI, MCP sidecar, download Job, and node services together. The current NVIDIA incident showed a Job can fit while its inference pod cannot; avoid reproducing this on AMD.
- [ ] Render both deployment configurations and run relevant Helm tests. Record storage binding constraints and expected generated resources. Commit chart and registry changes in their respective repositories; open reviewable PRs/MRs in dependency order.

**Ordering:** Prepare the isolated AMD test values and render them before Task 3's hardware test; this preparation does not enable GitOps sync. Use accepted candidate digests for Task 6, then promote supported tags through Task 4's release flow. Enable the permanent AMD GitOps deployment only after acceptance and authorized rollout.

## Task 6: Hardware Acceptance and Handoff

- [ ] After authorized candidate publication/deployment through Task 3, confirm the actual pulled image digest, torch version, `torch.version.hip`, GPU model, and `torch.cuda.is_available()` (PyTorch also uses the `torch.cuda` API on ROCm). Record evidence against each candidate digest; this acceptance gates supported release tags and permanent deployment.
- [ ] Run a small GPU tensor operation and synchronize. Confirm ComfyUI reports the AMD device and serves `/system_stats` and `/object_info` with all required nodes.
- [ ] Execute one known supported image-generation workflow on AMD; verify output and review logs for backend/precision errors. Repeat with a required GGUF workflow if delivering that variant.
- [ ] Confirm model download verification/pruning succeeds on the AMD instance's own PVC, and that both the Job and inference pod can progress under their declared requests.
- [ ] Record elapsed inference time and peak VRAM/system RAM for these fixtures. These are acceptance observations, not a broad benchmark claim.
- [ ] Verify the NVIDIA deployment is unaffected and its validation still passes. Report separately: CI build results, hardware execution results, supported GPU/model formats, unverified paths, PR/MR links, image digests, and rollback configuration.

## Completion Criteria

The generic ROCm image builds in GitHub, dependency updates are tracked by Renovate, Helm renders an AMD deployment without NVIDIA requirements, separate storage and model-management settings are correct, and a known workflow runs on the identified AMD GPU. GGUF support is accepted separately with real AMD execution evidence. A GPU-less CI build alone does not complete hardware acceptance.
