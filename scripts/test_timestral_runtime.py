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
    def test_only_kserve_serving_and_dependency_roots_remain(self):
        for name in ('app','pyproject.toml','uv.lock','requirements-cuda.txt'):
            self.assertFalse((ROOT/'timestral'/name).exists(),name)
        for variant in ('cpu','cuda','rocm','openvino'):
            dockerfile=(ROOT/f'timestral/Dockerfile.{variant}').read_text()
            self.assertIn('"-m", "serving"',dockerfile)
            self.assertRegex(dockerfile,r'python:3\.13\.\d+-slim-bookworm@sha256:[a-f0-9]{64}')
        workflow=(ROOT/'.github/workflows/build.yaml').read_text()
        job=workflow.split('  timestral-tests:',1)[1].split('\n  changes:',1)[0]
        self.assertIn('uses: ./.github/workflows/timestral-standard.yaml',job)
        acceptance=(ROOT/'.github/workflows/timestral-standard.yaml').read_text()
        self.assertIn('python-version: "3.13"',acceptance)
        self.assertNotIn('  pull_request:',acceptance)
        # A reusable run must not cancel another caller's required acceptance.
        self.assertNotIn('\nconcurrency:',acceptance)
        self.assertNotIn('tests/test_api.py',job)
        self.assertIn('--project timestral/dependencies/cpu',acceptance)
        self.assertIn("needs.changes.outputs.timestral-required == 'true'",job)
        build=workflow.split('  build-standard:',1)[1].split('  native-build:',1)[0]
        self.assertIn('needs: [changes, timestral-tests]',build)

    def test_cpu_uses_frozen_lock_and_cuda_uses_same_torch_release(self):
        project = tomllib.loads((ROOT / "timestral/dependencies/cpu/pyproject.toml").read_text())
        requirement = next(d for d in project["project"]["dependencies"] if d.startswith("torch=="))
        release = requirement.split("==", 1)[1].split("+", 1)[0]
        cpu = (ROOT / "timestral/Dockerfile.cpu").read_text()
        self.assertIn("uv sync --frozen --no-dev", cpu)
        self.assertNotIn("--no-install-package torch", cpu)
        cuda = (ROOT / "timestral/Dockerfile.cuda").read_text()
        cuda_project = tomllib.loads((ROOT / "timestral/dependencies/cuda/pyproject.toml").read_text())
        self.assertIn(f"torch=={release}+cu130", cuda_project["project"]["dependencies"])
        self.assertIn("uv sync --frozen --no-dev", cuda)

    def test_both_images_check_installed_upstream_version(self):
        for variant in ("cpu", "cuda"):
            with self.subTest(variant=variant):
                dockerfile = (ROOT / f"timestral/Dockerfile.{variant}").read_text()
                self.assertIn("ARG TIMESTRAL_VERSION=1.0.0", dockerfile)
                self.assertIn("check_version.py", dockerfile)
                self.assertIn("TIMESTRAL_VERSION", dockerfile)

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
