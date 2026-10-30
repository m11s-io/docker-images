"""Seal and verify the complete allowlisted publication bundle."""
import argparse
import hashlib
import json
from pathlib import Path
import re

FILES = frozenset({"model/1/model.xml", "model/1/model.bin", "config.json", "quantiles.json",
                   "LICENSE", "README.md", "validation.json", "validation-fixtures.json",
                   "ovms-validation.json"})
CASES = {"random", "sinusoidal", "constant", "scattered-missing", "leading-missing"}


def inventory(root: Path) -> set:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("bundle must be a real directory")
    names = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("symlinks cannot be published")
        if path.is_file(): names.add(path.relative_to(root).as_posix())
        elif not path.is_dir(): raise ValueError("special files cannot be published")
    return names


def check_reports(root: Path) -> None:
    for name in ["validation.json", "ovms-validation.json"]:
        report = json.loads((root / name).read_text())
        if report.get("passed") is not True or set(report.get("cases", {})) != CASES:
            raise ValueError("both complete validation reports must pass before publication")
        for case in report["cases"].values():
            if case.get("rtol") != 1e-4 or case.get("atol") != 1e-4:
                raise ValueError("unexpected validation tolerance")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def seal(root: Path) -> None:
    if inventory(root) != FILES:
        raise ValueError("bundle contains missing or unexpected files")
    check_reports(root)
    manifest = "".join(f"{digest(root / name)}  {name}\n" for name in sorted(FILES))
    (root / "SHA256SUMS").write_text(manifest)
    verify(root)


def verify(root: Path) -> None:
    if inventory(root) != FILES | {"SHA256SUMS"}:
        raise ValueError("bundle contains missing or unexpected files")
    entries = {}
    for line in (root / "SHA256SUMS").read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match or match[2] not in FILES or match[2] in entries:
            raise ValueError("invalid checksum manifest entry")
        entries[match[2]] = match[1]
    if set(entries) != FILES:
        raise ValueError("incomplete manifest")
    for name, expected in entries.items():
        if digest(root / name) != expected:
            raise ValueError(f"checksum mismatch: {name}")
    check_reports(root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--verify", type=Path)
    options = parser.parse_args()
    if bool(options.bundle) == bool(options.verify): parser.error("choose --bundle or --verify")
    if options.verify: verify(options.verify)
    else: seal(options.bundle)
