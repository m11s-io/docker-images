"""Validate dependencies and CPU startup before an image can be published."""
from __future__ import annotations

import argparse
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen


def check_cuda_backend() -> None:
    from comfy_kitchen.backends import cuda

    # Importing Kitchen alone can silently disable a broken native extension.
    # These flags describe library loading, not whether a GPU is attached.
    if not cuda._EXT_AVAILABLE:
        raise RuntimeError(f"Comfy Kitchen CUDA extension unavailable: {cuda._EXT_ERROR}")


def check_cuda_variants(torch_version: str, torchvision_version: str) -> None:
    torch_cuda = re.search(r"\+cu(\d+)$", torch_version)
    vision_cuda = re.search(r"\+cu(\d+)$", torchvision_version)
    if not torch_cuda or not vision_cuda or torch_cuda[1] != vision_cuda[1]:
        raise RuntimeError("Torch and TorchVision must use the same CUDA variant")


def check_dependencies() -> None:
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
    constraints = Path(os.environ["PIP_CONSTRAINT"])
    for requirement in constraints.read_text().splitlines():
        name, expected = requirement.split("==", 1)
        installed = version(name)
        if installed != expected:
            raise RuntimeError(f"{name}: expected {expected}, installed {installed}")

    import av  # noqa: F401
    import comfy.audio
    import torch
    import torchvision

    if torch.version.cuda is None:
        raise RuntimeError("the image requires a CUDA-enabled PyTorch build")
    check_cuda_variants(torch.__version__, torchvision.__version__)
    check_cuda_backend()
    if comfy.audio.resample(torch.zeros(1, 480), 48000, 24000).shape != (1, 240):
        raise RuntimeError("audio resampling returned an unexpected shape")
    print(f"torch={torch.__version__}, torchvision={torchvision.__version__}, CUDA={torch.version.cuda}")


def check_startup(gguf: bool, timeout_seconds: float = 120) -> None:
    # Use a free loopback port so this can also run beside a local ComfyUI server.
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryFile(mode="w+t") as logs:
        process = subprocess.Popen(
            [sys.executable, "main.py", "--cpu", "--listen", "127.0.0.1", "--port", str(port)],
            stdout=logs, stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"ComfyUI exited before readiness (code {process.returncode})")
                try:
                    with urlopen(base + "/system_stats", timeout=2) as response:
                        stats = json.load(response)
                    if "system" not in stats:
                        raise RuntimeError("ComfyUI returned invalid system stats")
                    break
                except (URLError, TimeoutError):
                    time.sleep(min(0.5, max(0, deadline - time.monotonic())))
            else:
                raise RuntimeError("ComfyUI startup timed out")
            if gguf:
                with urlopen(base + "/object_info", timeout=10) as response:
                    nodes = json.load(response)
                if "UnetLoaderGGUF" not in nodes:
                    raise RuntimeError("ComfyUI-GGUF did not register UnetLoaderGGUF")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            logs.seek(0)
            print(logs.read())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gguf", action="store_true")
    args = parser.parse_args()
    check_dependencies()
    check_startup(args.gguf)
