# syntax=docker/dockerfile:1@sha256:ecfaec9ed6d810b56388c508f4121597bfbba70d41a6dfeee4d8cad5f295fc32
#
# A stdio MCP server for a separately deployed ComfyUI instance.  ComfyUI is
# deliberately not bundled: comfy-mcp is a thin wrapper over comfy-cli, and
# the GPU runtime is provided by m11s/comfyui.

FROM python:3.13.13-slim-bookworm@sha256:355bfa66770995d7e9a0da4b3473b44d0cb451f6b56f5615ad9c39e3c4eca03f AS builder

ARG COMFY_CLI_REF=v1.20.0
ARG COMFY_MCP_REF=v0.10.0

RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /src

RUN git clone --depth 1 --branch "${COMFY_CLI_REF}" https://github.com/Comfy-Org/comfy-cli.git comfy-cli && \
    git clone --depth 1 --branch "${COMFY_MCP_REF}" https://github.com/Comfy-Org/comfy-mcp.git comfy-mcp && \
    sed -i "s/version = \"0.0.0\"/version = \"${COMFY_CLI_REF#v}\"/" comfy-cli/pyproject.toml && \
    python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir ./comfy-cli ./comfy-mcp && \
    /opt/venv/bin/comfy --version && \
    /opt/venv/bin/comfy-mcp --version

FROM python:3.13.13-slim-bookworm@sha256:355bfa66770995d7e9a0da4b3473b44d0cb451f6b56f5615ad9c39e3c4eca03f

COPY --from=builder /opt/venv /opt/venv

RUN groupadd --system --gid 10001 comfy && \
    useradd --system --uid 10001 --gid comfy --create-home --home-dir /workspace comfy && \
    chown comfy:comfy /workspace

ENV HOME=/workspace \
    PATH=/opt/venv/bin:$PATH \
    COMFY_BIN=/opt/venv/bin/comfy \
    COMFY_PROJECT=/workspace

WORKDIR /workspace
USER comfy

ENTRYPOINT ["comfy-mcp"]
