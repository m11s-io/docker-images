"""Guarded conversion-only rewrites from the audited export experiment."""
from pathlib import Path
import shutil

REWRITES = {
    "src/timestral/masks.py": [
        ("obs_per_patch.cummax(dim=-1).values", "(obs_per_patch.to(torch.int64).cumsum(dim=-1) > 0)"),
    ],
}


def patch_source(source: Path, destination: Path) -> None:
    """Check all expected rewrites before creating an isolated patched copy."""
    replacements = {}
    for name, rewrites in REWRITES.items():
        text = (source / name).read_text()
        for original, replacement in rewrites:
            if text.count(original) != 1:
                raise ValueError(f"source drift: expected one occurrence in {name}")
            text = text.replace(original, replacement)
        replacements[name] = text
    shutil.copytree(source, destination)
    for name, text in replacements.items():
        (destination / name).write_text(text)
