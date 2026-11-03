# Standard V2 migration

The repository now contains only the shared official KServe V2 implementation.
The custom `/forecast` app, its dependency roots and tests have been removed.
Current release/flavor image tags use V2. Source cleanup does not change existing
cluster services or prove that all callers have migrated.

## Rollout order

1. Require passing native image/protocol and target-device checks for the exact
   image/model/artifact pins. OpenVINO uses matching v2 bundles; old bounded
   receipts cannot initialize the new runtime.
2. Compare speed and held-out forecast accuracy with matching upstream defaults
   on all four backends. Record actual hardware and capabilities.
3. Prepare separate namespaced service resources alongside existing deployments;
   review exact pins, gateway body limits, resources, Argo behavior and rollback.
4. Obtain rollout authorization, verify the intended endpoint and loaded identity,
   then inventory real caller traffic and implement required V2 translations.
5. Obtain caller-cutover authorization. Verify real requests and retain rollback
   until the old deployment is explicitly approved for retirement.

## Historical rollback reference

Read-only verification on2026-10-30 recorded the old deployment as:

- Image: `m11s/timestral@sha256:18fdc4b87b50dbdc389cc528110e7d856b54aa657512fd21a869eee33131fd03`
- Model/revision: `mistralai/Timestral-209M` / `9874d252ab0aae16f7f7c999f98f98d6ad7d8365`
- Internal endpoint: `http://timestral-timestral.svc.cluster.local`, POST `/forecast`.

Recheck live state before relying on this historical reference. A source scan
found no configured product caller at the time, which does not prove absence
of external/unmanaged callers. Historical receipts remain under
[verification](verification/archived-details.md). No automatic cluster deletion,
client cutover or cache removal follows from this source cleanup.
