# Renovate Digest Auto-Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-merge Renovate digest-only PRs after their affected Docker build succeeds, and group ComfyUI Dockerfile version updates together.

**Architecture:** Renovate enables auto-merge only for `digest` updates and lets Renovate merge after checks pass. The workflow runs on PRs, but gates expensive image builds to Renovate digest PRs; the existing main-branch workflow continues to publish after merge. ComfyUI GGUF-only digest changes get a targeted build that uses the changed default digest.

**Tech Stack:** Renovate JSON configuration; GitHub Actions YAML; Docker Buildx.

**Spec:** `docs/superpowers/specs/2026-10-23-renovate-digest-automerge-design.md`

## Global Constraints

- Only Docker datasource Renovate `digest` updates are auto-merged.
- PR image builds must not publish images, Docker Hub descriptions, or the MCP catalog.
- Only affected image contexts and variants should build on a digest PR.
- `comfyui/Dockerfile.gguf` digest updates must validate the pinned default they change; CI must not override it with a freshly built generic image for that case.
- ComfyUI version updates in `comfyui/Dockerfile` are grouped for `major`, `minor`, and `patch` update types; digest updates remain separate.
- Main-branch image publishing keeps its current behavior.

## Review Focus

- A non-digest Renovate PR must not run the extra image build or become auto-mergeable; gate workflow build jobs on the explicit Renovate `-digest` branch suffix.
- A Dockerfile digest PR must build only its affected image context; verify the paths-filter output is used by both generic and native build paths.
- A GGUF-only digest PR must build GGUF from `Dockerfile.gguf`'s updated pinned default and must skip the generic base build; inspect the generated build-args and step conditions.
- PR jobs must not publish; inspect every Docker push, Docker Hub description, native description, and MCP catalog condition for the PR event.
- A grouped ComfyUI version PR must exclude `digest` update types; confirm both rules' `matchUpdateTypes` are disjoint.

---

### Task 1: Configure digest auto-merge and ComfyUI grouping

**Files:**
- Modify: `renovate.json`

- [x] Add a package rule matching Docker datasource `matchUpdateTypes: ["digest"]`, with `automerge: true` and `platformAutomerge: false` so Renovate waits for green checks before merging without relying on the repository's missing branch-protection rule.
- [x] Add a package rule matching `matchFileNames: ["comfyui/Dockerfile"]` and `matchUpdateTypes: ["major", "minor", "patch"]`, with group name `ComfyUI Dockerfile dependencies`.
- [x] Pin the digest `branchTopic` suffix to `-digest`; parse `renovate.json` as JSON and review rule ordering and scopes.

### Task 2: Build digest PRs without publishing

**Files:**
- Modify: `.github/workflows/build.yaml`

- [x] Add a `pull_request` trigger without path exclusions so Renovate digest branches always receive a workflow result; extend the `changes` job to handle pull requests and grant the `pull-requests: read` permission needed by `dorny/paths-filter`.
- [x] Run image builds on PRs only when the source branch is Renovate-managed and ends in the digest branch suffix; preserve changed-image selection to select contexts.
- [x] Make Docker image builds use `push: false` for PRs, load local ComfyUI images for smoke checks, and skip Docker Hub login/description, native description, and MCP catalog publication on PRs.
- [x] Add dedicated ComfyUI generic and GGUF file-change outputs. For GGUF-only digest PRs, skip the generic ComfyUI build and build `Dockerfile.gguf` without a `COMFYUI_BASE` override. Keep the existing generic-to-GGUF flow for generic ComfyUI digest PRs and main pushes.
- [x] Map `pull_request` to the existing changed-image selection path for `native_image_matrix.py`, retaining workflow-dispatch selection behavior.
- [x] Parse workflow YAML and review publication conditions. `actionlint` is not installed; no image publishing or tests were run.
