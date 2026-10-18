ARG VLLM_BASE_IMAGE=vllm/vllm-openai:v0.32.0-x86_64@sha256:6ee133356d49ed24cee03dd0cda3d3980279a11c107ce3e752c89e76540f41c9

FROM ${VLLM_BASE_IMAGE}

RUN python3 -m pip install --no-cache-dir orjson \
    && python3 -c "import orjson; print(orjson.__version__)"
