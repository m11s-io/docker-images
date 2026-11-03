import importlib.util
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


class StandardPublishTest(unittest.TestCase):
    def module(self):
        spec=importlib.util.spec_from_file_location('standard_publish',ROOT/'publish.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_environment_only_authorizes_main_release_events(self):
        import os
        from unittest.mock import patch
        p=self.module()
        env=dict(GITHUB_ACTIONS='true',GITHUB_REF='refs/heads/main',
            GITHUB_REPOSITORY='m11s-io/docker-images',HF_OIDC_RESOURCE=p.DESTINATION)
        for event in ('push','workflow_dispatch'):
            with patch.dict(os.environ,dict(env,GITHUB_EVENT_NAME=event),clear=True):
                p.validate_environment()
        for key,value in [('GITHUB_EVENT_NAME','pull_request'),('GITHUB_REF','refs/heads/untrusted'),
                          ('GITHUB_REPOSITORY','fork/docker-images')]:
            with patch.dict(os.environ,dict(env,GITHUB_EVENT_NAME='push',**({key:value} if key!='GITHUB_EVENT_NAME' else {})),clear=True):
                os.environ[key]=value
                with self.assertRaises(ValueError):p.validate_environment()

    def test_allowlist_preserves_legacy_and_rejects_arbitrary_remote_files(self):
        p=self.module()
        good='standard-v2/'+'a'*64+'/profiles/context.bin'
        self.assertTrue(p.is_standard_file(good))
        self.assertTrue(p.is_standard_file('standard-v1/'+'a'*64+'/profiles/block-1.bin'))
        for bad in ('standard-v2/current/profiles/context.bin',
                    'standard-v2/'+'a'*64+'/profiles/token.txt',
                    'standard-v2/'+'a'*64+'/profiles/../secret'):
            self.assertFalse(p.is_standard_file(bad))
        p.validate_remote_inventory(['.gitattributes','model/1/model.bin',good])
        with self.assertRaises(ValueError):p.validate_remote_inventory(['secret.txt'])

    def test_protocol_evidence_requires_nonempty_all_passing_tests(self):
        import tempfile
        p=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'protocol.xml'
            for invalid in ('<testsuites/>','<testsuite tests="39" failures="1"/>','<testsuite tests="39" errors="1"/>','<testsuite tests="39" skipped="1"/>'):
                path.write_text(invalid)
                with self.assertRaises(ValueError):p.verify_protocol(path)
            path.write_text('<testsuites><testsuite tests="39" failures="0" errors="0" skipped="0"><properties><property name="forecast_rtol" value="0.0001"/><property name="forecast_atol" value="0.0001"/></properties></testsuite></testsuites>')
            p.verify_protocol(path)

    def test_model_specific_bundle_requires_exact_parity_and_run_provenance(self):
        import hashlib,json,tempfile,os
        from unittest.mock import patch
        sys.path.insert(0,str(ROOT.parents[1]))
        from serving.artifacts import PROFILE_FILES,MODEL_REVISIONS,SOURCE_REVISION
        p=self.module()
        for model_id,revision in MODEL_REVISIONS.items():
            with self.subTest(model=model_id),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);profiles=root/'profiles';evidence=root/'evidence'
                profiles.mkdir();evidence.mkdir()
                for name in PROFILE_FILES:(profiles/name).write_bytes(b'fixture')
                from profiles import cases,case_options
                keys={f'{name}-s{int(s)}-c{int(c)}' for name in cases() for s,c in case_options(name)}
                import numpy as np
                from serving.divergence import assess
                reference=np.ones((1,1,1024,21),np.float32)
                strict=assess(reference,reference,model_id=model_id,case='maximum-horizon')
                parity=dict(passed=True,cases={k:dict(strict) for k in keys},neural_backend='openvino',reference_weights_loaded_in_runtime_worker=False,github_run='42')
                if model_id!='mistralai/Timestral-209M':
                    actual=reference.copy()
                    actual.flat[0]+={'mistralai/Timestral-5M':.0003,
                        'mistralai/Timestral-28M':.002,'mistralai/Timestral-123M':.01}[model_id]
                    parity['cases']['maximum-horizon-s0-c0']=assess(actual,reference,model_id=model_id,case='maximum-horizon')
                (evidence/'parity.json').write_text(json.dumps(parity))
                manifest=dict(format='timestral-openvino-profiles-v2',model_id=model_id,model_revision=revision,source_revision=SOURCE_REVISION,precision='FP32',parity_report_sha256=p.digest(evidence/'parity.json'),files={name:p.digest(profiles/name) for name in PROFILE_FILES})
                (profiles/'manifest.json').write_text(json.dumps(manifest))
                expected=p.digest(profiles/'manifest.json')
                (evidence/'manifest-sha256.txt').write_text(expected)
                (evidence/'protocol-parity.xml').write_text(f'<testsuite tests="39" failures="0" errors="0" skipped="0"><properties><property name="forecast_rtol" value="0.0001"/><property name="forecast_atol" value="0.0001"/><property name="model_id" value="{model_id}"/><property name="model_revision" value="{revision}"/></properties></testsuite>')
                (evidence/'provenance.json').write_text(json.dumps(dict(source='a'*40,run='42')))
                with patch.dict(os.environ,dict(GITHUB_SHA='a'*40,GITHUB_RUN_ID='42')):
                    self.assertEqual(p.verify_bundle(root)[0],expected)
                    (evidence/'provenance.json').write_text('{}')
                    with self.assertRaises(ValueError):p.verify_bundle(root)

    def test_publish_preserves_legacy_and_checks_uploaded_parent_inventory_and_bytes(self):
        import contextlib,os,tempfile,types,json
        from unittest.mock import patch
        p=self.module()
        class API:
            def __init__(self):self.files={'.gitattributes':b'lfs','model/1/model.bin':b'legacy'};self.uploads=[]
            def model_info(self,repo):return types.SimpleNamespace(private=False,sha='parent')
            def list_repo_files(self,repo_id,revision):return list(self.files)
            def upload_folder(self,**kwargs):
                self.uploads.append(kwargs)
                for path in Path(kwargs['folder_path']).rglob('*'):
                    if path.is_file():self.files[kwargs['path_in_repo']+'/'+path.relative_to(kwargs['folder_path']).as_posix()]=path.read_bytes()
                return types.SimpleNamespace(oid='verified-commit')
        with tempfile.TemporaryDirectory() as tmp,contextlib.chdir(tmp):
            root=Path(tmp);bundle=root/'bundle'
            names={'profiles/manifest.json',*(f'evidence/{name}' for name in p.EVIDENCE)}
            for name in names:
                path=bundle/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps({'model_id':'mistralai/Timestral-5M','model_revision':'c'*40}) if name=='profiles/manifest.json' else name)
            api=API();downloads=[]
            def download(repo,filename,revision):
                self.assertEqual(revision,'verified-commit')
                downloads.append(filename);path=root/'remote'/filename
                path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(api.files[filename]);return str(path)
            sdk=types.SimpleNamespace(HfApi=lambda:api,hf_hub_download=download)
            env=dict(GITHUB_SHA='a'*40,GITHUB_RUN_ID='42',TIMESTRAL_RELEASE_IMAGE='m11s/timestral@sha256:'+'d'*64)
            with patch.object(p,'validate_environment'),patch.object(p,'verify_bundle',return_value=('b'*64,{'manifest.json'})),patch.dict(sys.modules,{'huggingface_hub':sdk}),patch.dict(os.environ,env,clear=True):
                result=p.publish(bundle)
                self.assertEqual(result['revision'],'verified-commit')
                self.assertEqual(result['image'],env['TIMESTRAL_RELEASE_IMAGE'])
                self.assertEqual(result['model_revision'],'c'*40)
                self.assertEqual(result['profiles_path'],'standard-v2/'+'b'*64+'/profiles')
                self.assertEqual(api.uploads[0]['parent_commit'],'parent')
                self.assertEqual(api.files['model/1/model.bin'],b'legacy')
                self.assertEqual(set(downloads),{'standard-v2/'+'b'*64+'/'+name for name in names})
                # A retry verifies an existing complete release without upload;
                # changing any published byte must never silently overwrite it.
                api.model_info=lambda repo:types.SimpleNamespace(private=False,sha='verified-commit')
                api.files['standard-v2/'+'b'*64+'/profiles/manifest.json']=b'corrupt'
                with self.assertRaisesRegex(ValueError,'checksum mismatch'):p.publish(bundle)
                self.assertEqual(len(api.uploads),1)
                api.files.pop('standard-v2/'+'b'*64+'/profiles/manifest.json')
                with self.assertRaisesRegex(ValueError,'incomplete'):p.publish(bundle)
                self.assertEqual(len(api.uploads),1)
                api.files['secret.txt']=b'never upload'
                with self.assertRaisesRegex(ValueError,'unexpected files'):p.publish(bundle)
                self.assertEqual(len(api.uploads),1)
