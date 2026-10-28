# CUDA Dependency Ownership Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. Do not delegate unless the user requests it.

**Goal:** Remove ComfyUI's redundant system CUDA installation and run the latest compatible stable CUDA-enabled PyTorch stack, with Renovate automatically updating and merging changes after required GitHub checks pass.

**Architecture:** Use a pinned Python base for ComfyUI, with CUDA runtime libraries supplied by the selected PyTorch wheels and driver libraries supplied by the host NVIDIA container runtime. Retain each application's own dependency files; Renovate discovers stable releases across CUDA variants, groups compatible application dependencies, and auto merges only after required CI checks establish package compatibility. Timestral retains its existing Python base and CPU lock workflow.

**Tech Stack:** Docker Buildx, Python/pip/uv, PyTorch CUDA wheels, Renovate, GitHub Actions, unittest.

**Spec / design basis:** The user's approved direction in the CUDA source-analysis conversation: plain Python base, latest compatible stable PyTorch/CUDA wheels, prebuilt native helpers, automatic CUDA variant updates and merging after required checks, and host driver management kept separate. This document records the implementation choices for review; it does not authorize deployment.

## Global Constraints

- Work in `m11s-io-github/docker-images`; preserve existing uncommitted workflow and documentation changes. Inspect the diff before editing. Create an isolated checkout at execution time if needed.
- Preserve ComfyUI Python minor `3.14` and the existing GGUF commit during the packaging migration. Torch `2.14.1+cu130` and TorchVision `0.29.1+cu130` are the starting pins, not an upgrade ceiling. Select the latest compatible stable CUDA wheels published for the target Python/platform; exclude nightly, prerelease, CPU and ROCm wheels from CUDA images.
- Record the old image's exact Python patch and select the same patch in the new official Python slim Debian base, pinned by digest. If unavailable, explicitly review the patch change before implementation.
- Keep Timestral Python `3.15.2` and its application/source pins initially. Update CPU and CUDA Torch releases together; preserve the CPU-only default and regenerate its lockfile on updates.
- Preserve UID/GID 10001, `/opt/venv`, home/cache ownership, ports, mounts, entrypoint behavior, and generic/GGUF build relationship.
- Fail installation if `comfy-kitchen` or `comfy-aimdo` would require a source build. Do not silently publish an image without its native CUDA backend.
- Run image builds on GitHub Actions, not locally. No driver upgrade, Helm image update, manual publishing, or deployment in this work. Automatic merges may trigger the repository’s existing main-branch image publishing workflow. GPU tests validate a release; source and binary dependency inspection establish packaging requirements.
- Full dependency graph locking, including Timestral's separately resolved CUDA dependencies, is a follow-up. Do not describe the requirements pins below as a complete lockfile.

## Review Focus

- Native helper wheels may be unavailable for a target Python/platform: fail installation explicitly.
- An import can succeed while Comfy Kitchen silently disables CUDA: inspect its native extension directly during build validation.
- Moving away from NVIDIA's base loses environment defaults and library search paths: preserve GPU visibility/capabilities explicitly and inspect driver library discovery.
- Independently updated Torch/TorchVision releases can be incompatible: group proposals and require real image dependency/import checks; grouping alone does not establish compatibility.
- Timestral CPU and CUDA Torch releases can drift: include both in one Renovate group and retain a meaningful release-parity check.

## Task 1: Remove the duplicate CUDA installation from ComfyUI

**Files:** Modify `comfyui/Dockerfile`, `comfyui/Dockerfile.gguf`, `comfyui/verify_image.py`, and `comfyui/README.md`; extend `scripts/test_comfyui_validation.py` only for new validation behavior.

**Interfaces:** Existing `check_dependencies() -> None` and `check_startup(gguf: bool, timeout_seconds: float = 120) -> None` remain. Validation must work without a GPU during image builds.

- [ ] Record the currently selected image's Python patch, native helper wheel versions, and inherited NVIDIA environment configuration. Use the source revision pinned by the image, not only the newer local ComfyUI checkout.
- [ ] Replace the CUDA Ubuntu base with the selected pinned official Python 3.14 slim Debian base. Remove deadsnakes/PPA and distro Python installation. Use the base interpreter to create `/opt/venv`; use `python` consistently in both Dockerfiles.
- [ ] Retain required X11 libraries, git, CA certificates, and C compiler support for runtime compilation. Use the Debian base's compiler consistently in `CC`; do not retain a nonexistent `/usr/bin/gcc-12`. Remove `TORCH_CUDA_ARCH_LIST` if nothing builds CUDA extensions.
- [ ] Set `NVIDIA_VISIBLE_DEVICES=all` and `NVIDIA_DRIVER_CAPABILITIES=compute,utility` explicitly. Preserve nonroot home/cache directories. Do not carry forward CUDA toolkit paths or `NVIDIA_REQUIRE_CUDA` from the removed base.
- [ ] Keep existing Torch install/constraints unchanged in this task. Add targeted `--only-binary=comfy-kitchen,comfy-aimdo` to the upstream dependency installation. Apply the same protection to the GGUF dependency install.
- [ ] Extend dependency validation to reject a missing/broken Kitchen CUDA extension directly, without requiring a physical GPU. Inspect the exact pinned helper's loader interface before coding. Add a regression test for the failure case, then implement it and run `python3 -m unittest discover -s scripts -p 'test_comfyui_validation.py'`.
- [ ] Build generic Linux AMD64 image and GGUF child using that exact local parent. Both existing dependency/audio/startup validations must pass. Inspect ELF dependencies of Torch, Kitchen, AIMDO, and ANGLE: all non-driver libraries must resolve; driver libraries must be intentionally host-provided. Record the compiler and shared-library providers.
- [ ] Update the image README with the dependency ownership and binary-only policy. Record GPU execution as unverified unless actually run. Review the diff and commit only this task's changes.

## Task 2: Make CUDA Torch pins visible to Renovate

**Files:** Create `comfyui/requirements-cuda.txt` and `timestral/requirements-cuda.txt`; modify `comfyui/Dockerfile`, `timestral/Dockerfile.cuda`, `comfyui/verify_image.py`, `scripts/test_timestral_runtime.py`, and `renovate.json`. Add `scripts/test_cuda_renovate.py` for policy behavior where useful.

**Interfaces:** Channel-neutral `requirements-cuda.txt` files contain exact stable CUDA wheel pins. ComfyUI contains Torch and TorchVision; Timestral contains Torch. Use the aggregate official PyTorch index for Renovate lookup, restricted to stable `+cu` builds. Derive the complete channel-specific installation index from the Torch pin; the aggregate index does not contain all runtime dependencies. Verify actual index contents and Renovate lookup behavior before selecting the index. ComfyUI continues exposing `PIP_CONSTRAINT` to validation and later installs.

- [ ] Move inline wheel pins into these requirements files. For ComfyUI, derive the constraints file from requirement lines, excluding index options, so upstream requirements still resolve from PyPI while respecting Torch pins. Make validation ignore comments/options if it reads the requirements file directly.
- [ ] Change Timestral's existing post-sync CUDA install to consume its requirements file. Keep the CPU `uv.lock` unchanged. Update the existing parity test to read the CUDA requirements file and compare the release portion with `pyproject.toml`.
- [ ] Verify Renovate's requirements manager extracts both files using the CUDA index and retains CUDA local-version suffixes and discovers newer CUDA variants. Use extraction/lookup output, not regex matching alone. If the selected Renovate release drops local-version compatibility, add a narrowly scoped compatibility/version rule and demonstrate its behavior before continuing.
- [ ] Extend the ComfyUI update group to include `comfyui/requirements-cuda.txt`. Add a Timestral Torch group covering CPU project/lock and CUDA requirements updates. Keep the two applications independently upgradeable.
- [ ] Remove the cu130-only filter. Enable `automerge: true`, `platformAutomerge: true`, and `ignoreTests: false` for the scoped ComfyUI dependency group and Timestral PyTorch group, including stable major/minor/patch and CUDA variant updates. Preserve the existing Docker digest policy. Inspect inherited rules so a later rule cannot disable this policy.
- [ ] Test extraction of every current dependency, exclusion of CPU wheels from CUDA proposals, discovery of a newer stable CUDA variant without changing the index manually, ComfyUI grouping, and Timestral CPU/CUDA parity. Confirm all channels/versions exist for the selected Python/platform; a grouped PR is allowed to fail CI if upstream publishes incompatible packages.
- [ ] Run the Renovate config validator, image/runtime script tests, and Timestral API tests via `uv run --frozen pytest tests/test_api.py -q`. Build both Timestral variants and rebuild both ComfyUI variants after changing their install inputs. Ensure requirements changes trigger the existing CI image filters; modify filters only if inspection proves a gap.
- [ ] Document that Renovate proposes available versions and auto merges only after required package/image checks pass. Review and commit this task separately.

## Task 2a: Prove automatic CUDA upgrades and merge gates

**Files:** Modify `renovate.json`, `.github/workflows/cuda-dependencies.yaml`, `scripts/test_timestral_runtime.py`, Dockerfile/ignore references to renamed requirements, and both image READMEs. Inspect GitHub repository rules through its API.

- [ ] Check official PyTorch wheel listings for the latest stable Torch/TorchVision combination available on Linux AMD64 for each image’s Python. Record the selected versions and CUDA variant; do not equate a newer NVIDIA toolkit release with an available PyTorch build.
- [ ] Run the pinned Renovate release against an older-pins fixture using the official index. Assert that it proposes a newer CUDA variant, excludes CPU/ROCm/prerelease wheels, and groups Torch/TorchVision and Timestral CPU/CUDA updates correctly. Check whether inherited release-age/timestamp requirements block wheel updates; scope any necessary exception to these dependencies.
- [ ] Rename existing `requirements-cu130.txt` files and update every build, ignore-list, test, documentation and Renovate reference. Replace hardcoded cu130 parity assumptions with CUDA suffix recognition and CPU/CUDA release parity.
- [ ] Inspect repository auto-merge availability and branch rules. Require stable check names covering ComfyUI generic/GGUF builds, Timestral CPU/CUDA builds, runtime/API tests, lint and Renovate policy validation before automatic merging. Account for path-filtered workflows so required checks do not remain pending on unrelated PRs. Enable repository auto merge if needed and authorized; report any missing repository administration access rather than claiming the gate exists.
- [ ] Verify failing or pending checks prevent merge. Run all image builds on GitHub; merge only passing updates. Treat hardware GPU inference checks as separate release/promotion evidence, not something CPU runners establish.
- [ ] Update PR description and documentation with the final latest-stable/auto-merge policy and commit the changes.

## Task 3: Final review and release evidence

**Files:** Update the verification notes in `comfyui/README.md` and correct stale CUDA/TorchAudio claims in `kubernetes/registry/apps/comfyui/README.md` and `timestral/docs/python-3.15.md`. Read `kubernetes/registry/AGENTS.md` before editing that repository. Documentation changes must distinguish the proposed image from the deployed image.

- [ ] Run the repository's relevant image/runtime unittest suites and Dockerfile lint workflow. Summarize results and inspect the complete diff for unrelated changes.
- [ ] Verify final images contain the expected Python/Torch variants and no system CUDA toolkit installation; verify CPU Timestral has no CUDA runtime dependencies.
- [ ] Record the source/binary dependency findings, exact image identities, build results, and any unresolved packaging issues. Do not claim GPU inference or performance based on CPU-mode startup.
- [ ] Prepare a separate release checklist: on an NVIDIA node, verify driver discovery, Torch CUDA operation, Kitchen native CUDA availability, and representative quantized/GGUF workflows before production promotion. Do not execute deployment as part of this plan.
- [ ] Report changes, evidence, and the remaining release checks for review. Keep all publishing/deployment work outside this change.

## Follow-up: Reproducible complete dependency graphs

Resolve this separately after the migration: lock ComfyUI's complete application dependencies and Timestral's CUDA variant with hashes, regenerate on Renovate updates, and install without unconstrained transitive resolution. This has its own resolver/index and CPU/CUDA variant design; direct wheel pins in Task 2 do not solve it.
