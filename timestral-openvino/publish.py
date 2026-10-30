"""Publish a validated bundle using job-scoped HF OIDC, then verify its commit."""
import argparse
import json
import os
from pathlib import Path

from package import FILES, digest, verify

DESTINATION = "m11s-org/Timestral-5M-OpenVINO-experimental"


def validate_environment() -> None:
    expected = {"GITHUB_ACTIONS": "true", "GITHUB_REF": "refs/heads/main",
                "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REPOSITORY": "m11s-io/docker-images",
                "HF_OIDC_RESOURCE": DESTINATION}
    for key, value in expected.items():
        if os.environ.get(key) != value:
            raise ValueError(f"publication requires the configured main dispatch: {key}")


def publish(bundle: Path) -> str:
    validate_environment()
    verify(bundle)
    report = json.loads((bundle / "validation.json").read_text())
    if report.get("ci_commit") != os.environ.get("GITHUB_SHA") or report.get("ci_run") != os.environ.get("GITHUB_RUN_ID"):
        raise ValueError("bundle provenance does not match this CI run")
    from huggingface_hub import HfApi, hf_hub_download
    # In the pinned SDK, HF_OIDC_RESOURCE triggers exchange before other token sources.
    api = HfApi()
    info = api.model_info(DESTINATION)
    if not info.private:
        raise ValueError("experimental model repository must remain private")
    commit = api.upload_folder(repo_id=DESTINATION, folder_path=str(bundle),
                               commit_message=f"Validated OpenVINO export from {os.environ['GITHUB_SHA'][:12]}",
                               allow_patterns=sorted(FILES | {"SHA256SUMS"}))
    revision = commit.oid
    names = set(api.list_repo_files(DESTINATION, revision=revision))
    if names - {".gitattributes"} != FILES | {"SHA256SUMS"}:
        raise ValueError("remote commit contains missing or unexpected files")
    for name in FILES | {"SHA256SUMS"}:
        remote = Path(hf_hub_download(DESTINATION, filename=name, revision=revision))
        if digest(remote) != digest(bundle / name):
            raise ValueError(f"remote checksum mismatch: {name}")
    url = f"https://huggingface.co/{DESTINATION}/tree/{revision}"
    print(f"Verified HF commit: {revision}\n{url}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as stream:
            stream.write(f"Published and verified [{DESTINATION}]({url})\n\nImmutable revision: `{revision}`\n")
    return revision


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    publish(parser.parse_args().bundle)
