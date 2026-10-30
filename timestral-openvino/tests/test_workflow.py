"""Guard publish authorization and artifact provenance at the workflow boundary."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

class WorkflowTest(unittest.TestCase):
    def test_publication_requires_main_dispatch_and_successful_validation(self):
        path=ROOT/".github/workflows/timestral-openvino.yaml"
        self.assertTrue(path.exists(),"publishing workflow is missing")
        import yaml
        workflow=yaml.safe_load(path.read_text())
        jobs=workflow["jobs"]
        publish=jobs["publish"]
        self.assertEqual(publish["needs"],["validate"])
        self.assertEqual(publish["if"],"github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'")
        self.assertEqual(publish["permissions"],{"contents":"read","id-token":"write"})
        self.assertEqual(workflow["permissions"],{"contents":"read"})
        self.assertNotIn("id-token",jobs["validate"].get("permissions",{}))
        self.assertFalse(workflow["concurrency"]["cancel-in-progress"])
        self.assertEqual(workflow["concurrency"]["group"],"timestral-openvino-${{ github.ref }}")
        self.assertEqual(publish["env"]["HF_OIDC_RESOURCE"],"${{ vars.HF_TIMESTRAL_OPENVINO_REPO }}")
        steps=publish["steps"]
        self.assertTrue(any(s.get("uses","").startswith("actions/download-artifact@") and s.get("with",{}).get("name")=="timestral-openvino-validated" for s in steps))
        commands="\n".join(s.get("run","") for s in steps)
        self.assertIn("package.py --verify",commands)
        self.assertIn("publish.py --bundle",commands)
        self.assertNotIn("secrets.HF",path.read_text())

if __name__=="__main__":unittest.main()
