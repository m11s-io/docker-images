# ComfyUI Dependency Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Upgrade the generic and GGUF images together and verify dependency resolution, startup, and GPU execution.

**Architecture:** Keep the existing source-built ComfyUI image and GGUF derivative. Update upstream pins, build the generic image first, and pass its exact output digest to the GGUF build so both variants contain the same release.

**Tech Stack:** Docker Buildx, CUDA/cuDNN, Ubuntu 22.04, Python 3.14, PyTorch, GitHub Actions.

**Spec:** Bounded design in this conversation; this document is the explicitly requested plan. Review before implementation.

## Global Constraints

- Keep Ubuntu 22.04, Python 3.14, non-root UID/GID 10001, port 8188, and existing volume paths.
- CUDA base: `13.4.2-cudnn-runtime-ubuntu22.04@sha256:d5982da4024f00929ce8297a901f2c962b9fb06e3b9df2fdca35ecbdcd6754ee`.
- ComfyUI: `v0.39.0`; torch: `2.14.1+cu130`; torchvision: `0.29.1+cu130`.
- Preserve GGUF commit `6ea2651e7df66d7585f6ffee804b20e92fb38b8a`.
- Proposed image release: `0.5.5` and `0.5.5-gguf`; update documentation and workflow tags together.
- Do not deploy or publish as part of local validation.

## Review Focus

- TorchAudio 2.11 versus torch 2.14 native compatibility: inspect wheel metadata and ComfyUI usage before deciding whether to retain it.
- Python 3.14 wheel coverage: require successful amd64 image build and `pip check`.
- Host driver compatibility: check NVIDIA's CUDA 13.4 requirements against the target host before GPU testing.
- GGUF parent drift: derivative must use the generic image produced by this build.
- No-push CI path: derivative must also consume the new generic image when `skip_push=true`.

### Task 1: Upgrade and validate the generic image

**Files:** `comfyui/Dockerfile`, `comfyui/README.md`, `.github/workflows/build.yaml`.

**Interfaces:** Produces a locally tested `m11s/comfyui:0.5.5` image; publishing CI exposes the build's digest for Task 2.

- [x] Inspect ComfyUI v0.39.0 audio code and TorchAudio wheel requirements. v0.39.0 removes TorchAudio from requirements; remove the explicit install and constraint if upstream no longer requires it. If required, resolve a supported combination before proceeding; matching CUDA labels alone do not prove compatibility.
- [x] Update CUDA, ComfyUI, torch, and torchvision to the exact pins above. Update both install commands and pip constraints, and correct related comments.
- [x] Update generic release tags and README to 0.5.5. Describe the actual CUDA and upstream versions consistently.
- [x] Run `docker buildx build --platform linux/amd64 --load -t m11s/comfyui:0.5.5 ./comfyui`. Expected: complete dependency installation and successful image build.
- [x] Run `docker run --rm --entrypoint python3.14 m11s/comfyui:0.5.5 -m pip check`. Expected: no broken requirements.
- [x] Run a container import check for torch, torchvision, and ComfyUI's audio dependencies; assert torch/torchvision versions equal the exact pins and `torch.version.cuda == '13.0'`.
- [ ] On a compatible NVIDIA host, verify `torch.cuda.is_available()`, perform a CUDA tensor operation, start the normal entrypoint, and request `/system_stats`. Expected: successful GPU operation, HTTP 200, and no startup traceback. Record unavailable GPU access as an unverified check.
- [x] Review diff and commit the validated generic-image changes.

### Task 2: Keep GGUF on the same build and validate both release paths

**Files:** `comfyui/Dockerfile.gguf`, `.github/workflows/build.yaml`, `comfyui/README.md`.

**Interfaces:** Consumes Task 1's generic image. Produces `m11s/comfyui:0.5.5-gguf` with the same ComfyUI and PyTorch versions.

- [x] Add `ARG COMFYUI_BASE` before the GGUF `FROM`, retaining a digest-pinned published parent as its standalone default until the new release digest exists. Use `FROM ${COMFYUI_BASE}`.
- [x] Give the generic publishing build an output ID and pass `COMFYUI_BASE=m11s/comfyui@<that build's digest>` to the GGUF publishing build. Do not invent a future digest or push from the local workspace to obtain one.
- [x] For `skip_push=true`, load the generic linux/amd64 build into Docker and build the derivative with Docker against that local tag; verify this path does not pull the old pinned parent. Keep the publishing path on the exact registry digest.
- [x] Remove the obsolete 0.5.2 compatibility comment and redundant packages/home-directory setup, now supplied by the generic parent. Keep GGUF ownership and non-root execution.
- [x] Update GGUF workflow and README release tags to 0.5.5-gguf.
- [x] Build the GGUF image locally with `--build-arg COMFYUI_BASE=m11s/comfyui:0.5.5`. Run `pip check`, verify matching torch/ComfyUI versions, and check the pinned GGUF commit.
- [ ] Start the variant on a compatible GPU host, check `/system_stats` and `/object_info`, and confirm the GGUF node loads without import errors. If a GGUF model fixture is available, execute a known workflow and verify output; otherwise record inference as unverified.
- [x] Validate workflow YAML with actionlint if available, run `git diff --check`, and inspect both push/no-push parent-selection paths. After a normal authorized release publishes 0.5.5, advance the standalone default to its real digest.
- [x] Review and commit the GGUF and workflow changes. Report completed checks and remaining GPU/CI limitations before integration.

## Execution results — 2026-10-13

- Implemented directly on main as requested; commits `020178d` and `9edc743`.
- Native amd64 validation passed: https://github.com/m11s-io/docker-images/actions/runs/38348546599 . Both images passed `pip check`, exact PyTorch version checks, audio resampling, CPU server startup, and `/system_stats`. GGUF registered `UnetLoaderGGUF` at `/object_info`.
- Published release: https://github.com/m11s-io/docker-images/actions/runs/38349090368 . Docker Hub tags `0.5.5`/`latest` share `sha256:4ded8163ebd626390e19343c4e7fd6c3b6db1b6a2c3ea4536861704ae7813712`; `0.5.5-gguf`/`latest-gguf` share `sha256:a5306e1834c60a88a05c3d91b8279b9305e7dd105bc6f90609c25b73b5f58240`.
- Standalone GGUF default now pins the real generic 0.5.5 digest. Temporary validation branch removed.
- Final actionlint and extracted smoke-script `bash -n` passed. Independent code review found no blocking defects; its HTTP-timeout suggestion was implemented.
- GPU execution, host driver compatibility, and model inference remain unverified; neither the Mac nor the GitHub runner has the required NVIDIA GPU. The image's `NVIDIA_REQUIRE_CUDA` constraint must also be satisfied by the deployment host.

### Implementation decisions

- Work on main per user instruction; preserve unrelated concurrent DeepSeek changes. Shared-checkout risk was handled by staging only ComfyUI changes.
- Validate this configuration update with actual image builds and runtime checks instead of tests that repeat pins. Hardware behavior remains the verification limit.
- Prepare shared CI/tag edits while the generic build runs; validate the combined result before release.
- Temporarily keep the existing published GGUF fallback until the new digest exists; replace it after publication. No old fallback remains.
- Isolate application Python in `/opt/venv`: the initial global `pip check` failed on Ubuntu's PyGObject metadata and missing pycairo. The isolated environment and both final images pass dependency checks. The runtime must continue using the venv PATH.
- Move validation to GitHub at user request; publish directly from main after explicit publishing authorization. The temporary remote validation branch is deleted.
