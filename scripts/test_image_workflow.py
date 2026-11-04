"""Behavioral contract for dynamic image workflow routing."""

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ImageWorkflowTest(unittest.TestCase):
    def test_workflow_routes_from_selector_outputs_and_preserves_product_hooks(self):
        workflow = (ROOT / ".github/workflows/build.yaml").read_text()
        self.assertIn("python3 scripts/image_matrix.py", workflow)
        for output in ("matrix-standard", "matrix-native", "timestral-required",
                       "comfy-mcp-selected", "timestral-openvino-selected"):
            self.assertIn(output, workflow)
        self.assertIn("join(matrix.tags, ',')", workflow)
        self.assertIn("uses: ./.github/workflows/timestral-standard.yaml", workflow)
        self.assertIn("publish-mcp-catalog:", workflow)
        self.assertIn("publish-timestral-profiles:", workflow)
        self.assertIn("image-checks:", workflow)
        self.assertIn("always()", workflow)
        self.assertNotIn("dorny/paths-filter", workflow)
        self.assertNotIn("NATIVE_IMAGES:", workflow)
        self.assertNotIn("type: choice", workflow)

    def test_standard_caller_supplies_shared_builder_contract(self):
        workflow = (ROOT / ".github/workflows/build.yaml").read_text()
        standard = workflow.split("  build-standard:", 1)[1].split("  native-build:", 1)[0]
        self.assertIn("uses: m11s-io/.github/.github/workflows/container-image.yml@main", standard)
        for name in ("source-ref", "context", "dockerfile", "repository", "tags",
                     "platforms", "cache-scope", "cache-mode", "free-space",
                     "description", "readme-file", "push"):
            self.assertIn(f"      {name}:", standard)
        self.assertIn("join(matrix.tags, ',')", standard)
        self.assertIn("DOCKER_USER:", standard)
        self.assertIn("DOCKER_PASS:", standard)


if __name__ == "__main__":
    unittest.main()
