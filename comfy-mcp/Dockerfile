# syntax=docker/dockerfile:1.28.0@sha256:bb22d9815c728170f72750f4e5b0d672e06176142e1d602c7e66c050100b7e5b
#
# An MCP server for a separately deployed ComfyUI instance. ComfyUI is
# deliberately not bundled: comfy-mcp is a thin wrapper over comfy-cli, and
# the GPU runtime is provided by m11s/comfyui.

FROM python:3.15.2-slim-bookworm@sha256:4d54a654d391909a6c0de8035e15c01ad196d31e4a1552bb328bf1181e4d393a AS builder

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

FROM python:3.15.2-slim-bookworm@sha256:4d54a654d391909a6c0de8035e15c01ad196d31e4a1552bb328bf1181e4d393a

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
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/opt/venv/bin:$PATH \
    COMFY_BIN=/opt/venv/bin/comfy \
    COMFY_PROJECT=/workspace

WORKDIR /workspace
USER comfy

# Default port for the optional Streamable HTTP transport.
EXPOSE 8080

# Exercise the actual installed CLI/SDK and both transports on each platform.
# The bind-mounted test and temporary configuration do not enter the image.
RUN --mount=type=bind,source=tests/smoke.py,target=/tmp/comfy-mcp-smoke.py \
    python -m pip check && python /tmp/comfy-mcp-smoke.py

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD ["python", "/opt/comfy-mcp-image/healthcheck.py"]

# No argument keeps the established stdio contract. Kubernetes supplies the
# explicit Streamable HTTP command below, which is the only mode that binds a
# network listener.
ENTRYPOINT ["python", "/opt/comfy-mcp-image/entrypoint.py"]
