import importlib.util
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


class StandardPublishTest(unittest.TestCase):
    def module(self):
        spec=importlib.util.spec_from_file_location('standard_publish',ROOT/'publish_standard.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_allowlist_preserves_legacy_and_rejects_arbitrary_remote_files(self):
        p=self.module()
        good='standard-v1/'+'a'*64+'/profiles/block-1.bin'
        self.assertTrue(p.is_standard_file(good))
        for bad in ('standard-v1/current/profiles/block-1.bin',
                    'standard-v1/'+'a'*64+'/profiles/token.txt',
                    'standard-v1/'+'a'*64+'/profiles/../secret'):
            self.assertFalse(p.is_standard_file(bad))
        p.validate_remote_inventory(['.gitattributes','model/1/model.bin',good])
        with self.assertRaises(ValueError):p.validate_remote_inventory(['secret.txt'])

    def test_protocol_evidence_requires_nonempty_all_passing_tests(self):
        import tempfile
        p=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'protocol.xml'
            for invalid in ('<testsuites/>','<testsuite tests="38" failures="1"/>','<testsuite tests="38" errors="1"/>','<testsuite tests="38" skipped="1"/>'):
                path.write_text(invalid)
                with self.assertRaises(ValueError):p.verify_protocol(path)
            path.write_text('<testsuites><testsuite tests="38" failures="0" errors="0" skipped="0"/></testsuites>')
            p.verify_protocol(path)

    def test_model_specific_bundle_requires_exact_parity_and_run_provenance(self):
        import hashlib,json,tempfile,os
        from unittest.mock import patch
        sys.path.insert(0,str(ROOT.parent/'timestral'))
        from serving.artifacts import PROFILE_FILES,MODEL_REVISIONS,SOURCE_REVISION
        p=self.module()
        for model_id,revision in MODEL_REVISIONS.items():
            with self.subTest(model=model_id),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);profiles=root/'profiles';evidence=root/'evidence'
                profiles.mkdir();evidence.mkdir()
                for name in PROFILE_FILES:(profiles/name).write_bytes(b'fixture')
                keys={f'{name}-s{s}-c{c}' for name in ('short','fixed','nonaligned','long-context','five-patches','four-patches','maximum-horizon','missing','multi-block','nonnegative') for s in (0,1) for c in (0,1)}
                parity=dict(passed=True,cases={k:dict(rtol=1e-4,atol=1e-4,max_absolute_error=0) for k in keys},neural_backend='openvino',reference_weights_loaded_in_runtime_worker=False,github_run='42')
                (evidence/'parity.json').write_text(json.dumps(parity))
                manifest=dict(format='timestral-openvino-profiles-v1',model_id=model_id,model_revision=revision,source_revision=SOURCE_REVISION,precision='FP32',max_context=256,per_shot_horizon_patches=5,parity_report_sha256=p.digest(evidence/'parity.json'),files={name:p.digest(profiles/name) for name in PROFILE_FILES})
                (profiles/'manifest.json').write_text(json.dumps(manifest))
                expected=p.digest(profiles/'manifest.json')
                (evidence/'manifest-sha256.txt').write_text(expected)
                (evidence/'protocol-parity.xml').write_text('<testsuite tests="38" failures="0" errors="0" skipped="0"/>')
                (evidence/'provenance.json').write_text(json.dumps(dict(source='a'*40,run='42')))
                with patch.dict(os.environ,dict(GITHUB_SHA='a'*40,GITHUB_RUN_ID='42')):
                    self.assertEqual(p.verify_bundle(root)[0],expected)
                    (evidence/'provenance.json').write_text('{}')
                    with self.assertRaises(ValueError):p.verify_bundle(root)
