"""Exercise real Renovate lookup, grouping and merge policy against PyTorch indexes.

Run inside the pinned Renovate CI container. Fixtures use published older pins
so this check proves updates are discovered even when production pins are current.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
CUDA_FILES = ("comfyui/requirements-cuda.txt", "timestral/requirements-cuda.txt")
GROUPS = {
    "comfyui/requirements-cuda.txt": "ComfyUI Dockerfile dependencies",
    "timestral/requirements-cuda.txt": "Timestral PyTorch",
    "timestral/pyproject.toml": "Timestral PyTorch",
}


def check_lookup(same_release: bool) -> None:
    with tempfile.TemporaryDirectory(prefix="cuda-renovate-") as directory:
        fixture = Path(directory)
        for name in ("renovate.json", *CUDA_FILES, "timestral/pyproject.toml"):
            target = fixture / name
            target.parent.mkdir(parents=True, exist_ok=True)
            source = (ROOT / name).read_text()
            if name in CUDA_FILES:
                # Keep the public release but move back one published CUDA
                # variant: a channel-only update must also produce a PR.
                source = re.sub(r"\+cu\d+", "+cu130", source)
            if not same_release:
                source = source.replace("2.14.1+", "2.14.0+")
                source = source.replace("0.29.1+", "0.29.0+")
            target.write_text(source)
        subprocess.run(["git", "init", "-q"], cwd=fixture, check=True)
        subprocess.run(["git", "add", "."], cwd=fixture, check=True)
        subprocess.run(
            ["git", "-c", "user.name=CI", "-c", "user.email=ci@example.invalid",
             "commit", "-qm", "Published older PyTorch pins"],
            cwd=fixture, check=True,
        )
        log = fixture / "lookup.jsonl"
        result = subprocess.run(
            ["renovate", "--platform=local", "--dry-run=lookup"],
            cwd=fixture, text=True, capture_output=True,
            env={**os.environ, "LOG_LEVEL": "warn", "LOG_FILE": str(log),
                 "LOG_FILE_LEVEL": "trace", "LOG_FILE_FORMAT": "json",
                 "RENOVATE_ENABLED_MANAGERS": '["pip_requirements","pep621"]',
                 "RENOVATE_INCLUDE_PATHS": '["comfyui/**","timestral/**"]'},
            timeout=240,
        )
        if result.returncode:
            raise RuntimeError(f"Renovate lookup failed: {result.stdout}\n{result.stderr}")
        records = [json.loads(line) for line in log.read_text().splitlines()]
        packages = next(r["config"] for r in records if r.get("msg") == "packageFiles with updates")
        seen = set()
        proposed = set()
        for files in packages.values():
            for package in files:
                filename = package["packageFile"]
                for dep in package["deps"]:
                    if dep["depName"] not in ("torch", "torchvision"):
                        continue
                    assert not dep.get("skipReason"), dep
                    assert not dep.get("warnings"), dep
                    updates = dep.get("updates", [])
                    # The CPU package need not change for a CUDA variant update.
                    if filename in CUDA_FILES or not same_release:
                        assert updates, f"No update found for {filename}: {dep}"
                    if updates:
                        proposed.add((filename, dep["depName"]))
                    for update in updates:
                        version = update["newVersion"]
                        if filename in CUDA_FILES:
                            assert re.fullmatch(r"\d+\.\d+\.\d+\+cu\d+", version), version
                            assert int(version.rsplit("cu", 1)[1]) > 130, version
                            assert dep["registryUrls"] == ["https://download.pytorch.org/whl"], dep
                        else:
                            assert version.endswith("+cpu"), version
                    seen.add((filename, dep["depName"]))
        assert seen == {(CUDA_FILES[0], "torch"), (CUDA_FILES[0], "torchvision"),
                        (CUDA_FILES[1], "torch"), ("timestral/pyproject.toml", "torch")}, seen

        # This trace record comes from Renovate's branch generator, after
        # inherited presets and update-type rules have actually been applied.
        branches = [r["config"] for r in records if r.get("msg") == "generateBranchConfig"]
        checked = set()
        branch_names = {}
        for upgrades in branches:
            for upgrade in upgrades:
                filename = upgrade["packageFile"]
                if filename not in GROUPS or upgrade["depName"] not in ("torch", "torchvision"):
                    continue
                assert upgrade["groupName"] == GROUPS[filename], upgrade
                assert upgrade["automerge"] is True, upgrade
                assert upgrade["platformAutomerge"] is True, upgrade
                assert upgrade["ignoreTests"] is False, upgrade
                assert not upgrade.get("pendingChecks"), upgrade
                checked.add((filename, upgrade["depName"]))
                branch_names.setdefault(GROUPS[filename], set()).add(upgrade["branchName"])
                print(f"{filename}: {upgrade['currentValue']} -> {upgrade['newValue']}; "
                      f"group={upgrade['groupName']}; auto merge after checks")
        expected = proposed
        assert checked == expected, (checked, expected)
        assert all(len(names) == 1 for names in branch_names.values()), branch_names
        assert len(set.union(*branch_names.values())) == 2, branch_names


if __name__ == "__main__":
    if not shutil.which("renovate"):
        raise SystemExit("Run this check inside the Renovate CI container")
    check_lookup(same_release=False)
    check_lookup(same_release=True)
