# CUDA Dependency Ownership Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. Do not delegate unless the user requests it.

**Goal:** Remove ComfyUI's redundant system CUDA installation and make the explicitly selected PyTorch dependencies maintainable by Renovate.

**Architecture:** Use a pinned Python base for ComfyUI, with CUDA runtime libraries supplied by the selected PyTorch wheels and driver libraries supplied by the host NVIDIA container runtime. Retain each application's own dependency files; Renovate proposes updates within the selected CUDA channel and CI checks package compatibility. Timestral retains its existing Python base and CPU lock workflow.

**Tech Stack:** Docker Buildx, Python/pip/uv, PyTorch CUDA wheels, Renovate, GitHub Actions, unittest.

**Spec / design basis:** The user's approved direction in the CUDA source-analysis conversation: plain Python base, existing Python/Torch versions preserved initially, prebuilt native helpers, explicit CUDA channel selection, and host driver management kept separate. This document records the implementation choices for review; it does not authorize deployment.

## Global Constraints

- Work in `m11s-io-github/docker-images`; preserve existing uncommitted workflow and documentation changes. Inspect the diff before editing. Create an isolated checkout at execution time if needed.
- Keep ComfyUI `v0.43.0`, Torch `2.14.1+cu130`, TorchVision `0.29.1+cu130`, Python minor `3.14`, and the existing GGUF commit unchanged in the migration.
- Record the old image's exact Python patch and select the same patch in the new official Python slim Debian base, pinned by digest. If unavailable, explicitly review the patch change before implementation.
- Keep Timestral Python `3.15.2`, Torch `2.14.1+cpu` / `2.14.1+cu130`, and its application/source pins unchanged.
- Preserve UID/GID 10001, `/opt/venv`, home/cache ownership, ports, mounts, entrypoint behavior, and generic/GGUF build relationship.
- Fail installation if `comfy-kitchen` or `comfy-aimdo` would require a source build. Do not silently publish an image without its native CUDA backend.
- No driver upgrade, Helm image update, publishing, or deployment in this work. GPU tests validate a release; source and binary dependency inspection establish packaging requirements.
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

**Files:** Create `comfyui/requirements-cu130.txt` and `timestral/requirements-cu130.txt`; modify `comfyui/Dockerfile`, `timestral/Dockerfile.cuda`, `comfyui/verify_image.py`, `scripts/test_timestral_runtime.py`, and `renovate.json`. Add `scripts/test_cuda_renovate.py` for policy behavior where useful.

**Interfaces:** ComfyUI file contains Torch `2.14.1+cu130` and TorchVision `0.29.1+cu130`; Timestral file contains Torch `2.14.1+cu130`. Both declare `--index-url https://download.pytorch.org/whl/cu130`. ComfyUI continues exposing `PIP_CONSTRAINT` to validation and later installs.

- [ ] Move inline wheel pins into these requirements files. For ComfyUI, derive the constraints file from requirement lines, excluding index options, so upstream requirements still resolve from PyPI while respecting Torch pins. Make validation ignore comments/options if it reads the requirements file directly.
- [ ] Change Timestral's existing post-sync CUDA install to consume its requirements file. Keep the CPU `uv.lock` unchanged. Update the existing parity test to read the CUDA requirements file and compare the release portion with `pyproject.toml`.
- [ ] Verify Renovate's requirements manager extracts both files using the CUDA index and retains the `+cu130` variant. Use extraction/lookup output, not regex matching alone. If the selected Renovate release drops local-version compatibility, add a narrowly scoped compatibility/version rule and demonstrate its behavior before continuing.
- [ ] Extend the ComfyUI update group to include `comfyui/requirements-cu130.txt`. Add a Timestral Torch group covering CPU project/lock and CUDA requirements updates. Keep the two applications independently upgradeable.
- [ ] Keep CUDA channel changes manual. Require tests for Torch updates; do not enable version automerge. Preserve the existing Docker digest policy.
- [ ] Test extraction of every current dependency, exclusion of CPU wheels from CUDA proposals, preservation of the CUDA index/channel, ComfyUI grouping, and Timestral CPU/CUDA parity. Confirm all channels/versions exist for the selected Python/platform; a grouped PR is allowed to fail CI if upstream publishes incompatible packages.
- [ ] Run the Renovate config validator, image/runtime script tests, and Timestral API tests via `uv run --frozen pytest tests/test_api.py -q`. Build both Timestral variants and rebuild both ComfyUI variants after changing their install inputs. Ensure requirements changes trigger the existing CI image filters; modify filters only if inspection proves a gap.
- [ ] Document that Renovate proposes available versions but compatibility is established by package/image checks. Review and commit this task separately.

## Task 3: Final review and release evidence

**Files:** Update the verification notes in `comfyui/README.md` and correct stale CUDA/TorchAudio claims in `kubernetes/registry/apps/comfyui/README.md` and `timestral/docs/python-3.15.md`. Read `kubernetes/registry/AGENTS.md` before editing that repository. Documentation changes must distinguish the proposed image from the deployed image.

- [ ] Run the repository's relevant image/runtime unittest suites and Dockerfile lint workflow. Summarize results and inspect the complete diff for unrelated changes.
- [ ] Verify final images contain the expected Python/Torch variants and no system CUDA toolkit installation; verify CPU Timestral has no CUDA runtime dependencies.
- [ ] Record the source/binary dependency findings, exact image identities, build results, and any unresolved packaging issues. Do not claim GPU inference or performance based on CPU-mode startup.
- [ ] Prepare a separate release checklist: on an NVIDIA node, verify driver discovery, Torch CUDA operation, Kitchen native CUDA availability, and representative quantized/GGUF workflows before production promotion. Do not execute deployment as part of this plan.
- [ ] Report changes, evidence, and the remaining release checks for review. Keep all publishing/deployment work outside this change.

## Follow-up: Reproducible complete dependency graphs

Resolve this separately after the migration: lock ComfyUI's complete application dependencies and Timestral's CUDA variant with hashes, regenerate on Renovate updates, and install without unconstrained transitive resolution. This has its own resolver/index and CPU/CUDA variant design; direct wheel pins in Task 2 do not solve it.
