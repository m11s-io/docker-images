# Standard V2 migration

The standard-serving work is a candidate until real-image REST/gRPC, unchanged
upstream final-forecast parity and device acceptance have passed. Existing
`latest-cpu`/`latest-cuda` and `/forecast` remain the legacy contract. Do not
publish an incompatible serving change to these aliases.

## Preserved rollback

Read-only verification on 2026-10-30 matched the checked-in original service:

- Image: `m11s/timestral@sha256:18fdc4b87b50dbdc389cc528110e7d856b54aa657512fd21a869eee33131fd03`
- Model: `mistralai/Timestral-209M`
- Revision: `9874d252ab0aae16f7f7c999f98f98d6ad7d8365`
- Internal service: `http://timestral-timestral.svc.cluster.local`, POST `/forecast`.

Keep that service and its cache available during migration. Preserve each
client's endpoint/configuration for rollback. No model-size substitution: a 5M
preview is never evidence for a 209M cutover.

## Gates and order

1. Resolve compatible source/framework locks from runtime-matrix.md. Validate
   pure contract, malformed inputs, official protocol round trips and all 21
   quantiles before adopting the shared handler.
2. Prove CPU standard REST and gRPC with pinned Triton clients against a real
   candidate image; compare same-model final forecasts with upstream, including
   covariates, options, missingness, grouped rows and decode blocks.
3. Prove CUDA/ROCm on actual target hardware, including parameter residency,
   expected vendor/architecture, final forecast parity and missing-device errors.
   Unsupported or unavailable hardware stays pending; it cannot be promoted.
4. Keep direct OpenVINO experimental with a versioned capability/profile matrix.
   Validate its CPU properties and no neural PyTorch fallback. Publish new
   artifacts only after validation, through the unchanged OIDC trust identity.
5. Publish accepted candidates under immutable candidate/version tags. Prepare
   namespaced, explicitly selected ServingRuntime/InferenceService resources for
   plt alongside the original endpoint. Review rendered catalogs and Argo diffs.
6. Obtain rollout authorization before deploying new services. Record loaded
   image/model/artifact revisions, device and same-model sustained benchmarks.
7. Inventory every `/forecast` caller and verify its V2 translation with the real
   client. Roll gradually only after acceptance and explicit cutover approval.
   Revert the caller endpoint/configuration to the preserved service on parity,
   readiness, error or latency regressions.
8. Retire the old service and remove its wrapper only when unused and explicitly
   authorized. Stable aliases follow accepted clients and hardware, not builds.

No rollout, client cutover, artifact publication, stable-tag update or old-service
retirement is authorized by the implementation plan alone. Candidate build code
must keep those operations gated. Triton compatibility covers tested standard
inference, metadata and readiness only; extensions require separate evidence.

## Initial caller inventory

A read-only scan of managed product, platform and registry sources found the
legacy service documentation but no configured product caller of this endpoint.
The wrapper's own tests and benchmark are reference callers. This does not prove
that unmanaged or external callers are absent. Obtain the endpoint owner's
complete caller inventory and traffic evidence before cutover or retirement.
No legacy wrapper, dependency or reference test has been removed.

## Hardware-acceptance candidates

The manual `timestral-candidates.yaml` workflow runs only on `main` and publishes
CPU/CUDA/ROCm/OpenVINO images for isolated acceptance jobs. Each tag contains the complete
source commit, workflow run ID, attempt, and variant; it is never reused by a
subsequent run. Use the recorded `m11s/timestral@sha256:...` reference in jobs.
The `timestral-acceptance-<variant>` artifacts record these identities and mark
hardware acceptance pending. These images are test inputs, not promoted releases;
ordinary builds still cannot publish Timestral or update the legacy aliases.
