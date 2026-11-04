"""Exercise selector outputs and the PR workflow's required-check gate."""

import json
import os
import pathlib
import subprocess
import textwrap
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/build.yaml"
SHA = "a" * 40


def selector_outputs(*args):
    result = subprocess.run(
        ["python3", str(ROOT / "scripts/image_matrix.py"), "--root", str(ROOT),
         "--event", "workflow_dispatch", "--sha", SHA, *args],
        capture_output=True, text=True, check=True,
    )
    return dict(line.split("=", 1) for line in result.stdout.splitlines())


def aggregate_gate_script():
    lines = WORKFLOW.read_text().splitlines()
    image_checks = lines.index("  image-checks:")
    run = lines.index("        run: |", image_checks)
    body = []
    for line in lines[run + 1:]:
        if line and not line.startswith("          "):
            break
        body.append(line[10:] if line.startswith("          ") else "")
    return textwrap.dedent("\n".join(body))


class ImageWorkflowTest(unittest.TestCase):
    def test_empty_and_selected_native_selector_outputs(self):
        empty = subprocess.run(
            ["python3", str(ROOT / "scripts/image_matrix.py"), "--root", str(ROOT),
             "--event", "push", "--sha", SHA, "--changed-json", "[]"],
            capture_output=True, text=True, check=True,
        )
        empty = dict(line.split("=", 1) for line in empty.stdout.splitlines())
        self.assertEqual(json.loads(empty["matrix-standard"]), {"include": []})
        self.assertEqual(json.loads(empty["matrix-native"]), {"include": []})
        self.assertEqual(empty["has-standard"], "false")
        self.assertEqual(empty["has-native"], "false")

        selected = selector_outputs("--selected", "comfy-mcp")
        native = json.loads(selected["matrix-native"])["include"]
        self.assertEqual([row["id"] for row in native], ["comfy-mcp"])
        self.assertEqual(json.loads(selected["matrix-standard"]), {"include": []})

    def test_timestral_selector_output_identifies_acceptance_and_profile_hooks(self):
        result = subprocess.run(
            ["python3", str(ROOT / "scripts/image_matrix.py"), "--root", str(ROOT),
             "--event", "push", "--sha", SHA, "--changed-json",
             '["timestral/openvino/backend.py"]'],
            capture_output=True, text=True, check=True,
        )
        output = dict(line.split("=", 1) for line in result.stdout.splitlines())
        rows = json.loads(output["matrix-standard"])["include"]
        self.assertEqual([row["id"] for row in rows], ["timestral-openvino"])
        self.assertEqual(output["timestral-required"], "true")
        self.assertEqual(output["timestral-openvino-selected"], "true")

    def test_aggregate_gate_accepts_empty_and_successful_selected_runs(self):
        script = aggregate_gate_script()
        empty = {
            "CHANGES_RESULT": "success", "STANDARD_RESULT": "skipped", "HAS_STANDARD": "false",
            "NATIVE_RESULT": "skipped", "HAS_NATIVE": "false", "TIMESTRAL_RESULT": "skipped",
            "TIMESTRAL_REQUIRED": "false",
        }
        selected = {
            "CHANGES_RESULT": "success", "STANDARD_RESULT": "success", "HAS_STANDARD": "true",
            "NATIVE_RESULT": "success", "HAS_NATIVE": "true", "TIMESTRAL_RESULT": "success",
            "TIMESTRAL_REQUIRED": "true",
        }
        for env in (empty, selected):
            with self.subTest(env=env):
                self.assertEqual(subprocess.run(["bash", "-e", "-c", script], env={**os.environ, **env}).returncode, 0)

    def test_aggregate_gate_rejects_failed_cancelled_and_required_skipped_jobs(self):
        base = {
            "CHANGES_RESULT": "success", "STANDARD_RESULT": "success", "HAS_STANDARD": "true",
            "NATIVE_RESULT": "skipped", "HAS_NATIVE": "false", "TIMESTRAL_RESULT": "skipped",
            "TIMESTRAL_REQUIRED": "false",
        }
        failures = (
            {**base, "STANDARD_RESULT": "failure"},
            {**base, "NATIVE_RESULT": "cancelled", "HAS_NATIVE": "true"},
            {**base, "CHANGES_RESULT": "cancelled"},
            {**base, "TIMESTRAL_RESULT": "skipped", "TIMESTRAL_REQUIRED": "true"},
            {**base, "STANDARD_RESULT": "skipped"},
        )
        for env in failures:
            with self.subTest(env=env):
                self.assertNotEqual(subprocess.run(["bash", "-e", "-c", aggregate_gate_script()],
                                                   env={**os.environ, **env}).returncode, 0)


if __name__ == "__main__":
    unittest.main()
