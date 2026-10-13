ARG VLLM_BASE_IMAGE=vllm/vllm-openai:v0.31.0-x86_64@sha256:a4a4c0437bf7240089da5f08aa370c4aee17ae5290f7a3b468825ee26c4c3a6b

FROM ${VLLM_BASE_IMAGE}

RUN python3 -m pip install --no-cache-dir orjson \
    && python3 -c "import orjson; print(orjson.__version__)"
