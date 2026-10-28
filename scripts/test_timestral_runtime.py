"""Guard the Python and PyTorch contract across Timestral's build and CI."""

import pathlib
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class TimestralRuntimeTest(unittest.TestCase):
    def test_python_315_is_used_by_project_both_images_and_ci(self):
        project = tomllib.loads((ROOT / "timestral/pyproject.toml").read_text())
        self.assertEqual(project["project"]["requires-python"], ">=3.15,<3.16")
        for variant in ("cpu", "cuda"):
            dockerfile = (ROOT / f"timestral/Dockerfile.{variant}").read_text()
            self.assertRegex(dockerfile, r"ARG PYTHON_BASE=python:3\.15\.\d+-slim-bookworm@sha256:[a-f0-9]{64}")
        workflow = (ROOT / ".github/workflows/build.yaml").read_text()
        job = workflow.split("  timestral-tests:", 1)[1].split("\n  changes:", 1)[0]
        self.assertIn('python-version: "3.15"', job)

    def test_cpu_uses_frozen_lock_and_cuda_uses_same_torch_release(self):
        project = tomllib.loads((ROOT / "timestral/pyproject.toml").read_text())
        requirement = next(d for d in project["project"]["dependencies"] if d.startswith("torch=="))
        release = requirement.split("==", 1)[1].split("+", 1)[0]
        cpu = (ROOT / "timestral/Dockerfile.cpu").read_text()
        self.assertIn("uv sync --frozen --no-dev", cpu)
        self.assertNotIn("--no-install-package torch", cpu)
        cuda = (ROOT / "timestral/Dockerfile.cuda").read_text()
        self.assertRegex(cuda, rf"torch=={re.escape(release)}\+cu130(?:\s|$)")

    def test_both_images_check_installed_upstream_version(self):
        for variant in ("cpu", "cuda"):
            with self.subTest(variant=variant):
                dockerfile = (ROOT / f"timestral/Dockerfile.{variant}").read_text()
                self.assertIn("ARG TIMESTRAL_VERSION=1.0.0", dockerfile)
                self.assertIn("check_version.py", dockerfile)
                self.assertIn("TIMESTRAL_VERSION", dockerfile)

    def test_rocm_keeps_amd_torch_and_uses_matching_api_dependencies(self):
        dockerfile = (ROOT / "timestral/Dockerfile.rocm").read_text()
        self.assertIn("--require-hashes --no-deps -r requirements-rocm.txt", dockerfile)
        self.assertIn("assert torch.version.hip", dockerfile)
        self.assertIn("MODEL_DEVICE=cuda", dockerfile)
        self.assertIn("tests/test_api.py", dockerfile)
        self.assertIn("COPY --from=validation", dockerfile)
        requirements = (ROOT / "timestral/requirements-rocm.in").read_text().splitlines()
        project = tomllib.loads((ROOT / "timestral/pyproject.toml").read_text())
        for dependency in project["project"]["dependencies"]:
            if dependency.startswith(("fastapi==", "pydantic-settings==", "uvicorn[standard]==")):
                self.assertIn(dependency, requirements)
        lock = (ROOT / "timestral/requirements-rocm.txt").read_text()
        self.assertNotRegex(lock, r"(?m)^(torch|triton|nvidia-[a-z-]+)==")
        upstream = next(d for d in project["project"]["dependencies"] if d.startswith("timestral @"))
        self.assertIn(upstream, dockerfile)

    def test_version_check_accepts_match_and_rejects_mismatch(self):
        checker = ROOT / "timestral/check_version.py"
        with tempfile.TemporaryDirectory() as directory:
            dist_info = pathlib.Path(directory) / "timestral-1.0.0.dist-info"
            dist_info.mkdir()
            (dist_info / "METADATA").write_text(
                "Metadata-Version: 2.1\nName: timestral\nVersion: 1.0.0\n\n"
            )
            env = {"PYTHONPATH": directory}
            matched = subprocess.run(
                [sys.executable, str(checker), "1.0.0"], capture_output=True,
                text=True, env=env,
            )
            self.assertEqual(matched.returncode, 0, matched.stderr)
            mismatch = subprocess.run(
                [sys.executable, str(checker), "9.9.9"], capture_output=True,
                text=True, env=env,
            )
            self.assertNotEqual(mismatch.returncode, 0)
            self.assertIn("does not match image version", mismatch.stderr)


if __name__ == "__main__":
    unittest.main()
