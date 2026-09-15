# syntax=docker/dockerfile:1@sha256:ecfaec9ed6d810b56388c508f4121597bfbba70d41a6dfeee4d8cad5f295fc32
#
# An MCP server for a separately deployed ComfyUI instance. ComfyUI is
# deliberately not bundled: comfy-mcp is a thin wrapper over comfy-cli, and
# the GPU runtime is provided by m11s/comfyui.

FROM python:3.14.7-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f AS builder

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

FROM python:3.14.7-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f

LABEL org.opencontainers.image.title="m11s/comfy-mcp" \
      org.opencontainers.image.description="Thin comfy-mcp and comfy-cli image with optional native Streamable HTTP transport"

COPY --from=builder /opt/venv /opt/venv
COPY entrypoint.py healthcheck.py /opt/comfy-mcp-image/

RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd --system --gid 10001 comfy && \
    useradd --system --uid 10001 --gid comfy --create-home --home-dir /workspace comfy && \
    chown comfy:comfy /workspace

ENV HOME=/workspace \
    PATH=/opt/venv/bin:$PATH \
    COMFY_BIN=/opt/venv/bin/comfy \
    COMFY_PROJECT=/workspace

WORKDIR /workspace
USER comfy

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD ["python", "/opt/comfy-mcp-image/healthcheck.py"]

# No argument keeps the established stdio contract. Kubernetes supplies the
# explicit Streamable HTTP command below, which is the only mode that binds a
# network listener.
ENTRYPOINT ["python", "/opt/comfy-mcp-image/entrypoint.py"]
