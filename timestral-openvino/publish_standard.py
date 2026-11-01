"""Append a validated standard-v1 profile release; preserve legacy HF contents."""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import xml.etree.ElementTree as ET

from package import digest,inventory
from publish import DESTINATION,validate_environment
from publication_inventory import is_standard_file,validate_remote_inventory

EVIDENCE={'parity.json','protocol-parity.xml','provenance.json','manifest-sha256.txt'}


def verify_protocol(path):
    root=ET.parse(path).getroot()
    suites=[root] if root.tag=='testsuite' else list(root.findall('testsuite'))
    if not suites or sum(int(s.get('tests','0')) for s in suites)<38:
        raise ValueError('complete actual-image protocol evidence is required')
    if any(int(s.get(key,'0')) for s in suites for key in ('failures','errors','skipped')):
        raise ValueError('protocol evidence must pass without skipped tests')


def verify_bundle(bundle):
    from serving.artifacts import PROFILE_FILES,MODEL_REVISIONS,verify_profiles
    if bundle.is_symlink() or not bundle.is_dir() or (bundle/'evidence').is_symlink():
        raise ValueError('publication requires a real bundle directory')
    manifest_sha=(bundle/'evidence/manifest-sha256.txt').read_text().strip()
    identity=json.loads((bundle/'profiles/manifest.json').read_text())
    model_id=identity.get('model_id')
    manifest=verify_profiles(bundle/'profiles',manifest_sha,model_id,MODEL_REVISIONS.get(model_id))
    parity_path=bundle/'evidence/parity.json'
    parity=json.loads(parity_path.read_text())
    expected_cases={f'{name}-s{symmetric}-c{clip}'
        for name in ('short','fixed','nonaligned','long-context','five-patches','four-patches',
                     'maximum-horizon','missing','multi-block','nonnegative')
        for symmetric in (0,1) for clip in (0,1)}
    if (digest(parity_path)!=manifest['parity_report_sha256'] or
        parity.get('passed') is not True or set(parity.get('cases',{}))!=expected_cases or
        parity.get('neural_backend')!='openvino' or
        parity.get('reference_weights_loaded_in_runtime_worker') is not False or
        str(parity.get('github_run'))!=os.environ['GITHUB_RUN_ID']):
        raise ValueError('complete same-run OpenVINO parity evidence is required')
    for case in parity['cases'].values():
        if (case.get('rtol')!=1e-4 or case.get('atol')!=1e-4 or
            not isinstance(case.get('max_absolute_error'),(int,float)) or
            not math.isfinite(case['max_absolute_error']) or case['max_absolute_error']<0):
            raise ValueError('unexpected profile parity tolerance')
    verify_protocol(bundle/'evidence/protocol-parity.xml')
    provenance=json.loads((bundle/'evidence/provenance.json').read_text())
    if provenance!={'source':os.environ['GITHUB_SHA'],'run':os.environ['GITHUB_RUN_ID']}:
        raise ValueError('publication provenance does not match this run')
    return manifest_sha,PROFILE_FILES|{'manifest.json'}


def publish(bundle):
    validate_environment()
    manifest_sha,profile_files=verify_bundle(bundle)
    from huggingface_hub import HfApi,hf_hub_download
    api=HfApi();info=api.model_info(DESTINATION)
    if not info.private: raise ValueError('experimental repository must remain private')
    before=set(api.list_repo_files(DESTINATION,revision=info.sha))
    validate_remote_inventory(before)
    prefix='standard-v1/'+manifest_sha
    names={*(f'profiles/{name}' for name in profile_files),*(f'evidence/{name}' for name in EVIDENCE)}
    expected={prefix+'/'+name for name in names}
    existing={name for name in before if name.startswith(prefix+'/')}
    if existing and existing!=expected:
        raise ValueError('content-addressed release is incomplete; refusing overwrite')
    if existing:
        revision=info.sha
    else:
        with tempfile.TemporaryDirectory() as directory:
            release=Path(directory)
            for name in names:
                target=release/name;target.parent.mkdir(parents=True,exist_ok=True)
                source=bundle/name
                if source.is_symlink() or not source.is_file():raise ValueError('publication requires regular files')
                shutil.copyfile(source,target)
            if inventory(release)!=names:raise ValueError('unexpected staged release files')
            result=api.upload_folder(repo_id=DESTINATION,folder_path=str(release),path_in_repo=prefix,
                allow_patterns=sorted(names),parent_commit=info.sha,
                commit_message='Validated standard-v1 preview '+os.environ['GITHUB_SHA'][:12])
            revision=result.oid
    after=set(api.list_repo_files(DESTINATION,revision=revision))
    if after!=before|expected:raise ValueError('unexpected remote release inventory')
    for name in names:
        remote=Path(hf_hub_download(DESTINATION,filename=prefix+'/'+name,revision=revision))
        if digest(remote)!=digest(bundle/name):raise ValueError('remote release checksum mismatch: '+name)
    receipt=dict(repository=DESTINATION,revision=revision,path=prefix,manifest_sha256=manifest_sha,
                 source=os.environ['GITHUB_SHA'],run=os.environ['GITHUB_RUN_ID'],status='experimental-preview')
    print(json.dumps(receipt,indent=2))
    Path('standard-publication.json').write_text(json.dumps(receipt,indent=2)+'\n')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write('```json\n'+json.dumps(receipt,indent=2)+'\n```\n')
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True)
    publish(p.parse_args().bundle)
