# syntax=docker/dockerfile:1
#
# ComfyUI, built from upstream source (comfyanonymous/ComfyUI publishes no
# official image) on a CUDA 13.3 runtime base. TORCH_CUDA_ARCH_LIST includes
# 12.0 (Blackwell / RTX 50-series) through older archs for portability.
#
# Build:
#   docker build -t m11s/comfyui:0.5.0 .

FROM nvidia/cuda:13.3.1-cudnn-runtime-ubuntu22.04@sha256:d613b00c36d11fc3acc8923ef5d7672d30f469c1a9049906fbd993dd2ba8155f

ARG COMFYUI_REF=v0.35.1
ARG COMFYUI_GGUF_REF=main

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TORCH_CUDA_ARCH_LIST="7.0;7.5;8.0;8.6;8.9;9.0;12.0+PTX"

# python3.11 isn't in jammy's default repos; deadsnakes backports it.
RUN apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common ca-certificates && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        python3.11 \
        python3.11-venv \
        git \
        libx11-6 \
        libxcb1 \
        libxext6 && \
    rm -rf /var/lib/apt/lists/* && \
    python3.11 -m ensurepip --upgrade

WORKDIR /app

# requirements.txt below pins torch unversioned, which would otherwise
# resolve to a CPU-only wheel from the default PyPI index. Install CUDA
# wheels explicitly first, then constrain pip so requirements.txt can't
# silently replace them.
#
# torchaudio stays at 2.11.0: it's in maintenance mode and hasn't cut a
# release matching the 2.12+ torch line.
RUN python3.11 -m pip install --no-cache-dir \
        --extra-index-url https://download.pytorch.org/whl/cu132 \
        torch==2.14.0 \
        torchvision==0.29.0 \
        torchaudio==2.11.0 && \
    printf 'torch==2.14.0\ntorchvision==0.29.0\ntorchaudio==2.11.0\n' > /etc/pip-constraints.txt
ENV PIP_CONSTRAINT=/etc/pip-constraints.txt

RUN git clone --branch ${COMFYUI_REF} --depth 1 \
        https://github.com/comfyanonymous/ComfyUI.git .

RUN python3.11 -m pip install --no-cache-dir -r requirements.txt

# ComfyUI-GGUF adds GGUF-quantized model loaders (UnetLoaderGGUF,
# DualCLIPLoaderGGUF, etc.) alongside the built-in safetensors loaders -
# additive, doesn't change how existing fp8/safetensors workflows load.
# Lets 16GB-VRAM workflows fit with headroom (e.g. Flux Q5_K_M ~8-9GB vs
# ~16GB combined at fp8) instead of swap-thrashing UNET/CLIP every run.
RUN git clone --branch ${COMFYUI_GGUF_REF} --depth 1 \
        https://github.com/city96/ComfyUI-GGUF.git custom_nodes/ComfyUI-GGUF && \
    python3.11 -m pip install --no-cache-dir -r custom_nodes/ComfyUI-GGUF/requirements.txt

RUN groupadd --system --gid 10001 comfyui && \
    useradd --system --uid 10001 --gid comfyui --no-create-home comfyui && \
    mkdir -p /app/models /app/output /app/input /app/user && \
    chown -R comfyui:comfyui /app

USER comfyui

EXPOSE 8188

ENTRYPOINT ["python3.11", "main.py", "--listen", "0.0.0.0", "--port", "8188"]
