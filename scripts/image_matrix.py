#!/usr/bin/env python3
"""Discover image manifests, select changed images, and resolve publish tags."""

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


SOURCES = {"base-image", "base-arg", "version-arg", "deb-package"}
FIELDS = {
    "repository", "build_context", "dockerfile", "readme_file", "description",
    "version", "version_source", "version_ref", "tag_suffix", "strip_prefix",
    "strip_suffix", "latest", "platforms", "builder", "cache_mode", "free_space",
    "watch", "ignore", "timestral", "comfy_mcp", "timestral_openvino", "variants",
}


def _fail(message):
    raise ValueError(message)


def _safe_path(root, value, label):
    if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in PurePosixPath(value).parts:
        _fail(f"{label} must be a repository-relative path")
    resolved = (root / value).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        _fail(f"{label} escapes repository through a symlink: {value}")
    return value


def _validate_config(config, label, top_level=False):
    if not isinstance(config, dict):
        _fail(f"{label} must be a JSON object")
    allowed = FIELDS if top_level else FIELDS - {"variants"}
    unknown = set(config) - allowed
    if unknown:
        _fail(f"{label} has unknown field(s): {', '.join(sorted(unknown))}")
    for key in ("description", "version", "version_source", "version_ref", "tag_suffix", "strip_prefix", "strip_suffix", "latest", "platforms", "builder", "cache_mode"):
        if key in config and not isinstance(config[key], str):
            _fail(f"{label}.{key} must be a string")
    for key in ("free_space", "timestral", "comfy_mcp", "timestral_openvino"):
        if key in config and type(config[key]) is not bool:
            _fail(f"{label}.{key} must be a boolean")
    for key in ("watch", "ignore"):
        if key in config and (not isinstance(config[key], list) or not all(isinstance(x, str) and x for x in config[key])):
            _fail(f"{label}.{key} must be an array of non-empty glob strings")


def discover_images(root):
    root = Path(root).resolve()
    images = []
    ids = set()
    for manifest in sorted(root.glob("*/image.json")):
        _safe_path(root, str(manifest.relative_to(root)), "manifest")
        folder = manifest.parent.name
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", folder):
            _fail(f"invalid image folder ID: {folder}")
        try:
            raw = json.loads(manifest.read_text())
        except (OSError, json.JSONDecodeError) as error:
            _fail(f"cannot read {manifest}: {error}")
        _validate_config(raw, str(manifest.relative_to(root)), top_level=True)
        variants = raw.get("variants")
        if variants is not None:
            if not isinstance(variants, dict) or not variants:
                _fail(f"{folder}.variants must be a non-empty object")
            shared = {k: v for k, v in raw.items() if k != "variants"}
            for variant, values in variants.items():
                if not isinstance(variant, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", variant):
                    _fail(f"invalid variant ID in {folder}: {variant!r}")
                _validate_config(values, f"{folder}.variants.{variant}")
                item = {**shared, **values, "folder": folder, "id": folder + "-" + variant}
                _append_image(root, item, images, ids)
        else:
            item = {**raw, "folder": folder, "id": folder}
            _append_image(root, item, images, ids)
    return images


def _append_image(root, item, images, ids):
    ident = item["id"]
    if ident in ids:
        _fail(f"duplicate image ID: {ident}")
    ids.add(ident)
    sources = int("version" in item) + int("version_source" in item or "version_ref" in item)
    if sources != 1:
        _fail(f"{ident} must declare exactly one version or version_source/version_ref")
    if "version_source" in item:
        if item.get("version_source") not in SOURCES or not isinstance(item.get("version_ref"), str) or not item["version_ref"]:
            _fail(f"{ident} has invalid version_source/version_ref")
    elif "version_ref" in item:
        _fail(f"{ident} cannot declare version_ref without version_source")
    builder = item.get("builder", "standard")
    if builder not in ("standard", "native"):
        _fail(f"{ident}.builder must be standard or native")
    if item.get("cache_mode", "max") not in ("max", "min"):
        _fail(f"{ident}.cache_mode must be max or min")
    repository = item.get("repository", f"m11s/{item['folder']}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._/-]*", repository):
        _fail(f"{ident}.repository is invalid")
    if "platforms" in item and not item["platforms"]:
        _fail(f"{ident}.platforms cannot be empty")
    for key in ("repository", "build_context", "dockerfile", "readme_file"):
        if key in item:
            _safe_path(root, item[key], f"{ident}.{key}")
    for key in ("watch", "ignore"):
        for glob in item.get(key, []):
            if glob.startswith("/") or ".." in PurePosixPath(glob).parts:
                _fail(f"{ident}.{key} contains an unsafe glob: {glob}")
    images.append(item)


def _paths_from_git(root, event, base, head):
    if not base or not head:
        return None
    try:
        if event == "pull_request":
            merge = subprocess.check_output(["git", "merge-base", base, head], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
            rev_range = f"{merge}...{head}"
        else:
            rev_range = f"{base}..{head}"
        raw = subprocess.check_output(["git", "diff", "--name-status", "-M", rev_range], cwd=root, text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, OSError):
        return None
    paths = []
    for line in raw.splitlines():
        parts = line.split("\t")
        if parts[0].startswith("R") or parts[0].startswith("C"):
            paths.extend(parts[1:3])
        elif len(parts) > 1:
            paths.append(parts[1])
    return paths


def _resolve_tags(root, image, sha):
    folder, ident = image["folder"], image["id"]
    repository = image.get("repository", f"m11s/{folder}")
    dockerfile = image.get("dockerfile", f"{folder}/Dockerfile")
    latest = image.get("latest", "latest" + image.get("tag_suffix", ""))
    args = [sys.executable, str(Path(__file__).with_name("image_tags.py")), "--repository", repository,
            "--latest", latest, "--sha", sha, "--strip-prefix", image.get("strip_prefix", ""),
            "--strip-suffix=" + image.get("strip_suffix", ""), "--suffix=" + image.get("tag_suffix", "")]
    if "version" in image:
        args.extend(["--version", image["version"]])
    else:
        args.extend(["--" + image["version_source"], image["version_ref"], "--dockerfile", dockerfile])
    try:
        return subprocess.check_output(args, cwd=root, text=True, stderr=subprocess.PIPE).splitlines()
    except subprocess.CalledProcessError as error:
        _fail(error.stderr.strip() or f"cannot resolve tags for {ident}")


def _match(path, pattern):
    # Git-style globs treat **/ as matching zero or more directory levels.
    expression = ""
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            expression += "(?:.*/)?"
            index += 3
        elif pattern.startswith("**", index):
            expression += ".*"
            index += 2
        elif pattern[index] == "*":
            expression += "[^/]*"
            index += 1
        elif pattern[index] == "?":
            expression += "[^/]"
            index += 1
        else:
            expression += re.escape(pattern[index])
            index += 1
    return re.fullmatch(expression, path) is not None


def build_matrix(root, event, selected="all", sha="", base=None, head=None, changed_paths=None):
    root = Path(root).resolve()
    images = discover_images(root)  # validate all manifests before any selection decision
    ids = {image["id"] for image in images}
    if selected != "all" and selected not in ids:
        _fail(f"unknown selected image {selected!r}; expected all or one of: {', '.join(sorted(ids))}")
    if event not in ("push", "pull_request", "workflow_dispatch"):
        _fail(f"unsupported event: {event}")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        _fail("sha must be a full Git commit SHA")
    if changed_paths is None and event != "workflow_dispatch":
        changed_paths = _paths_from_git(root, event, base, head)
    all_paths = changed_paths is None
    if changed_paths is None:
        changed_paths = []
    if not isinstance(changed_paths, list) or not all(isinstance(p, str) and p for p in changed_paths):
        _fail("changed paths must be an array of non-empty repository paths")
    for path in changed_paths:
        parsed = PurePosixPath(path)
        if parsed.is_absolute() or ".." in parsed.parts:
            _fail(f"changed path must be repository-relative and cannot traverse parents: {path!r}")
    current_manifests = {f"{image['folder']}/image.json" for image in images}
    for path in changed_paths:
        if PurePosixPath(path).name == "image.json" and path not in current_manifests and not (root / path).exists():
            _fail(f"enrolled image manifest {path} was removed; explicitly retire the image target before deleting it")
    resolved_tags = {image["id"]: _resolve_tags(root, image, sha) for image in images}
    shared_scripts = {"scripts/image_matrix.py", "scripts/test_image_matrix.py", "scripts/image_tags.py",
                      "scripts/test_image_tags.py"}
    shared_workflows = {".github/workflows/build.yaml", ".github/workflows/lint.yaml"}
    global_change = all_paths or any(p in shared_scripts or p in shared_workflows for p in changed_paths)
    standard, native, selected_ids = [], [], []
    for image in images:
        ident, folder = image["id"], image["folder"]
        if event == "workflow_dispatch":
            enabled = selected == "all" or selected == ident
        elif global_change:
            enabled = True
        else:
            watch = [f"{folder}/image.json", *image.get("watch", [f"{folder}/**"])]
            ignore = image.get("ignore", [f"{folder}/**/*.md", f"{folder}/**/docs/**",
                f"{folder}/**/compose*.yaml", f"{folder}/**/compose*.yml",
                f"{folder}/**/docker-compose*.yaml", f"{folder}/**/docker-compose*.yml"])
            enabled = any(any(_match(path, pattern) for pattern in watch) and not any(_match(path, pattern) for pattern in ignore) for path in changed_paths)
        if not enabled:
            continue
        selected_ids.append(ident)
        row = {
            "id": ident, "context": ident,
            "repository": image.get("repository", f"m11s/{folder}"),
            "build_context": image.get("build_context", folder),
            "dockerfile": image.get("dockerfile", f"{folder}/Dockerfile"),
            "readme_file": image.get("readme_file", f"{folder}/README.md"),
            "latest": image.get("latest", "latest" + image.get("tag_suffix", "")),
            "platforms": image.get("platforms", "linux/amd64,linux/arm64" if image.get("builder") == "native" else "linux/amd64"),
            "builder": image.get("builder", "standard"),
            "cache_mode": image.get("cache_mode", "min" if image.get("builder") == "native" else "max"),
            "free_space": image.get("free_space", False),
            "description": image.get("description", ""),
        }
        for key in ("version", "version_source", "version_ref", "tag_suffix", "strip_prefix", "strip_suffix"):
            if key in image:
                row[key] = image[key]
        tags = resolved_tags[ident]
        row["tags"] = tags
        row["meta-tags"] = "\n".join("type=raw,value=" + tag.split(":", 1)[1] for tag in tags)
        (native if row["builder"] == "native" else standard).append(row)
    return {
        "standard": {"include": standard}, "native": {"include": native}, "selected_ids": selected_ids,
        "has_standard": bool(standard), "has_native": bool(native),
        "timestral_required": any(x.get("timestral") for x in images if x["id"] in selected_ids),
        "comfy_mcp_selected": any(x.get("comfy_mcp", x["id"] == "comfy-mcp") for x in images if x["id"] in selected_ids),
        "timestral_openvino_selected": any(x.get("timestral_openvino", x["id"] == "timestral-openvino") for x in images if x["id"] in selected_ids),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", required=True, choices=("push", "pull_request", "workflow_dispatch"))
    parser.add_argument("--selected", default="all")
    parser.add_argument("--sha", required=True)
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--changed-json", help="JSON array of changed paths for deterministic selection")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args(argv)
    changed = json.loads(args.changed_json) if args.changed_json is not None else None
    result = build_matrix(args.root, args.event, args.selected, args.sha, args.base, args.head, changed)
    for key, value in (("matrix-standard", result["standard"]), ("matrix-native", result["native"]),
                       ("selected-ids", result["selected_ids"])):
        print(f"{key}=" + json.dumps(value, separators=(",", ":")))
    for key in ("has_standard", "has_native", "timestral_required", "comfy_mcp_selected", "timestral_openvino_selected"):
        print(key.replace("_", "-") + "=" + str(result[key]).lower())


if __name__ == "__main__":
    try:
        main()
    except (ValueError, json.JSONDecodeError) as error:
        print(f"image_matrix: {error}", file=sys.stderr)
        raise SystemExit(2)
