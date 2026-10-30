"""Packaging boundary checks; actual inference and device acceptance run in CI."""
import pathlib
import re
import tomllib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class StandardImageTest(unittest.TestCase):
    def test_all_baseline_variants_use_same_official_entrypoint_and_source(self):
        for variant in ('cpu','cuda','rocm'):
            with self.subTest(variant=variant):
                content = (ROOT/f'timestral/Dockerfile.{variant}').read_text()
                self.assertIn('COPY serving/ ./serving/',content)
                self.assertIn('"-m", "serving"',content)
                self.assertIn('USER 10001:10001',content)
                self.assertIn('uv sync --frozen --no-dev',content)
                self.assertNotIn('uvicorn", "app.',content)
                self.assertNotIn('COPY app',content)
                self.assertNotIn('HF_TOKEN=',content)
                self.assertNotIn('from_pretrained(',content)
                self.assertRegex(content,r'python:3\.12\.\d+-slim-bookworm@sha256:[0-9a-f]{64}')
                self.assertIn(f'TIMESTRAL_BACKEND={variant}',content)

    def test_locks_bind_framework_to_correct_vendor_index(self):
        for variant,suffix in [('cpu','cpu'),('cuda','cu130'),('rocm','rocm7.2')]:
            with self.subTest(variant=variant):
                root = ROOT/f'timestral/dependencies/{variant}'
                project=tomllib.loads((root/'pyproject.toml').read_text())
                lock=tomllib.loads((root/'uv.lock').read_text())
                torch=next(p for p in lock['package'] if p['name']=='torch')
                self.assertEqual(torch['version'],f'2.14.1+{suffix}')
                self.assertEqual(torch['source']['registry'],f'https://download.pytorch.org/whl/{suffix}')
                kserve=next(p for p in lock['package'] if p['name']=='kserve')
                self.assertIn('abc6c47ab4af588e40c67372b4835122234f6f74', kserve['source']['git'])
                self.assertEqual(project['project']['requires-python'],'>=3.12,<3.13')
                self.assertNotIn('override-dependencies',project['tool']['uv'])

if __name__ == '__main__': unittest.main()


class VariantRoutingTest(unittest.TestCase):
    def selected(self,path):
        import fnmatch
        text=(ROOT/'.github/workflows/build.yaml').read_text()
        section=text.split('            timestral-cpu:\n',1)[1].split('\n  # Preserve legacy',1)[0]
        section='            timestral-cpu:\n'+section
        selected=set()
        for variant in ('cpu','cuda','rocm','openvino'):
            match=re.search(rf'^            timestral-{variant}:\n((?:              .*\n)*)',section,re.MULTILINE)
            self.assertIsNotNone(match)
            patterns=re.findall(r"- '([^']+)'",match.group(1))
            if any(fnmatch.fnmatchcase(path,pattern) for pattern in patterns): selected.add(variant)
        return selected

    def test_shared_contract_context_and_fixtures_validate_every_consumer(self):
        for path in ('timestral/serving/contract.py','timestral/.dockerignore','timestral/tests/fixtures/forecast-v1.json'):
            with self.subTest(path=path): self.assertEqual(self.selected(path),{'cpu','cuda','rocm','openvino'})

    def test_backend_locks_dockerfiles_and_export_profiles_select_their_consumer(self):
        for path,expected in [('timestral/openvino/backend.py','openvino'),
                              ('timestral/openvino/export/profiles.json','openvino'),
                              ('timestral/dependencies/cpu/uv.lock','cpu'),
                              ('timestral/Dockerfile.cuda','cuda'),
                              ('timestral/dependencies/rocm/pyproject.toml','rocm')]:
            with self.subTest(path=path): self.assertEqual(self.selected(path),{expected})
