# syntax=docker/dockerfile:1
#
# ComfyUI, built from upstream source (comfyanonymous/ComfyUI publishes no
# official image) on a CUDA 13.0 runtime base. TORCH_CUDA_ARCH_LIST includes
# 12.0 (Blackwell / RTX 50-series) through older archs for portability.
#
# Build:
#   docker build -t m11s/comfyui:0.3.0 .

FROM nvidia/cuda:13.0.3-cudnn-runtime-ubuntu22.04

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
RUN python3.11 -m pip install --no-cache-dir \
        --extra-index-url https://download.pytorch.org/whl/cu130 \
        torch==2.11.0 \
        torchvision==0.26.0 \
        torchaudio==2.11.0 && \
    printf 'torch==2.11.0\ntorchvision==0.26.0\ntorchaudio==2.11.0\n' > /etc/pip-constraints.txt
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

# --disable-cuda-malloc: torch's cudaMallocAsync allocator hangs the server
# unresponsive on this CUDA 13.0 + torch 2.11 build (accepts TCP, never
# answers HTTP). Forcing the native allocator via ComfyUI's own flag avoids
# it; overriding PYTORCH_CUDA_ALLOC_CONF as an env var instead crashes at
# import with a PyTorch internal assert (allocator backend mismatch between
# load time and runtime).
ENTRYPOINT ["python3.11", "main.py", "--listen", "0.0.0.0", "--port", "8188", "--disable-cuda-malloc"]
