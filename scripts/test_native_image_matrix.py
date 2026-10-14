import unittest

from native_image_matrix import build_matrix


IMAGES = [
    {"context": "deepseek-harness", "repository": "m11s/deepseek-harness", "version": "0.2.0-rc.2", "latest": "latest"},
    {"context": "chromium-cdp", "repository": "m11s/chromium-cdp", "version": "bookworm-20261005", "latest": "latest"},
    {"context": "comfy-mcp", "repository": "m11s/comfy-mcp", "version": "0.2.3", "latest": "latest"},
]
SHA = "494d7fbb6b32003ec4dbcabdaef93e07a033817e"


class NativeImageMatrixTest(unittest.TestCase):
    def matrix(self, event="push", selected="all", changed=None):
        return build_matrix(IMAGES, event, selected, changed or {}, SHA)["include"]

    def test_push_builds_only_changed_images(self):
        rows = self.matrix(changed={"chromium-cdp": "true", "deepseek-harness": "false"})
        self.assertEqual([row["context"] for row in rows], ["chromium-cdp"])

    def test_workflow_only_push_has_empty_matrix(self):
        self.assertEqual(self.matrix(), [])

    def test_dispatch_all_includes_every_native_image(self):
        self.assertEqual(len(self.matrix(event="workflow_dispatch")), 3)

    def test_dispatch_specific_image_ignores_path_flags(self):
        rows = self.matrix(event="workflow_dispatch", selected="comfy-mcp", changed={"deepseek-harness": "true"})
        self.assertEqual([row["context"] for row in rows], ["comfy-mcp"])

    def test_dispatch_amd64_only_image_has_empty_native_matrix(self):
        self.assertEqual(self.matrix(event="workflow_dispatch", selected="comfyui"), [])

    def test_tags_preserve_version_latest_and_twelve_character_sha(self):
        row = self.matrix(event="workflow_dispatch", selected="deepseek-harness")[0]
        self.assertEqual(row["meta-tags"].splitlines(), [
            "type=raw,value=0.2.0-rc.2", "type=raw,value=latest", "type=raw,value=sha-494d7fbb6b32",
        ])


if __name__ == "__main__":
    unittest.main()
