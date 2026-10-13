# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
#
# ComfyUI, built from upstream source (comfyanonymous/ComfyUI publishes no
# official image) on a CUDA 13.4 runtime base. TORCH_CUDA_ARCH_LIST includes
# 12.0 (Blackwell / RTX 50-series) through older archs for portability.
#
# Build:
#   docker build -t m11s/comfyui:0.5.5 .

FROM nvidia/cuda:13.4.2-cudnn-runtime-ubuntu22.04@sha256:d5982da4024f00929ce8297a901f2c962b9fb06e3b9df2fdca35ecbdcd6754ee

ARG COMFYUI_REF=v0.39.0

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TORCH_CUDA_ARCH_LIST="7.0;7.5;8.0;8.6;8.9;9.0;12.0+PTX"
ENV CC=/usr/bin/gcc-12

# Python 3.14 isn't in jammy's default repos; deadsnakes backports it.
RUN apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common ca-certificates && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        python3.14 \
        python3.14-dev \
        python3.14-venv \
        gcc-12 \
        git \
        libx11-6 \
        libxcb1 \
        libxext6 && \
    rm -rf /var/lib/apt/lists/* && \
    python3.14 -m venv /opt/venv

# Keep application dependencies separate from Ubuntu's system Python packages.
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

# Install CUDA wheels explicitly and constrain upstream requirements to keep
# the selected PyTorch versions. ComfyUI v0.39.0 no longer uses TorchAudio.
# PyTorch wheels supply CUDA 13.0 libraries independently of the runtime base.
RUN python3.14 -m pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cu130 \
        torch==2.14.1+cu130 \
        torchvision==0.29.1+cu130 && \
    printf 'torch==2.14.1+cu130\ntorchvision==0.29.1+cu130\n' > /etc/pip-constraints.txt
ENV PIP_CONSTRAINT=/etc/pip-constraints.txt

RUN git clone --branch ${COMFYUI_REF} --depth 1 \
        https://github.com/comfyanonymous/ComfyUI.git .

RUN python3.14 -m pip install --no-cache-dir -r requirements.txt

RUN groupadd --system --gid 10001 comfyui && \
    useradd --system --uid 10001 --gid comfyui \
        --create-home --home-dir /home/comfyui comfyui && \
    mkdir -p /app/models /app/output /app/input /app/user && \
    chown -R comfyui:comfyui /app

USER comfyui

EXPOSE 8188

ENTRYPOINT ["python3.14", "main.py", "--listen", "0.0.0.0", "--port", "8188"]
