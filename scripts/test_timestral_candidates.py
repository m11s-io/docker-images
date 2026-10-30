"""Guard the explicit, temporary hardware-acceptance publication boundary."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CandidatePublicationTest(unittest.TestCase):
    def test_publication_requires_manual_main_dispatch_and_unique_tags(self):
        workflow = (ROOT / '.github/workflows/timestral-candidates.yaml').read_text()
        self.assertIn('workflow_dispatch:', workflow)
        self.assertNotIn('pull_request:', workflow)
        self.assertNotIn('\n  push:', workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn('acceptance-${{ github.sha }}-${{ github.run_id }}-${{ github.run_attempt }}-${{ matrix.variant }}', workflow)
        self.assertNotIn('latest', workflow)
        self.assertNotIn('id-token: write', workflow)
        self.assertIn('provenance: mode=max', workflow)
        self.assertIn('steps.build.outputs.digest', workflow)
        self.assertIn('variant: [cpu, cuda, rocm]', workflow)
        self.assertIn('python -m unittest discover -s scripts', workflow)
