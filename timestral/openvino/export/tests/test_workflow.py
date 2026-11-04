"""Guard automatic release wiring, publication authorization and same-run evidence."""
from pathlib import Path
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[4]

class WorkflowTest(unittest.TestCase):
    def test_publication_requires_main_release_and_successful_validation(self):
        text=(ROOT/'.github/workflows/timestral-openvino.yaml').read_text()
        workflow=yaml.safe_load(text)
        triggers=workflow.get('on',workflow.get(True))
        self.assertIn('workflow_dispatch',triggers)
        self.assertIn('workflow_call',triggers)
        jobs=workflow['jobs'];publish=jobs['publish']
        self.assertEqual(publish['needs'],['validate'])
        self.assertIn("github.ref == 'refs/heads/main'",publish['if'])
        self.assertIn("needs.validate.result == 'success'",publish['if'])
        self.assertIn("inputs.reuse-validation && needs.validate.result == 'skipped'",publish['if'])
        self.assertEqual(publish['permissions'],{'contents':'read','id-token':'write'})
        self.assertEqual(workflow['permissions'],{'contents':'read'})
        self.assertNotIn('id-token',jobs['validate'].get('permissions',{}))
        self.assertEqual(jobs['validate']['uses'],'./.github/workflows/timestral-standard.yaml')
        self.assertFalse(publish['strategy']['fail-fast'])
        self.assertEqual(publish['strategy']['max-parallel'],1)
        self.assertFalse(workflow['concurrency']['cancel-in-progress'])
        self.assertEqual(publish['env']['HF_OIDC_RESOURCE'],'${{ vars.HF_TIMESTRAL_OPENVINO_REPO }}')
        steps=publish['steps']
        download=next(s for s in steps if s.get('uses','').startswith('actions/download-artifact@'))
        self.assertEqual(download['with']['name'],'timestral-openvino-preview-${{ matrix.model }}-${{ github.sha }}')
        commands='\n'.join(s.get('run','') for s in steps)
        self.assertIn('sha-${GITHUB_SHA:0:12}-openvino',commands)
        self.assertIn('TIMESTRAL_RELEASE_IMAGE=m11s/timestral@$digest',commands)
        self.assertIn('timestral/openvino/export/publish.py --bundle',commands)
        self.assertNotIn('secrets.HF',text)

    def test_automatic_release_requires_pushed_image_and_same_run_validation(self):
        workflow=yaml.safe_load((ROOT/'.github/workflows/build.yaml').read_text())
        job=workflow['jobs']['publish-timestral-profiles']
        self.assertEqual(job['uses'],'./.github/workflows/timestral-openvino.yaml')
        self.assertEqual(job['needs'],['changes','timestral-tests','build'])
        self.assertTrue(job['with']['reuse-validation'])
        for condition in ("github.ref == 'refs/heads/main'", "github.event_name == 'push'",
                          "github.event.inputs.skip_push != 'true'", "needs.build.result == 'success'",
                          "needs.timestral-tests.result == 'success'", "needs.changes.outputs.timestral-openvino == 'true'"):
            self.assertIn(condition,job['if'])
        triggers=workflow.get('on',workflow.get(True))
        self.assertIn('.github/workflows/timestral-openvino.yaml',triggers['push']['paths'])

if __name__=='__main__':unittest.main()

class ReleaseReceiptTest(unittest.TestCase):
    def test_combined_release_rejects_missing_or_mismatched_receipts(self):
        import json,os,subprocess,sys,tempfile
        workflow=yaml.safe_load((ROOT/'.github/workflows/timestral-openvino.yaml').read_text())
        release=workflow['jobs']['release']
        self.assertEqual(release['needs'],['publish'])
        command=next(s['run'] for s in release['steps'] if s.get('name')=='Collect immutable deployment references')
        code=command.split("<<'PYTHON'\n",1)[1].rsplit('\nPYTHON',1)[0]
        records=[dict(model_id='mistralai/Timestral-'+size,source='a'*40,run='42',
                      image='m11s/timestral@sha256:'+'b'*64,revision='c'*40,
                      profiles_path='standard-v2/'+'d'*64+'/profiles',manifest_sha256='d'*64)
                 for size in ('5M','28M','123M','209M')]
        for invalid in (None,'missing','source','image','duplicate'):
            with self.subTest(invalid=invalid),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                current=[dict(r) for r in records]
                if invalid=='missing':current.pop()
                if invalid=='source':current[0]['source']='e'*40
                if invalid=='image':current[0]['image']='m11s/timestral@sha256:'+'e'*64
                if invalid=='duplicate':current[0]['model_id']=current[1]['model_id']
                for index,record in enumerate(current):
                    p=root/'receipts'/str(index)/'standard-publication.json'
                    p.parent.mkdir(parents=True);p.write_text(json.dumps(record))
                result=subprocess.run([sys.executable,'-c',code],cwd=root,
                    env=dict(os.environ,GITHUB_SHA='a'*40,GITHUB_RUN_ID='42',GITHUB_STEP_SUMMARY=str(root/'summary')),
                    capture_output=True,text=True)
                self.assertEqual(result.returncode==0,invalid is None,result.stderr)
                if invalid is None:
                    receipt=json.loads((root/'timestral-openvino-release.json').read_text())
                    self.assertEqual(len(receipt['models']),4)
                    self.assertEqual(receipt['models']['mistralai/Timestral-209M']['manifest_sha256'],'d'*64)
