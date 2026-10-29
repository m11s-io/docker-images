# Timestral Forecast API

This service wraps the upstream [`TimestralForecaster.forecast`](https://github.com/mistralai/timestral) API. It loads one checkpoint per process and serves forecasts on port `8000`. Run one Uvicorn worker per pod so the process uses one model and admits one forecast at a time.

## Checkpoint and startup

`MODEL_ID` defaults to `mistralai/Timestral-209M`. `MODEL_REVISION` is required
and must be a full 40-character commit hash from the selected Hugging Face
model repository. Set both values to select a different compatible checkpoint;
the same CPU, CUDA, or ROCm image can load each size. The upstream Timestral family
includes 5M, 28M, 123M, and 209M checkpoints. Known immutable revisions are:

| Checkpoint | Revision |
| --- | --- |
| `mistralai/Timestral-5M` (smoke test) | `bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f` |
| `mistralai/Timestral-28M` (benchmark) | `49b26409ac87b5935539a5d8ffe7f397b720db47` |
| `mistralai/Timestral-123M` | `5a147287addda85f6acd8da3fb8858fe9af7e8f7` |
| `mistralai/Timestral-209M` | `9874d252ab0aae16f7f7c999f98f98d6ad7d8365` |

Model weights are downloaded to `HF_HOME` (default `/models/huggingface`). The cache must be writable. Set `HF_TOKEN` only when Hugging Face access requires it; it is treated as a secret and is never included in API errors. Startup fails if model loading fails or if `MODEL_DEVICE=cuda` but CUDA is unavailable. The service does not fall back to CPU.

## HTTP contract

`POST /forecast` accepts a JSON object:

```json
{
  "context": [[[1.0, 2.0, null, 4.0]]],
  "prediction_length": 1,
  "observation_mask": [[[true, true, true, false]]],
  "past_covariates": [[[0.0, 1.0, 0.0, 1.0]]],
  "known_covariates": [[[0.0, 1.0, 0.0, 1.0, 0.0]]],
  "categorical_past_covariates": [[[1, 2, 1, 3]]],
  "categorical_known_covariates": [[[1, 2, 1, 3, 2]]],
  "symmetric_averaging": true,
  "clip_nonnegative": true
}
```

`context` is strictly `[batch, variates, time]`. `null` means a missing numerical observation and is passed upstream as NaN. The optional boolean mask has the same shape. Numeric and categorical past covariates are `[batch, covariates, context_time]`; known-future covariates are `[batch, covariates, context_time + prediction_length]`. Categorical codes retain the upstream target-encoding behavior. `symmetric_averaging` and `clip_nonnegative` default to the upstream defaults (`true`).

Success returns the model id, immutable revision, quantile levels, quantiles shaped `[batch, variates, prediction_length, 21]`, and median shaped `[batch, variates, prediction_length]`:

```json
{
  "model": "mistralai/Timestral-209M",
  "revision": "9874d252ab0aae16f7f7c999f98f98d6ad7d8365",
  "quantile_levels": [0.01, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.99],
  "quantiles": [[[[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 2.1]]]],
  "median": [[[1.1]]]
}
```

The numeric values in this example are illustrative. Endpoints `GET /healthz` and `GET /readyz` do not run inference. Readiness returns `503` until the checkpoint has loaded.

| Status | Meaning |
| --- | --- |
| `413` | Declared or streamed request body exceeds the configured byte limit |
| `422` | Invalid JSON fields, shape, values or configured work budget |
| `503` | Model is not ready or another inference is using the single slot |
| `500` | Inference failed or upstream returned an invalid/nonfinite forecast |

Errors do not include request series, tokens or upstream exception text. A disconnected/cancelled request does not stop a running PyTorch call; the inference slot stays occupied until that call actually finishes.

## Configuration

All names below are environment variables. Limits apply before converting request arrays to tensors or starting inference. The row budget counts target and covariate rows together; the output budget counts quantile elements.

| Variable | Default | Purpose |
| --- | --- | --- |
| `MODEL_ID` | `mistralai/Timestral-209M` | Hugging Face model repository id |
| `MODEL_REVISION` | required | Full immutable 40-character model commit |
| `MODEL_DEVICE` | `cpu` | `cpu` or `cuda`; CUDA never falls back silently |
| `HF_HOME` | `/models/huggingface` | Writable Hugging Face cache directory |
| `HF_TOKEN` | unset | Optional secret for gated/private model access |
| `TORCH_NUM_THREADS` | `2` | CPU thread count configured at startup |
| `MAX_REQUEST_BYTES` | `8388608` | Maximum JSON body size (8 MiB) |
| `MAX_BATCH_SIZE` | `8` | Maximum batch dimension |
| `MAX_ROWS_PER_SERIES` | `32` | Maximum target-plus-covariate row count |
| `MAX_CONTEXT_STEPS` | `32768` | Maximum context length |
| `MAX_PREDICTION_LENGTH` | `1024` | Maximum forecast horizon |
| `MAX_OUTPUT_ELEMENTS` | `1000000` | Maximum quantile output elements |

Every limit must be a positive integer. Invalid configuration, missing revision, unwritable cache, model load errors and unavailable CUDA cause startup failure.

## Running locally

With Python 3.15 and `uv` installed on Linux:

```sh
export MODEL_REVISION=9874d252ab0aae16f7f7c999f98f98d6ad7d8365
export MODEL_DEVICE=cpu
export HF_HOME="$PWD/.model-cache"
uv sync --frozen
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Python 3.15 PyTorch wheels are available for Linux through the official PyTorch indexes. On macOS, use the Linux container to run this service.

CUDA uses the same service code. The CUDA image installs the pinned CUDA PyTorch wheel. For a local venv, install the matching wheel after syncing the locked app dependencies, then run Uvicorn with `--no-sync` so uv does not restore the CPU wheel:

```sh
export MODEL_REVISION=9874d252ab0aae16f7f7c999f98f98d6ad7d8365
export MODEL_DEVICE=cuda
uv sync --frozen --no-dev --no-install-package torch
CUDA_CHANNEL=$(sed -n 's/^torch==[^+]*+\(cu[0-9]*\)$/\1/p' requirements-cuda.txt)
uv pip install --python .venv/bin/python \
  --index-url "https://download.pytorch.org/whl/$CUDA_CHANNEL" -r requirements-cuda.txt
uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

The CUDA runtime version follows the pinned PyTorch wheel in `requirements-cuda.txt`. Renovate updates stable CUDA variants and the matching CPU Torch release together, then auto merges after required GitHub checks pass. The host driver must support the selected runtime, and the container must receive a GPU. Setting `MODEL_DEVICE=cuda` does not allocate a GPU by itself.
## Tests and benchmarks

The API unit tests use an injected forecaster double and need no checkpoint:

```sh
uv run pytest tests/test_api.py -q
```

The real CPU HTTP-vs-upstream smoke test is opt-in because it downloads the pinned 5M checkpoint:

```sh
TIMESTRAL_RUN_REAL_TESTS=1 uv run pytest tests/test_inference.py -m cpu -q
```

`benchmarks/benchmark.py` accepts selectable model, context, horizon, variate and numeric-covariate cases. It emits one JSON record per case with cold load time, warm p50/p95 latency and peak memory. Its defaults describe the larger sizing matrix; narrow arguments make an initial practical run manageable:

```sh
uv run python benchmarks/benchmark.py --models 28M --contexts 512 --horizons 96 --variates 1 --covariates none --repeats 2
```

Timestral inference is synchronous and compute-bound. This service intentionally allows one active forecast per process; scale replicas based on measured model-specific memory and latency. The configured API limits are admission safeguards, not performance guarantees.

## AMD ROCm image

The `-rocm` and `latest-rocm` tags use AMD's ROCm 10.1.0 / PyTorch 2.14.0 / Python 3.14 image on Ubuntu 26.04, pinned by digest. This variant runs the same API code and checkpoints as CPU and NVIDIA. It preserves the base image's PyTorch/ROCm installation and installs a separate hash-locked API dependency set compatible with that Python. See `Dockerfile.rocm` for the exact runtime versions.

Use `MODEL_DEVICE=cuda` on AMD too: PyTorch ROCm exposes the `torch.cuda` interface. A compatible host driver and supported GPU architecture are required. With Docker, expose `/dev/kfd` and the appropriate `/dev/dri` render device and supply the host's device group permissions. With Kubernetes, use the AMD device plugin and request `amd.com/gpu: 1`; see the chart's ROCm example. Do not use an NVIDIA runtime class.

The process runs as a nonroot user. Mount a writable model cache at `/models` and writable temporary storage at `/tmp`; ROCm compilation caches are directed there. The validated base is large, so allow for a slow first image pull. Weights are downloaded at startup, not baked into the image.

Regenerate the API lock from the repository root with:

```sh
uv pip compile timestral/requirements-rocm.in --python-version 3.14 --python-platform x86_64-manylinux_2_28 --generate-hashes -o timestral/requirements-rocm.txt
```

Keep the FastAPI, Pydantic Settings, and Uvicorn pins aligned with `pyproject.toml`. The ROCm lock excludes PyTorch, which must remain supplied by the AMD base. Local `uv sync` continues to select the CPU development environment.

ROCm uses its own `requirements-torch-rocm.txt` constraints; CPU and CUDA pins
remain independent. The image runs `pip check` and verifies the exact Torch
version and HIP backend before adding API test dependencies. The application uses a virtual environment that inherits AMD's installed Torch
without uninstalling distro-managed packages. Tests run in a disposable image
stage constrained by the complete runtime inventory, so test installation cannot
upgrade a runtime package and hide a dependency failure.

Regenerate the test-only lock after the API lock:

```sh
uv pip compile timestral/requirements-rocm-test.in --constraint timestral/requirements-rocm.txt --python-version 3.14 --python-platform x86_64-manylinux_2_28 --generate-hashes -o timestral/requirements-rocm-test.txt
```

The earlier gfx1201 forecast probe used the older ROCm stack. This updated
image still requires a tensor/forecast acceptance run on the intended AMD node;
CPU CI API tests do not establish GPU execution.
