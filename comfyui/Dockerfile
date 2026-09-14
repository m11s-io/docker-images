# syntax=docker/dockerfile:1@sha256:ecfaec9ed6d810b56388c508f4121597bfbba70d41a6dfeee4d8cad5f295fc32
#
# ComfyUI, built from upstream source (comfyanonymous/ComfyUI publishes no
# official image) on a CUDA 13.3 runtime base. TORCH_CUDA_ARCH_LIST includes
# 12.0 (Blackwell / RTX 50-series) through older archs for portability.
#
# Build:
#   docker build -t m11s/comfyui:0.5.2 .

FROM nvidia/cuda:13.3.1-cudnn-runtime-ubuntu22.04@sha256:d613b00c36d11fc3acc8923ef5d7672d30f469c1a9049906fbd993dd2ba8155f

ARG COMFYUI_REF=v0.35.1

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TORCH_CUDA_ARCH_LIST="7.0;7.5;8.0;8.6;8.9;9.0;12.0+PTX"

# Python 3.14 isn't in jammy's default repos; deadsnakes backports it.
RUN apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common ca-certificates && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        python3.14 \
        python3.14-venv \
        git \
        libx11-6 \
        libxcb1 \
        libxext6 && \
    rm -rf /var/lib/apt/lists/* && \
    python3.14 -m ensurepip --upgrade

WORKDIR /app

# requirements.txt below pins torch unversioned, which would otherwise
# resolve to a CPU-only wheel from the default PyPI index. Install CUDA
# wheels explicitly first, then constrain pip so requirements.txt can't
# silently replace them.
#
# TorchAudio 2.11 publishes cu130, but not cu132. Keep all three PyTorch
# packages on cu130 so their native extensions use one CUDA ABI. The CUDA
# 13.3 base remains supported by the host driver independently.
RUN python3.14 -m pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cu130 \
        torch==2.14.0+cu130 \
        torchvision==0.29.0+cu130 \
        torchaudio==2.11.0+cu130 && \
    printf 'torch==2.14.0+cu130\ntorchvision==0.29.0+cu130\ntorchaudio==2.11.0+cu130\n' > /etc/pip-constraints.txt
ENV PIP_CONSTRAINT=/etc/pip-constraints.txt

RUN git clone --branch ${COMFYUI_REF} --depth 1 \
        https://github.com/comfyanonymous/ComfyUI.git .

RUN python3.14 -m pip install --no-cache-dir -r requirements.txt

RUN groupadd --system --gid 10001 comfyui && \
    useradd --system --uid 10001 --gid comfyui --no-create-home comfyui && \
    mkdir -p /app/models /app/output /app/input /app/user && \
    chown -R comfyui:comfyui /app

USER comfyui

EXPOSE 8188

ENTRYPOINT ["python3.14", "main.py", "--listen", "0.0.0.0", "--port", "8188"]
