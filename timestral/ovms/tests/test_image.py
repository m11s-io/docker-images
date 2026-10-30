from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
class ImageTest(unittest.TestCase):
    def test_runtime_is_ovms_with_pinned_source_and_no_custom_api(self):
        p=ROOT.parent/'Dockerfile.ovms'
        self.assertTrue(p.exists(),'derived OVMS Dockerfile missing')
        s=p.read_text()
        self.assertIn('openvino/model_server:2026.4.1@sha256:148e3fe802261ed0b5b634de3bbccdefe7176a218ec34a88e382b40704c34a1c',s)
        self.assertIn('uv sync --frozen',s)
        self.assertIn('USER 5000:5000',s)
        self.assertNotIn('uvicorn',s)
        self.assertIn('fetch_source.py',s)
        self.assertIn('ENTRYPOINT ["/ovms/bin/ovms"]',s)
        self.assertNotIn('model.safetensors',s)

    def test_ovms_context_is_explicit_and_exporter_is_colocated(self):
        ignore=ROOT.parent/'.dockerignore'
        self.assertTrue(ignore.exists(),'shared Timestral context ignore missing')
        self.assertFalse((ROOT.parent/'Dockerfile.ovms.dockerignore').exists())
        patterns=ignore.read_text().splitlines()
        for path in ['!ovms/pyproject.toml','!ovms/uv.lock','!ovms/fetch_source.py','!ovms/adapter/**']:
            self.assertIn(path,patterns)
        self.assertTrue((ROOT/'export/export.py').exists(),'exporter belongs beside the OVMS adapter')
        self.assertFalse((ROOT.parents[1]/'timestral-openvino').exists(),'duplicate top-level Timestral project')

    def test_ci_routes_ovms_changes_without_rebuilding_api_variants(self):
        import yaml
        repo=ROOT.parents[1]
        workflow=yaml.safe_load((repo/'.github/workflows/build.yaml').read_text())
        filters=next(s['with']['filters'] for s in workflow['jobs']['changes']['steps'] if s.get('id')=='filter')
        paths=yaml.safe_load(filters)
        for variant in ['timestral-cpu','timestral-cuda']:
            for excluded in ['!timestral/ovms/**','!timestral/Dockerfile.ovms']:
                self.assertIn(excluded,paths[variant])

    def test_shared_context_changes_trigger_actual_image_validation(self):
        import yaml
        workflow=yaml.safe_load((ROOT.parents[1]/'.github/workflows/timestral-ovms.yaml').read_text())
        triggers=workflow.get('on',workflow.get(True))
        self.assertIn('timestral/.dockerignore',triggers['pull_request']['paths'])

if __name__=='__main__':unittest.main()
