# syntax=docker/dockerfile:1.28.0@sha256:bb22d9815c728170f72750f4e5b0d672e06176142e1d602c7e66c050100b7e5b
#
# ComfyUI, built from upstream source (comfyanonymous/ComfyUI publishes no
# official image). PyTorch wheels supply the CUDA userspace libraries;
# the NVIDIA container runtime supplies the host driver.
#
# Build:
#   docker build -t m11s/comfyui:local comfyui

FROM python:3.14.8-slim-bookworm@sha256:44e000a07b48bef1517a2b14adc93c17af728ca98858b5e24c6e1b18de1b2ef2 AS runtime

# renovate: datasource=github-tags depName=Comfy-Org/ComfyUI
ARG COMFYUI_REF=v0.43.0

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV CC=/usr/bin/gcc
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

# Keep a C compiler for runtime-generated launchers; CUDA helpers use wheels.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        gcc \
        libc6-dev \
        git \
        libx11-6 \
        libxcb1 \
        libxext6 && \
    rm -rf /var/lib/apt/lists/* && \
    python -m venv /opt/venv

# Keep application dependencies separate from the base image's Python packages.
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

# Install CUDA wheels explicitly and constrain upstream requirements to keep
# the selected PyTorch versions. Audio dependencies follow upstream requirements.
# PyTorch wheels supply CUDA libraries independently of the runtime base.
COPY requirements-cuda.txt /opt/requirements-cuda.txt
RUN python -m pip install --no-cache-dir -r /opt/requirements-cuda.txt && \
    sed '/^--/d; /^#/d; /^[[:space:]]*$/d' /opt/requirements-cuda.txt > /etc/pip-constraints.txt
ENV PIP_CONSTRAINT=/etc/pip-constraints.txt

RUN git clone --branch ${COMFYUI_REF} --depth 1 \
        https://github.com/comfyanonymous/ComfyUI.git .

RUN python -m pip install --no-cache-dir \
        --only-binary=comfy-kitchen,comfy-aimdo -r requirements.txt

RUN groupadd --system --gid 10001 comfyui && \
    useradd --system --uid 10001 --gid comfyui \
        --create-home --home-dir /home/comfyui comfyui && \
    mkdir -p /app/models /app/output /app/input /app/user && \
    chown -R comfyui:comfyui /app

USER comfyui


EXPOSE 8188

ENTRYPOINT ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188"]

FROM runtime AS validation
COPY verify_image.py /app/verify_image.py
RUN python /app/verify_image.py && touch /tmp/comfyui-validated

# Depend on validation without including its generated startup state.
FROM runtime AS final
COPY --from=validation /tmp/comfyui-validated /usr/local/share/comfyui/image-validated
