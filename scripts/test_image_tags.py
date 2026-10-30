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

    def test_timestral_variants_resolve_pinned_version_and_distinct_commit_aliases(self):
        for variant in ("cpu", "cuda", "rocm", "openvino"):
            with self.subTest(variant=variant):
                dockerfile = (pathlib.Path(__file__).parents[1] / "timestral" /
                              f"Dockerfile.{variant}")
                result = self.resolve("--version-arg", "SERVING_VERSION",
                                      f"--suffix=-{variant}", f"--latest=candidate-standard-v1-{variant}",
                                      dockerfile=dockerfile.read_text())
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), [
                    f"m11s/example:standard-v1-0.1.0-{variant}",
                    f"m11s/example:candidate-standard-v1-{variant}",
                    f"m11s/example:sha-494d7fbb6b32-{variant}",
                ])

    def test_timestral_variants_are_manual_and_path_selected_in_existing_build_workflow(self):
        workflow = (pathlib.Path(__file__).parents[1] / ".github" / "workflows" /
                    "build.yaml").read_text()
        self.assertIn("- timestral-cpu", workflow)
        self.assertIn("- timestral-cuda", workflow)
        self.assertIn('"timestral/**"', workflow)
        self.assertIn("timestral/Dockerfile.cpu", workflow)
        self.assertIn("timestral/Dockerfile.cuda", workflow)
        self.assertIn("latest-cpu", workflow)
        self.assertIn("latest-cuda", workflow)
        self.assertIn("timestral-tests:", workflow)
        self.assertIn("uv run --frozen pytest tests/test_api.py -q", workflow)

    def test_variant_tags_have_separate_commit_alias(self):
        result = self.resolve("--version", "0.5.5", "--suffix=-gguf")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "m11s/example:0.5.5-gguf", "m11s/example:latest",
            "m11s/example:sha-494d7fbb6b32-gguf",
        ])

    def test_application_arg_follows_upstream_version_and_keeps_suffix(self):
        result = self.resolve("--version-arg", "CADDY_VERSION", "--suffix=-cloudflare",
                              dockerfile="ARG CADDY_VERSION=2.11.7\nFROM caddy:2\nARG CADDY_VERSION\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "m11s/example:2.11.7-cloudflare", "m11s/example:latest",
            "m11s/example:sha-494d7fbb6b32-cloudflare",
        ])

    def test_release_ref_strips_only_the_declared_prefix(self):
        result = self.resolve("--version-arg", "DSH_REF", "--strip-prefix", "dsh-v",
                              dockerfile="ARG DSH_REF=dsh-v0.2.1-rc.1\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "m11s/example:0.2.1-rc.1")

    def test_caddy_base_arg_strips_platform_suffix(self):
        result = self.resolve("--base-arg", "CADDY_BASE_IMAGE", "--strip-suffix=-alpine",
                              "--suffix=-cloudflare", dockerfile=(
                                  "ARG CADDY_BASE_IMAGE=caddy:2.11.7-alpine@sha256:abc\n"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "m11s/example:2.11.7-cloudflare")

    def test_unexpected_base_suffix_fails(self):
        result = self.resolve("--base-arg", "BASE", "--strip-suffix=-alpine",
                              dockerfile="ARG BASE=caddy:2.11.7-other@sha256:abc\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("declared suffix", result.stderr)

    def test_missing_duplicate_or_dynamic_application_arg_fails(self):
        for content in ["ARG OTHER=1\n", "ARG APP_VERSION=1\nARG APP_VERSION=2\n",
                        "ARG APP_VERSION=${OTHER}\n"]:
            with self.subTest(content=content):
                result = self.resolve("--version-arg", "APP_VERSION", dockerfile=content)
                self.assertNotEqual(result.returncode, 0)

    def test_unexpected_release_prefix_fails(self):
        result = self.resolve("--version-arg", "DSH_REF", "--strip-prefix", "dsh-v",
                              dockerfile="ARG DSH_REF=other-v0.2.0\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("prefix", result.stderr)

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
