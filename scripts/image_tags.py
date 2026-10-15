"""Resolve Docker publish tags from a release, Dockerfile argument, or base pin."""

import argparse
import pathlib
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--latest", required=True)
    parser.add_argument("--sha", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--version")
    source.add_argument("--base-image")
    source.add_argument("--base-arg")
    source.add_argument("--version-arg")
    parser.add_argument("--dockerfile", type=pathlib.Path)
    parser.add_argument("--suffix", default="")
    parser.add_argument("--strip-prefix", default="")
    parser.add_argument("--strip-suffix", default="")
    args = parser.parse_args()

    version = args.version
    if version is None:
        if args.dockerfile is None:
            parser.error("a Dockerfile is required for a Dockerfile version source")
        try:
            content = args.dockerfile.read_text()
        except OSError as error:
            parser.error(str(error))
        if args.base_arg or args.version_arg:
            pattern = rf"^\s*ARG\s+{re.escape(args.base_arg or args.version_arg)}=(\S+)\s*(?:#.*)?$"
        else:
            pattern = rf"^\s*FROM\s+({re.escape(args.base_image)}(?=[:@\s])\S*)(?:\s+AS\s+\S+)?\s*$"
        references = re.findall(pattern, content, flags=re.MULTILINE | re.IGNORECASE)
        if len(references) != 1:
            parser.error("expected exactly one matching Dockerfile base reference or version argument")
        if args.version_arg:
            version = references[0]
        else:
            # A registry's port is not an image tag; inspect only the final path segment.
            reference = references[0].split("@", 1)[0]
            if ":" not in reference.rsplit("/", 1)[-1]:
                parser.error("base reference must have an explicit image tag")
            version = reference.rsplit(":", 1)[1]

    if not version.startswith(args.strip_prefix):
        parser.error("version does not start with the declared prefix")
    version = version[len(args.strip_prefix):]
    if args.strip_suffix:
        if not version.endswith(args.strip_suffix):
            parser.error("version does not end with the declared suffix")
        version = version[:-len(args.strip_suffix)]

    if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
        parser.error("sha must be a full Git commit SHA")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._/-]*", args.repository):
        parser.error("invalid image repository")
    tags = [version + args.suffix, args.latest, "sha-" + args.sha[:12] + args.suffix]
    for tag in tags:
        if not re.fullmatch(r"[\w][\w.-]{0,127}", tag, flags=re.ASCII):
            parser.error(f"invalid Docker tag: {tag!r}")
    print("\n".join(f"{args.repository}:{tag}" for tag in tags))


if __name__ == "__main__":
    main()
