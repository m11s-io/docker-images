# Experimental Timestral OpenVINO block export

This separate Python 3.12 project exports only the fixed-shape single-block
neural prediction path. It does not change the existing Timestral API images.
See `model-card.md` for the artifact contract and limitations.

The repository workflow `.github/workflows/timestral-openvino.yaml` runs the heavy validation
on an x86 GitHub-hosted runner. It exports FP32 IR, compares all quantiles against
unmodified pinned upstream, serves the IR through pinned OVMS and performs real
KServe REST requests. The dependency environment is frozen in `uv.lock`.

PRs validate without write credentials. After merge, manually dispatch the
workflow on `main` to validate again and publish to the private destination
`m11s-org/Timestral-5M-OpenVINO-experimental`. The publish job alone has OIDC
permission and reads `HF_TIMESTRAL_OPENVINO_REPO`. No persistent HF token is used.

A failed export, parity comparison, serving check, bundle checksum check or
provenance check prevents publication. Publications are serialized. The job
summary records an immutable HF commit after downloading and verifying every
published file. Pin that revision for downstream use.

To reproduce in an isolated Linux x86-64 environment with Python 3.12, git,
Docker and uv 0.13.5:

```sh
uv sync --frozen
uv run --frozen python -m unittest discover -s tests
uv run --frozen python export.py --output /tmp/timestral-bundle
# Run the OVMS command from the workflow with that bundle mounted read-only.
uv run --frozen python validate_ovms.py --bundle /tmp/timestral-bundle
cp model-card.md /tmp/timestral-bundle/README.md
uv run --frozen python package.py --bundle /tmp/timestral-bundle
```

The output directory must be new. Tests use synthetic data only. Validation
reports record actual observed architecture/CPU; no native Intel or performance
validation is claimed. Full forecasting orchestration, covariates, dynamic
shapes and cluster deployment remain outside this export.

This directory moved from the old top-level `timestral-openvino/` into
`timestral/ovms/export/`. Its published fixed-block artifact remains separate from
the broader forecasting profiles required by the OVMS adapter. Run its commands
from this directory; the workflow filename stays unchanged because HF trust
claims are bound to that exact filename.
