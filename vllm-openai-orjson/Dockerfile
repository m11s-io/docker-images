ARG VLLM_BASE_IMAGE=vllm/vllm-openai:v0.29.0-x86_64@sha256:082ca6f035279109041ffd3fe0695cb568b29bc580b35c4f297a66a08b216c1b

FROM ${VLLM_BASE_IMAGE}

RUN python3 -m pip install --no-cache-dir orjson \
    && python3 -c "import orjson; print(orjson.__version__)"
