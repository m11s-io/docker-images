"""Export only the fixed-shape, single-block Timestral neural prediction path."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

SOURCE_COMMIT = "a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff"
MODEL_ID = "mistralai/Timestral-5M"
MODEL_REVISION = "bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f"
REWRITES = {
    "src/timestral/scaler.py": [
        ("means.unfold(-1, patch_size, patch_size)", "means.unflatten(-1, (-1, patch_size))"),
        ("scales.unfold(-1, patch_size, patch_size)", "scales.unflatten(-1, (-1, patch_size))"),
    ],
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


def validation_cases() -> dict:
    import numpy as np
    rng = np.random.default_rng(20261029)
    random = rng.normal(size=(1, 128)).astype(np.float32)
    sine = np.sin(np.arange(128, dtype=np.float32) / 8)[None, :]
    observed = np.ones((1, 128), dtype=np.bool_)
    scattered = observed.copy(); scattered[:, ::7] = False
    leading = observed.copy(); leading[:, :32] = False
    return {
        "random": (random, observed.copy()),
        "sinusoidal": (sine, observed.copy()),
        "constant": (np.full((1, 128), 3, dtype=np.float32), observed.copy()),
        "scattered-missing": (np.where(scattered, random, 0).astype(np.float32), scattered),
        "leading-missing": (np.where(leading, sine, 0).astype(np.float32), leading),
    }


def validate_outputs(reference, actual) -> dict:
    import numpy as np
    for name, value in [("reference", reference), ("actual", actual)]:
        if value.shape != (1, 32, 21) or value.dtype != np.float32:
            raise ValueError(f"{name} must be FP32 [1,32,21]")
        if not np.isfinite(value).all():
            raise ValueError(f"{name} contains nonfinite values")
    np.testing.assert_allclose(actual, reference, rtol=1e-4, atol=1e-4)
    return {"max_absolute_error": float(np.max(np.abs(actual - reference))),
            "rtol": 1e-4, "atol": 1e-4}


def hardware() -> dict:
    cpu = {}
    if Path("/proc/cpuinfo").exists():
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            key, sep, val = line.partition(":")
            if sep and key.strip() in {"vendor_id", "model name"}:
                cpu.setdefault(key.strip(), val.strip())
    # Hardware identifiers alone cannot prove execution wasn't emulated.
    return {"architecture": platform.machine(), "cpu": cpu,
            "execution": "github-hosted" if os.environ.get("GITHUB_ACTIONS") else "local-unverified",
            "intel_validation_claimed": False}


def worker(args) -> None:
    """Separate processes prevent patched imports contaminating the reference."""
    sys.path.insert(0, str(Path(args.source) / "src"))
    import numpy as np
    import torch
    from timestral.loading import load_model
    torch.set_num_threads(2)
    model = load_model(args.checkpoint, dtype=torch.float32)
    if model.config.num_quantiles != 21 or 32 % model.config.patch_size:
        raise ValueError("unexpected model quantiles or patch size")

    class Block(torch.nn.Module):
        def __init__(self):
            super().__init__(); self.model = model

        def forward(self, context, observed):
            return self.model.predict_block(
                context, observed, torch.zeros(1, dtype=torch.long),
                horizon_patches=32 // self.model.config.patch_size,
            )

    block = Block().eval()
    output = Path(args.output)
    if args.worker == "reference":
        fixtures = {}
        with torch.inference_mode():
            for name, (context, observed) in validation_cases().items():
                expected = block(torch.from_numpy(context), torch.from_numpy(observed)).numpy()
                validate_outputs(expected, expected)
                fixtures[name] = {"context": context.tolist(), "observed": observed.tolist(),
                                  "quantiles": expected.tolist()}
        (output / "validation-fixtures.json").write_text(json.dumps(fixtures, allow_nan=False))
        return

    import openvino as ov
    with torch.inference_mode():
        example = validation_cases()["random"]
        ir = ov.convert_model(block, example_input=tuple(torch.from_numpy(x) for x in example),
                              input=[("context", [1, 128], ov.Type.f32),
                                     ("observed", [1, 128], ov.Type.boolean)])
    ir.output(0).get_tensor().set_names({"quantiles"})
    dest = output / "model/1/model.xml"
    dest.parent.mkdir(parents=True)
    ov.save_model(ir, dest, compress_to_fp16=False)
    compiled = ov.Core().compile_model(str(dest), "CPU", {"INFERENCE_PRECISION_HINT": "f32"})
    fixtures = json.loads((output / "validation-fixtures.json").read_text())
    results = {}
    for name, case in fixtures.items():
        actual = compiled({"context": np.array(case["context"], dtype=np.float32),
                           "observed": np.array(case["observed"], dtype=np.bool_)})[compiled.output(0)]
        results[name] = validate_outputs(np.array(case["quantiles"], dtype=np.float32), actual)
    packages = {name: importlib.metadata.version(name) for name in
                ["torch", "openvino", "numpy", "safetensors", "huggingface-hub"]}
    config = json.loads((Path(args.checkpoint) / "config.json").read_text())
    (output / "quantiles.json").write_text(json.dumps(config["quantile_knots"], indent=2) + "\n")
    report = {"source_commit": SOURCE_COMMIT, "model_id": MODEL_ID, "model_revision": MODEL_REVISION,
              "ci_commit": os.environ.get("GITHUB_SHA"),
              "ci_run": os.environ.get("GITHUB_RUN_ID"), "hardware": hardware(),
              "packages": packages, "cases": results, "passed": True,
              "inputs": {"context": {"shape": [1, 128], "dtype": "FP32"},
                         "observed": {"shape": [1, 128], "dtype": "BOOL"}},
              "output": {"quantiles": {"shape": [1, 32, 21], "dtype": "FP32"}},
              "precision_hint": "f32", "compress_to_fp16": False}
    (output / "validation.json").write_text(json.dumps(report, indent=2) + "\n")


def export(output: Path) -> None:
    from huggingface_hub import snapshot_download
    if output.exists():
        raise ValueError("output must not exist; use a fresh artifact directory")
    output.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "upstream"
        subprocess.run(["git", "init", "-q", str(source)], check=True)
        subprocess.run(["git", "-C", str(source), "fetch", "--depth=1",
                        "https://github.com/mistralai/timestral.git", SOURCE_COMMIT], check=True)
        subprocess.run(["git", "-C", str(source), "checkout", "-q", "FETCH_HEAD"], check=True)
        actual = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
        if actual != SOURCE_COMMIT:
            raise ValueError("source revision mismatch")
        checkpoint = Path(snapshot_download(MODEL_ID, revision=MODEL_REVISION, token=False,
                              allow_patterns=["config.json", "model.safetensors"]))
        patched = Path(tmp) / "patched"
        patch_source(source, patched)
        shutil.copy2(source / "LICENSE", output / "LICENSE")
        shutil.copy2(checkpoint / "config.json", output / "config.json")
        for mode, src in [("reference", source), ("convert", patched)]:
            subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", mode,
                            "--source", str(src), "--checkpoint", str(checkpoint),
                            "--output", str(output.resolve())], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", choices=["reference", "convert"])
    parser.add_argument("--source"); parser.add_argument("--checkpoint")
    options = parser.parse_args()
    if options.worker: worker(options)
    else: export(options.output)
