# syntax=docker/dockerfile:1.28.0@sha256:bb22d9815c728170f72750f4e5b0d672e06176142e1d602c7e66c050100b7e5b

ARG VLLM_BASE_IMAGE=vllm/vllm-openai:v0.33.0-x86_64@sha256:91ee972ab751fb7180bc71c175865e36b091686600dca783d52b2511399810b3

FROM ${VLLM_BASE_IMAGE}

RUN python3 -m pip install --no-cache-dir orjson==3.13.0 \
    && python3 -c "import orjson; print(orjson.__version__)"
