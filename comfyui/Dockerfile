# syntax=docker/dockerfile:1
#
# ComfyUI, built from upstream source (comfyanonymous/ComfyUI publishes no
# official image) on a CUDA 12.8 runtime base. TORCH_CUDA_ARCH_LIST includes
# 12.0 (Blackwell / RTX 50-series) through older archs for portability.
#
# Build:
#   docker build -t m11s/comfyui:0.1.0 .

FROM nvidia/cuda:12.8.0-cudnn-runtime-ubuntu22.04

ARG COMFYUI_REF=v0.28.2

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
        git && \
    rm -rf /var/lib/apt/lists/* && \
    python3.11 -m ensurepip --upgrade

WORKDIR /app

# requirements.txt below pins torch unversioned, which would otherwise
# resolve to a CPU-only wheel from the default PyPI index. Install CUDA
# wheels explicitly first, then constrain pip so requirements.txt can't
# silently replace them.
RUN python3.11 -m pip install --no-cache-dir \
        --extra-index-url https://download.pytorch.org/whl/cu128 \
        torch==2.9.1 \
        torchvision==0.24.1 \
        torchaudio==2.9.1 && \
    printf 'torch==2.9.1\ntorchvision==0.24.1\ntorchaudio==2.9.1\n' > /etc/pip-constraints.txt
ENV PIP_CONSTRAINT=/etc/pip-constraints.txt

RUN git clone --branch ${COMFYUI_REF} --depth 1 \
        https://github.com/comfyanonymous/ComfyUI.git .

RUN python3.11 -m pip install --no-cache-dir -r requirements.txt

RUN groupadd --system --gid 10001 comfyui && \
    useradd --system --uid 10001 --gid comfyui --no-create-home comfyui && \
    mkdir -p /app/models /app/output /app/input /app/user && \
    chown -R comfyui:comfyui /app

USER comfyui

EXPOSE 8188

ENTRYPOINT ["python3.11", "main.py", "--listen", "0.0.0.0", "--port", "8188"]
