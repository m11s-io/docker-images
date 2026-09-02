ARG VLLM_BASE_IMAGE=vllm/vllm-openai:v0.28.0-x86_64

FROM ${VLLM_BASE_IMAGE}

RUN python3 -m pip install --no-cache-dir orjson \
    && python3 -c "import orjson; print(orjson.__version__)"
