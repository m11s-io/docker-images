import json
import tempfile
import unittest
from pathlib import Path
import subprocess
from unittest.mock import patch

from image_matrix import _paths_from_git, build_matrix, discover_images


SHA = "494d7fbb6b32003ec4dbcabdaef93e07a033817e"


class ImageMatrixTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def image(self, folder, config):
        directory = self.root / folder
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "Dockerfile").write_text("ARG APP_VERSION=1.2.3\n")
        (directory / "image.json").write_text(json.dumps(config))

    def test_inferred_defaults_and_tags(self):
        self.image("plain", {"version": "1.2.3"})
        result = build_matrix(self.root, "workflow_dispatch", "all", SHA)
        row = result["standard"]["include"][0]
        self.assertEqual(row["id"], "plain")
        self.assertEqual(row["repository"], "m11s/plain")
        self.assertEqual(row["build_context"], "plain")
        self.assertEqual(row["dockerfile"], "plain/Dockerfile")
        self.assertEqual(row["platforms"], "linux/amd64")
        self.assertEqual(row["tags"], ["m11s/plain:1.2.3", "m11s/plain:latest", "m11s/plain:sha-494d7fbb6b32"])

    def test_new_manifest_is_discovered_without_workflow_enrollment(self):
        self.image("new-image", {"version": "2.0"})
        self.assertEqual([x["folder"] for x in discover_images(self.root)], ["new-image"])

    def test_variants_select_shared_and_variant_files(self):
        self.image("multi", {"variants": {
            "cpu": {"version": "1", "watch": ["multi/common/**", "multi/Dockerfile.cpu"]},
            "gpu": {"version": "1", "dockerfile": "multi/Dockerfile.gpu", "watch": ["multi/common/**", "multi/Dockerfile.gpu"]},
        }})
        shared = build_matrix(self.root, "push", "all", SHA, changed_paths=["multi/common/lib.py"])
        self.assertEqual([r["id"] for r in shared["standard"]["include"]], ["multi-cpu", "multi-gpu"])
        manifest = build_matrix(self.root, "push", "all", SHA, changed_paths=["multi/image.json"])
        self.assertEqual([r["id"] for r in manifest["standard"]["include"]], ["multi-cpu", "multi-gpu"])
        specific = build_matrix(self.root, "push", "all", SHA, changed_paths=["multi/Dockerfile.gpu"])
        self.assertEqual([r["id"] for r in specific["standard"]["include"]], ["multi-gpu"])

    def test_native_defaults_and_semantic_flags(self):
        self.image("timestral", {"variants": {"openvino": {
            "version": "1", "builder": "native", "timestral": True,
            "timestral_openvino": True,
        }}})
        result = build_matrix(self.root, "workflow_dispatch", "all", SHA)
        row = result["native"]["include"][0]
        self.assertEqual(row["platforms"], "linux/amd64,linux/arm64")
        self.assertEqual(row["cache_mode"], "min")
        self.assertTrue(result["timestral_required"])
        self.assertTrue(result["timestral_openvino_selected"])

    def test_invalid_manifest_fails_before_path_selection(self):
        self.image("bad", {"version": "1", "mystery": True})
        with self.assertRaisesRegex(ValueError, "unknown"):
            build_matrix(self.root, "push", "all", SHA, changed_paths=[])

    def test_invalid_selected_fails_even_when_nothing_changed(self):
        self.image("plain", {"version": "1"})
        with self.assertRaisesRegex(ValueError, "selected"):
            build_matrix(self.root, "push", "not-here", SHA, changed_paths=[])

    def test_missing_history_selects_everything(self):
        self.image("plain", {"version": "1"})
        result = build_matrix(self.root, "push", "all", SHA, changed_paths=None)
        self.assertEqual([r["id"] for r in result["standard"]["include"]], ["plain"])

    def test_missing_base_and_head_select_everything(self):
        self.image("plain", {"version": "1"})
        result = build_matrix(self.root, "push", "all", SHA, base=None, head=None)
        self.assertEqual([r["id"] for r in result["standard"]["include"]], ["plain"])

    def test_missing_git_refs_skip_subprocess_diff(self):
        with patch("image_matrix.subprocess.check_output", side_effect=AssertionError("git must not run without refs")):
            self.assertIsNone(_paths_from_git(self.root, "push", None, None))

    def test_changed_paths_must_be_repository_relative(self):
        self.image("plain", {"version": "1"})
        for invalid_path in ("/plain/Dockerfile", "../plain/Dockerfile", "plain/../other/Dockerfile"):
            with self.subTest(path=invalid_path), self.assertRaisesRegex(ValueError, "repository-relative"):
                build_matrix(self.root, "push", "all", SHA, changed_paths=[invalid_path])

    def test_timestral_openvino_workflow_selects_only_its_watched_image(self):
        self.image("timestral", {"variants": {
            "openvino": {"version": "1", "watch": [".github/workflows/timestral-openvino.yaml"]},
        }})
        self.image("caddy", {"version": "1"})
        result = build_matrix(self.root, "push", "all", SHA,
                              changed_paths=[".github/workflows/timestral-openvino.yaml"])
        self.assertEqual(result["selected_ids"], ["timestral-openvino"])

    def test_docs_only_and_deleted_renamed_paths(self):
        self.image("plain", {"version": "1"})
        empty = build_matrix(self.root, "push", "all", SHA, changed_paths=["plain/README.md"])
        self.assertEqual(empty["selected_ids"], [])
        deletion = build_matrix(self.root, "push", "all", SHA, changed_paths=["plain/old.py", "plain/new.py"])
        self.assertEqual(deletion["selected_ids"], ["plain"])

    def test_shared_selector_changes_fan_out(self):
        self.image("a", {"version": "1"})
        self.image("b", {"version": "1"})
        result = build_matrix(self.root, "push", "all", SHA, changed_paths=["scripts/image_tags.py"])
        self.assertEqual(result["selected_ids"], ["a", "b"])

    def test_removed_manifest_fails_with_retirement_guidance(self):
        self.image("plain", {"version": "1"})
        (self.root / "plain" / "image.json").unlink()
        with self.assertRaisesRegex(ValueError, "explicitly retire"):
            build_matrix(self.root, "push", "all", SHA, changed_paths=["plain/image.json"])

    def test_pull_request_uses_merge_base_while_push_uses_given_range(self):
        def git(*args):
            return subprocess.check_output(["git", *args], cwd=self.root, text=True).strip()
        git("init", "-q")
        git("config", "user.email", "tests@example.invalid")
        git("config", "user.name", "Tests")
        (self.root / "base.txt").write_text("base")
        git("add", "base.txt")
        git("commit", "-qm", "base")
        merge_base = git("rev-parse", "HEAD")
        git("checkout", "-qb", "feature")
        (self.root / "feature.txt").write_text("feature")
        git("add", "feature.txt")
        git("commit", "-qm", "feature")
        feature_head = git("rev-parse", "HEAD")
        git("checkout", "-q", "-b", "main", merge_base)
        (self.root / "base-later.txt").write_text("later")
        git("add", "base-later.txt")
        git("commit", "-qm", "base advanced")
        base_head = git("rev-parse", "HEAD")
        self.assertEqual(_paths_from_git(self.root, "pull_request", base_head, feature_head), ["feature.txt"])
        self.assertEqual(_paths_from_git(self.root, "push", merge_base, feature_head), ["feature.txt"])


if __name__ == "__main__":
    unittest.main()
