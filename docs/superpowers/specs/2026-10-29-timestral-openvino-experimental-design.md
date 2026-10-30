# Experimental Timestral-5M OpenVINO publication

## Intent and scope

Turn the successful throwaway conversion into a reproducible experimental artifact
release for OVMS on Intel CPU. Publish the OpenVINO neural block to Hugging Face;
do not advertise a complete Timestral forecasting API or deploy to a cluster.

The user accepted model-artifact publication after the lean experiment and
specified GitHub Actions, with repository settings managed in `infra/github`.
Use the existing `m11s-io/docker-images` repository. The Hugging Face destination
namespace remains to be selected; the connected HF tools are anonymous.

## Approaches

1. OVMS Python handler executing the unchanged PyTorch forecaster: easiest route to
   full forecasting behavior but does not demonstrate OpenVINO acceleration.
2. Export the neural block as OpenVINO IR and preserve orchestration outside that
   graph: selected direction after discussion and successful experiment. Enables
   standard OVMS serving; full forecasting needs a later Python handler/adapter.

This first release covers only approach 2's validated fixed-shape block. A custom
OVMS image and full forecasting handler are separate follow-up work.

## Artifact contract

- Source code commit: `a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff`.
- Source model: `mistralai/Timestral-5M` at
  `bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f`.
- FP32 weights and CPU inference precision hint.
- Inputs: `context` FP32 `[1,128]`, `observed` BOOL `[1,128]`.
- Output: `quantiles` FP32 `[1,32,21]`; source quantile levels in metadata.
- No covariates, variable dimensions, multi-block decoding or full `/forecast` API.
- Suggested destination name: `Timestral-5M-OpenVINO-experimental` under the user's
  chosen HF namespace. This name is a proposal, not an existing repository.
- Publish version-directory IR files, source configuration, quantile metadata,
  source license/attribution, model card, checksums and validation report together.
- Record the returned immutable HF commit; deployments must pin that revision.

## Export and validation

Pin a separate export environment rather than changing the production CPU/CUDA/ROCm
dependencies. The experiment used Python 3.12, PyTorch 2.6.0+cpu and OpenVINO
2026.4.1. Lock its dependencies before CI use.

Apply two explicit conversion compatibility rewrites to a temporary source copy:
nonoverlapping `unfold` to `unflatten`, and boolean `cummax` to `cumsum > 0`.
Verify expected source matches and fail if it has changed. Compare against
unmodified upstream PyTorch; do not compare only against the patched exporter.

Gate publication on finite outputs, exact shapes, all 21 quantiles and
`rtol=1e-4, atol=1e-4` parity for random, sinusoidal, constant, scattered-missing
and leading-missing examples. Run an actual KServe REST request against the
exported IR in pinned OVMS 2026.4.1. Failed validation must prevent upload.

The existing result was x86 emulation on Apple ARM. CI must record architecture
and CPU vendor. Claim Intel validation only when a native x86-64 Intel worker is
confirmed; do not infer Intel hardware from a GitHub-hosted runner label. Performance claims
require a separate representative benchmark on actual Intel hardware.

## CI authentication and publishing

Use GitHub Actions OIDC and a repo-scoped HF trusted publisher, not a persistent
HF write token. On the HF model repo's Settings → Trusted Publishers, select
GitHub Actions and configure these exact publisher claims:

- `repository`: `m11s-io/docker-images`
- `branch`: `main`
- `workflow`: `timestral-openvino.yaml`

Place the workflow at `.github/workflows/timestral-openvino.yaml`. Only the
publishing job receives `id-token: write`; validation jobs need `contents: read`
and no HF write credentials. The publish job runs only on `refs/heads/main`
after export, parity checks and the OVMS HTTP check have succeeded. PR validation
does not publish. Use workflow dispatch for the initial experimental release.

The publishing job requests an ID token with audience `https://huggingface.co`.
Set `HF_OIDC_RESOURCE` to the selected HF model repo. The pinned `hf` CLI handles
GitHub's ID token request and token exchange automatically; no `HF_OIDC_ID_TOKEN`
or stored HF write token is needed. Serialize publishes to the same destination
and include CI/source provenance. Do not grant organization-wide default token
permissions for this job; workflow-scoped permissions are sufficient.

`infra/github/repositories.tf` already manages the repository and its `main`
branch protection. Keep the existing required checks. Manage the non-secret HF
destination as the repository Actions variable `HF_TIMESTRAL_OPENVINO_REPO`
through `infra/github`, once the destination is known. Any chosen runner setting
belongs there too. The HF-side trusted publisher must be configured on Hugging
Face; the GitHub OpenTofu provider cannot create that external trust relationship.
No GitLab infrastructure or pipeline configuration is part of this work.

Account Authentication → CI/CD Access provides read access and is not the
configuration needed for artifact publication. Public upstream model downloads
do not require account-level CI access.

Reference: https://huggingface.co/docs/hub/trusted-publishers

## Review and outstanding configuration

The initial deliverable is an exporter, validation job and OIDC publishing job,
plus explicit experimental documentation. Build and validate artifacts before
running the publishing job. No registry image or live deployment is needed for
the raw block, which the standard OVMS image already served in the experiment.

Still needed: HF destination namespace/repo, native Intel
runner availability and the repo trusted publisher setup. No model has yet been
published and no GitHub export/publishing workflow has yet been added or run.
