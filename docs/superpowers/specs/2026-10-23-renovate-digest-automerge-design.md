# Renovate Digest Auto-Merge Design

## Intent

Automatically merge Renovate digest-only dependency updates after the affected Docker image build succeeds. These updates preserve the human-readable tag while changing the pinned digest.

## Goals and Constraints

- Run the affected-image build on Renovate digest pull requests without publishing images. Version-update PRs remain manual and do not get an extra pre-merge image build.
- Let Renovate merge digest updates only after the pull request checks pass.
- Keep the existing main-branch build and publish behavior. This means an affected image is built once for PR validation and again after merge for publishing.
- Preserve current path filtering so a change to one image builds only that image; shared tag-resolver changes continue to select all images.
- For a ComfyUI `Dockerfile.gguf`-only digest update, validate the GGUF variant using that file's pinned default instead of rebuilding the generic ComfyUI image. Its default digest is overridden by the current workflow, so the normal pipeline would otherwise fail to exercise the Renovate change.
- Do not auto-merge version changes or other update types.
- Group ComfyUI Dockerfile version updates together so concurrent updates to the same build input, such as ComfyUI and CUDA, share one review/build PR. Keep digest updates separate.

## Approaches

- **PR build, then main build:** Chosen. It gates on the real image build and changes only the required workflow behavior. BuildKit cache remains enabled, but the image build runs twice.
- **Auto-merge after a lightweight PR check:** Cheaper, but the actual image build runs only after merge and cannot gate it.
- **Build once and promote after merge:** Avoids repeating the build, but needs temporary image publication and promotion logic beyond the current pipeline.

## Design

Add pull-request validation for Renovate branches whose topic ends in `-digest`. Set that digest branch topic explicitly in Renovate so the workflow can gate builds without relying on a generated PR title. Reuse changed-image selection, set image publication off for PR runs, and skip Docker Hub description and MCP catalog publishing on PRs. Build only the affected image variant. Renovate auto-merge applies only to Docker datasource digest updates and uses Renovate-managed merging after checks pass, because this repository has no required-check branch protection configured. Group version updates from `comfyui/Dockerfile` under a shared `groupName` and limit that rule to version update types (`major`, `minor`, `patch`), leaving digest updates separate.

## Validation

Review the workflow conditions to confirm only Renovate digest PRs run image builds, PR builds do not publish images or metadata, and only selected image variants build. Confirm the Renovate rule matches digest updates only and waits for status checks, and that the grouping rule combines version updates for `comfyui/Dockerfile` without including digest updates.
