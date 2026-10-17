# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
#
# An MCP server for a separately deployed ComfyUI instance. ComfyUI is
# deliberately not bundled: comfy-mcp is a thin wrapper over comfy-cli, and
# the GPU runtime is provided by m11s/comfyui.

FROM python:3.15.0-slim-bookworm@sha256:2a41267d9de9d358f77a1de356e0f16ecba8d39827855be0ce9ef4792edce402 AS builder

ARG COMFY_CLI_REF=v1.22.0
# renovate: datasource=github-tags depName=Comfy-Org/comfy-mcp
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

FROM python:3.15.0-slim-bookworm@sha256:2a41267d9de9d358f77a1de356e0f16ecba8d39827855be0ce9ef4792edce402

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

# Exercise the actual installed CLI/SDK and both transports on each platform.
# The bind-mounted test and temporary configuration do not enter the image.
RUN --mount=type=bind,source=tests/smoke.py,target=/tmp/comfy-mcp-smoke.py \
    python -m pip check && python /tmp/comfy-mcp-smoke.py

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD ["python", "/opt/comfy-mcp-image/healthcheck.py"]

# No argument keeps the established stdio contract. Kubernetes supplies the
# explicit Streamable HTTP command below, which is the only mode that binds a
# network listener.
ENTRYPOINT ["python", "/opt/comfy-mcp-image/entrypoint.py"]
