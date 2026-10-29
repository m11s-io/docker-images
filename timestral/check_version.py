"""Validate installed upstream Timestral and pinned Torch versions during builds."""

import importlib.metadata
import sys
from pathlib import Path
import tomllib


def check_torch(variant: str) -> None:
    import torch

    if variant == "cpu":
        project = tomllib.loads(Path("pyproject.toml").read_text())
        requirements = project["project"]["dependencies"]
    elif variant in ("cuda", "rocm"):
        filename = "requirements-torch-rocm.txt" if variant == "rocm" else "requirements-cuda.txt"
        requirements = Path(filename).read_text().splitlines()
    else:
        raise ValueError(f"Unknown Torch variant: {variant}")
    expected = next(line.split("==", 1)[1] for line in requirements if line.startswith("torch=="))
    actual = importlib.metadata.version("torch")
    if actual != expected:
        raise RuntimeError(f"expected Torch {expected}, installed {actual}")
    if (torch.version.cuda is not None) != (variant == "cuda"):
        raise RuntimeError(f"Torch CUDA runtime does not match {variant} image")
    hip = getattr(torch.version, "hip", None)
    if bool(hip) != (variant == "rocm"):
        raise RuntimeError(f"Torch HIP runtime does not match {variant} image")
    print(f"Verified Torch {actual}, CUDA={torch.version.cuda}, HIP={hip}")


def main() -> int:
    expected = sys.argv[1]
    try:
        actual = importlib.metadata.version("timestral")
    except importlib.metadata.PackageNotFoundError:
        print("Timestral distribution is not installed", file=sys.stderr)
        return 1

    if actual != expected:
        print(
            f"Timestral package version {actual} does not match image version {expected}",
            file=sys.stderr,
        )
        return 1

    if len(sys.argv) > 2:
        check_torch(sys.argv[2])
    print(f"Verified Timestral package version {actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
