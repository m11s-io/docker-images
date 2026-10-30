# Timestral project structure review

Scope: only the Timestral image family and the CI paths that build it.

## Chosen layout

```text
timestral/
  Dockerfile.cpu
  Dockerfile.cuda
  Dockerfile.ovms
  .dockerignore
  app/                         existing CPU/CUDA API
  tests/                       existing API/inference tests
  benchmarks/                  existing API benchmarks
  pyproject.toml, uv.lock       existing API environment
  ovms/
    adapter/                   KServe Python node and OpenVINO backend
    export/                    model export, parity and HF publication tools
    tests/                     adapter contract and actual-image integration
    fetch_source.py            hash-verified immutable upstream source
    pyproject.toml, uv.lock     embedded-Python-compatible runtime environment
    README.md
  docs/
```

## Concrete issues corrected

- The earlier top-level `timestral-openvino` split one product across directories.
  Export tools now live under `timestral/ovms/export`, beside their consumer.
- The shared Timestral `.dockerignore` originally admitted only API files. It
  now also admits the OVMS runtime source and lock, while excluding export tools,
  test fixtures and caches. Each Dockerfile copies only its variant inputs; a
  separate ignore file is unnecessary.
- The broad `timestral/**` CPU/CUDA filters would rebuild API variants for every
  OVMS-only edit. Explicit exclusions route those changes to dedicated OVMS
  validation. Shared API changes retain the existing routing.
- The HF publishing workflow filename stays `timestral-openvino.yaml`: external
  trusted-publisher claims bind that name. Only its paths/working directories
  move. Publication stays manual, main-only, validation-gated and repo-scoped.

## Boundaries worth keeping

The existing API and embedded OVMS Python versions differ. Their separate locks
are intentional, not duplicate dependency management to merge blindly. Export
conversion has its own dependency requirements and remains isolated too.

Do not combine the API into the OVMS image or make the image carry model weights.
Do not add a generic shared module layer just for the small amount of tensor
validation: the API accepts batches/covariates/nulls, while the current OVMS
candidate has a deliberately narrower tensor contract. Consolidate only once
actual shared semantics and tests justify it.

Keep source tests colocated with their runtime; repository-level scripts should
contain only cross-image CI contracts. Keep real-image forecast integration in
the dedicated workflow. Historical plans are an execution record and retain old
paths; maintained documentation and CI use the new paths.

## What remains before replacing a service

The derived image and adapter are candidates until the actual image build and
standard-API final-forecast integration pass. They currently target bounded5M
single-series/no-covariate support, not209M or full arbitrary feature coverage.
Real gRPC checks, verified versioned profile artifacts and a reviewed GitOps
rollout remain delivery gates. No API service is retired by this cleanup.
