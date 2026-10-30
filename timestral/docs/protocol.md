# Forecast tensor contract, version 1

Candidate KServe V2: POST `/v2/models/timestral/infer` (8080), gRPC
ModelInfer (8081). The official server owns health, metadata, encoding and errors.
No `/forecast` route is added. Triton inference compatibility must be demonstrated
with pinned 2.73.0 HTTP/gRPC clients; repository, shared-memory, sequence,
streaming, ensembles and other Triton extensions are not promised.

| Input | Datatype | Shape | Meaning |
| --- | --- | --- | --- |
| context | FP32 | B,V,T | Required target history |
| observation_mask | BOOL | B,V,T | Required; false marks missing history |
| prediction_length | INT64 | 1 | Required horizon H |
| past_covariates | FP32 | B,C,T | Optional numeric history |
| known_covariates | FP32 | B,C,T+H | Optional numeric history and future |
| categorical_past_covariates | FP64 | B,C,T | Optional category codes |
| categorical_known_covariates | FP64 | B,C,T+H | Optional category codes and future |
| symmetric_averaging | BOOL | 1 | Optional, defaults true |
| clip_nonnegative | BOOL | 1 | Optional, defaults true |

Every present covariate requires a same-shaped BOOL `<tensor_name>_mask`.
An orphan mask is invalid. Finite placeholders are required even where masked;
JSON NaN/infinity/null are invalid. Context missingness goes through the upstream
observation_mask argument. Covariate missingness becomes NaN internally for the
upstream encoder; no new encoding algorithm is introduced. FP64 categorical codes
preserve distinct numbers above 2**24. Each target row needs an observation.
Booleans are not numeric scalars; numeric values are not booleans. All dimensions
are positive. Duplicate/unknown inputs, wrong shape/dtype/content are invalid.

Budgets: 8 MiB decoded tensor payload, B<=8, total rows B*(V+all C)<=32,
T<=32768, 1<=H<=1024, B*V*H*21<=1000000. Declarations are checked before
array decoding. The row/horizon limits currently imply at most 688128 output
quantiles. The output guard remains independent. A runtime may reject capabilities
it cannot execute, but cannot silently change the operation.

The 8 MiB **wire-body** limit also requires transport enforcement: gRPC receive
message limit and an HTTP gateway body limit, including chunked bodies, before
SDK decoding. The inspected ModelServer has no public HTTP body-limit setting;
the handler cannot enforce a pre-decode HTTP byte bound on its own. HTTP deployment
acceptance is pending that gateway validation. Tensor budgets do not replace it.

Outputs, in this order: `quantiles` FP32[B,V,H,21], `median` FP32[B,V,H],
`quantile_levels` FP32[21]. Quantile levels must be finite, strictly increasing,
in [0,1], include exactly one 0.5 and match all 21 channels. Median is that
channel. Request ID is preserved. The standard response parameters identify
`contract_version=1`; the shared handler adds `model_id`, `model_revision` and
backend identity. Model identity is independent of runtime variant.

Invalid/unsupported input uses KServe InvalidInput (REST 400, gRPC
INVALID_ARGUMENT). Occupied capacity or unready model uses ModelNotReady
(REST 503, gRPC UNAVAILABLE). Internal failures are redacted. Cancellation does
not free the inference slot until the underlying computation has stopped.

## Inspected SDK/client interoperability details

Triton 2.73.0 JSON inference must pass
`headers={"content-type": "application/json"}`. Binary inference uses the
client's standard binary header. With the inspected KServe source, health
responses have bodies whereas Triton's HTTP readiness methods do not drain them.
Use a separate context-managed HTTP client for each readiness probe, closing it
before using an inference client. Reusing a concurrency=1 client for repeated
readiness probes can exhaust its pool. The diagnostic tests cover this explicit
usage; unrestricted readiness-client reuse is not an accepted capability.

The entry point configures specific exception handlers on the official SDK app
through its public application API. This covers schema and binary decoding
failures that happen before Model.predict: responses use a generic 400 and the
exceptions are not stringified or logged. No inference routes or separate HTTP
application/server are added. Actual-image malformed-transport tests cover
missing datatypes, malformed JSON/headers and truncated binary tensors. gRPC
startup rejects nonpositive/unlimited receive limits as well as limits above
8 MiB.
