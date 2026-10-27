# Python 3.15 migration

The service targets Python 3.15.2 on Linux AMD64. Its API and upstream Timestral
source revision are unchanged. NumPy advances from 2.2.6 to 2.5.4 so installation
can use Python 3.15 wheels. Both images use PyTorch 2.14.1, selecting the CPU or
CUDA 12.6 distribution explicitly.

CPU installation uses the committed `uv.lock` directly. The CUDA image replaces
the CPU distribution with `torch==2.14.1+cu126` from the official PyTorch index.
That wheel supplies its CUDA userspace dependencies. Both images use the same
Debian Python base, avoiding a copy of CPython from Debian into Ubuntu. NVIDIA
drivers and GPU access still come from the host/container runtime.

CI runs Python 3.15 and checks that the project, both image bases, and CI agree
on the Python minor version and PyTorch release. Renovate may update Python
within 3.15; later minor upgrades need another compatibility check.

## Verification

On 2026-10-27, the Linux AMD64 CPU image built successfully under Docker Desktop
on an ARM64 host. Under its nonroot UID 10001 and a read-only root filesystem,
it imported the application, SSL, SQLite, ctypes, NumPy and PyTorch successfully:

- Python 3.15.2
- NumPy 2.5.4
- PyTorch 2.14.1+cpu, with no CUDA runtime

The API suite and pinned 5M real-checkpoint smoke test passed inside this image:
**32 passed**. The smoke compares HTTP forecasts with direct upstream forecasts
and covers missing values plus numeric/categorical past and known covariates.
The repository image/runtime regression suite passed: **23 tests**.

The test suite reports an existing Starlette/AnyIO deprecation warning. These
checks establish functional compatibility, not performance on target nodes.
Actual NVIDIA GPU execution is not validated by a CPU-only Docker host.
The CUDA dependency resolver found compatible Python 3.15 wheels, but the local
image build was stopped during prolonged multi-gigabyte downloads. The complete
CUDA image build and NVIDIA execution remain release checks. CUDA transitive
artifacts are resolved separately from the CPU `uv.lock`, as in the previous
image; they are not covered by the CPU lock's hashes.

To repeat on a Linux Python 3.15 host:

```sh
uv sync --frozen
uv run --frozen pytest tests/test_api.py -q
TIMESTRAL_RUN_REAL_TESTS=1 uv run --frozen pytest tests/test_inference.py -m cpu -q
```

PyTorch's [2.14 release notes](https://pytorch.org/blog/pytorch-2-14-release-blog/)
document Python 3.15 wheels on its own indexes and the eager-only limitation.
This service does not use `torch.compile`.
