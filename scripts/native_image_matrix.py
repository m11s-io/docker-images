#!/usr/bin/env python3
"""Select changed multi-platform images and resolve their existing public tags."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


def build_matrix(images, event, selected, changed, sha):
    include = []
    for image in images:
        context = image["context"]
        enabled = (selected in ("all", context) if event == "workflow_dispatch"
                   else changed.get(context) == "true")
        if not enabled:
            continue
        args = [
            sys.executable, str(Path(__file__).with_name("image_tags.py")),
            "--repository", image["repository"],
            "--latest", image["latest"], "--sha", sha,
            "--strip-prefix", image.get("strip_prefix", ""),
            "--strip-suffix=" + image.get("strip_suffix", ""),
            "--suffix=" + image.get("tag_suffix", ""),
        ]
        if image.get("version_source"):
            args.extend(["--" + image["version_source"], image["version_ref"],
                         "--dockerfile", str(Path(context) / "Dockerfile")])
        else:
            args.extend(["--version", image["version"]])
        tags = subprocess.check_output(args, text=True).splitlines()
        prefix = image["repository"] + ":"
        include.append({**image, "meta-tags": "\n".join(
            "type=raw,value=" + tag[len(prefix):] for tag in tags
        )})
    return {"include": include}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", required=True)
    parser.add_argument("--event", choices=["push", "workflow_dispatch"], required=True)
    parser.add_argument("--selected", default="all")
    parser.add_argument("--changed", required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    matrix = build_matrix(json.loads(args.images), args.event, args.selected,
                          json.loads(args.changed), args.sha)
    print("matrix=" + json.dumps(matrix, separators=(",", ":")))
    print("has-images=" + str(bool(matrix["include"])).lower())


if __name__ == "__main__":
    main()
