# Standard V2 migration

The repository contains only the shared KServe V2 implementation. The custom
`/forecast` wrapper, its dependency roots and tests have been removed at the
user's request. Current release/flavor tags serve KServe V2. Older deployed
images remain separate operational resources until a deliberate client cutover.

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
8. Retire any remaining old deployment only after an authorized caller cutover.
   Source cleanup alone does not change cluster services.

No rollout, client cutover, artifact publication, stable-tag update or old-service
retirement is authorized by the implementation plan alone. Candidate build code
must keep those operations gated. Triton compatibility covers tested standard
inference, metadata and readiness only; extensions require separate evidence.

## Initial caller inventory

A read-only scan of managed product, platform and registry sources found the
legacy service documentation but no configured product caller of this endpoint.
The removed wrapper previously had reference callers in its tests. This does not prove
that unmanaged or external callers are absent. Obtain the endpoint owner's
complete caller inventory and traffic evidence before cutover or retirement.
Legacy wrapper code, dependencies and tests have been removed. Historical image
digests and verification receipts remain for provenance and rollback.

## Hardware validation images

The normal build workflow publishes CPU/CUDA/ROCm/OpenVINO images using
`<version>-<flavor>`, `latest-<flavor>`, and `sha-<commit>-<flavor>` tags.
Pin a published digest for isolated validation jobs. The former acceptance-tag
publishing workflow is retired; earlier receipts remain historical records.
