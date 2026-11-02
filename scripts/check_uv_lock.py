"""Check lock consistency using the resolver cutoff recorded in that lock.

Routine Renovate runs record a cooldown; security runs disable it. CI verifies
both without imposing the routine cooldown on a newly published security fix.
"""
import os
from pathlib import Path
import subprocess
import sys
import tomllib


def check(project: str) -> None:
    lock = Path(project) / "uv.lock"
    with lock.open("rb") as stream:
        options = tomllib.load(stream).get("options", {})
    cutoff = options.get("exclude-newer-span", options.get("exclude-newer", "false"))
    subprocess.run(
        ["uv", "lock", "--project", project, "--check"],
        env={**os.environ, "UV_EXCLUDE_NEWER": str(cutoff)},
        check=True,
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: check_uv_lock.py PROJECT")
    check(sys.argv[1])
