ARG VLLM_BASE_IMAGE=vllm/vllm-openai:v0.28.0-x86_64

FROM ${VLLM_BASE_IMAGE}

# orjson: faster JSON serialization for /v1/embeddings and /v1/chat/completions
# (pure-Python-level dependency, no ABI concerns).
#
# lmcache: KV-cache offload/sharing. Unlike orjson, it ships compiled CUDA
# extensions, so it must resolve against the same torch build vLLM already
# has installed - a bare `pip install lmcache` can't verify that at install
# time. The --extra-index-url below points pip at the cu130 torch wheel
# index to match this base image's CUDA 13.0.3 runtime, mirroring what
# LMCache's own Dockerfile does for its "release" build target:
# https://github.com/LMCache/LMCache/blob/dev/docker/Dockerfile
# lmcache's own PyPI dependency on torch is unconstrained, so pip keeps the
# torch vLLM already installed rather than replacing it.
#
# lmcache's dependency chain does pull in an older nvidia-nccl-cu13
# (2.29.7), silently downgrading it below the 2.30.7 vLLM's own Dockerfile
# pins ("DeepEPv2 requires NCCL >= 2.30.4") - confirmed locally, pip gives
# no warning since it only validates Python-level deps, not CUDA-library
# compatibility. Reinstalled explicitly afterwards to restore vLLM's pin.
RUN python3 -m pip install --no-cache-dir \
        orjson \
        lmcache==0.5.4 \
        --extra-index-url https://download.pytorch.org/whl/cu130 \
    && python3 -m pip install --no-cache-dir nvidia-nccl-cu13==2.30.7 \
    && python3 -c "import orjson; print(orjson.__version__)" \
    && python3 -c "import lmcache; print(lmcache.__version__)"
