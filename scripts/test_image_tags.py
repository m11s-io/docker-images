import pathlib
import subprocess
import sys
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).with_name("image_tags.py")
SHA = "494d7fbb6b32003ec4dbcabdaef93e07a033817e"


class ImageTagsTest(unittest.TestCase):
    def resolve(self, *args, dockerfile=None):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "Dockerfile"
            if dockerfile is not None:
                path.write_text(dockerfile)
                args = (*args, "--dockerfile", str(path))
            return subprocess.run(
                [sys.executable, str(SCRIPT), "--repository", "m11s/example",
                 "--latest", "latest", "--sha", SHA, *args],
                capture_output=True, text=True,
            )

    def test_release_version_and_commit_tag(self):
        result = self.resolve("--version", "0.5.5")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "m11s/example:0.5.5", "m11s/example:latest",
            "m11s/example:sha-494d7fbb6b32",
        ])

    def test_rclone_version_follows_updated_base_and_keeps_suffix(self):
        result = self.resolve("--base-image", "rclone/rclone", "--suffix=-inotify",
                              dockerfile="FROM rclone/rclone:1.75@sha256:abc AS base\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "m11s/example:1.75-inotify")
        self.assertEqual(result.stdout.splitlines()[2], "m11s/example:sha-494d7fbb6b32-inotify")

    def test_vllm_arg_follows_pr_version(self):
        result = self.resolve("--base-arg", "VLLM_BASE_IMAGE", dockerfile=(
            "ARG VLLM_BASE_IMAGE=vllm/vllm-openai:v0.31.0-x86_64@sha256:abc\n"
            "FROM ${VLLM_BASE_IMAGE}\n"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "m11s/example:v0.31.0-x86_64")

    def test_variant_tags_have_separate_commit_alias(self):
        result = self.resolve("--version", "0.5.5", "--suffix=-gguf")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "m11s/example:0.5.5-gguf", "m11s/example:latest",
            "m11s/example:sha-494d7fbb6b32-gguf",
        ])

    def test_missing_or_ambiguous_base_fails(self):
        for content in ["FROM other:1\n", "FROM rclone/rclone:1\nFROM rclone/rclone:2\n"]:
            with self.subTest(content=content):
                result = self.resolve("--base-image", "rclone/rclone", dockerfile=content)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("exactly one", result.stderr)

    def test_untagged_or_invalid_reference_fails(self):
        for reference in ["registry:5000/example@sha256:abc", "example:bad/tag"]:
            with self.subTest(reference=reference):
                result = self.resolve("--base-arg", "BASE", dockerfile=f"ARG BASE={reference}\n")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("tag", result.stderr)


if __name__ == "__main__":
    unittest.main()
