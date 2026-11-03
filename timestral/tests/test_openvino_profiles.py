"""Untrusted artifact validation and explicit preview capability rejection."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from kserve.errors import InvalidInput
from serving.contract import ForecastInputs
from serving.artifacts import verify_profiles

REVISION='bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f'
SOURCE='a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff'


def bundle(tmp_path):
    files={'config.json':b'{}','LICENSE':b'Apache-2.0','README.md':b'Timestral OpenVINO profiles'}
    for i in ('context','covariates'):
        files[f'{i}.xml']=b'IR'
        files[f'{i}.bin']=b'weights'
    for name,content in files.items(): (tmp_path/name).write_bytes(content)
    manifest={'format':'timestral-openvino-profiles-v2','model_id':'mistralai/Timestral-5M',
              'model_revision':REVISION,'source_revision':SOURCE,'precision':'FP32',
              'files':{name:hashlib.sha256(content).hexdigest() for name,content in files.items()}}
    data=json.dumps(manifest,sort_keys=True).encode()
    (tmp_path/'manifest.json').write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def test_verified_bundle_has_exact_revision_and_profiles(tmp_path):
    digest=bundle(tmp_path)
    got=verify_profiles(tmp_path,digest,'mistralai/Timestral-5M',REVISION)
    assert got['format']=='timestral-openvino-profiles-v2'


@pytest.mark.parametrize('bad',['checksum','manifest-digest','revision','model-size','extra','symlink','missing'])
def test_invalid_bundle_is_rejected_before_openvino_compilation(tmp_path,bad):
    digest=bundle(tmp_path)
    model_id='mistralai/Timestral-5M'; revision=REVISION
    if bad=='checksum': (tmp_path/'context.bin').write_bytes(b'corrupt')
    if bad=='manifest-digest': digest='0'*64
    if bad=='revision': revision='a'*40
    if bad=='model-size': model_id='mistralai/Timestral-209M'
    if bad=='extra': (tmp_path/'token').write_text('unexpected')
    if bad=='missing': (tmp_path/'covariates.xml').unlink()
    if bad=='symlink':
        (tmp_path/'config.json').unlink(); (tmp_path/'config.json').symlink_to(tmp_path/'block-1.xml')
    with pytest.raises(ValueError): verify_profiles(tmp_path,digest,model_id,revision)


def test_old_bounded_bundle_cannot_claim_full_capability(tmp_path):
    bundle(tmp_path)
    manifest=json.loads((tmp_path/'manifest.json').read_text())
    manifest['format']='timestral-openvino-profiles-v1'
    raw=json.dumps(manifest).encode();(tmp_path/'manifest.json').write_bytes(raw)
    with pytest.raises(ValueError):verify_profiles(tmp_path,hashlib.sha256(raw).hexdigest(),'mistralai/Timestral-5M',REVISION)


def test_openvino_load_verifies_artifacts_without_loading_reference_weights(monkeypatch,tmp_path):
    from serving.upstream import Settings, UpstreamForecaster
    from timestral import TimestralForecaster
    def forbid(*args,**kwargs): raise AssertionError('reference neural weights were loaded')
    monkeypatch.setattr(TimestralForecaster,'from_pretrained',forbid)
    monkeypatch.setenv('TIMESTRAL_FORECAST_ARTIFACTS',str(tmp_path))
    monkeypatch.setenv('TIMESTRAL_ARTIFACT_MANIFEST_SHA256','0'*64)
    with pytest.raises(ValueError,match='profile'):
        UpstreamForecaster.load(Settings(model_revision=REVISION,model_id='mistralai/Timestral-5M',backend='openvino'))


@pytest.mark.parametrize('model_id,revision',[
    ('mistralai/Timestral-5M',REVISION),
    ('mistralai/Timestral-209M','9874d252ab0aae16f7f7c999f98f98d6ad7d8365'),
])
def test_model_specific_profile_bundle_requires_matching_pinned_identity(tmp_path,model_id,revision):
    bundle(tmp_path)
    manifest=json.loads((tmp_path/'manifest.json').read_text())
    manifest.update(model_id=model_id,model_revision=revision)
    raw=json.dumps(manifest,sort_keys=True).encode()
    (tmp_path/'manifest.json').write_bytes(raw)
    digest=hashlib.sha256(raw).hexdigest()
    got=verify_profiles(tmp_path,digest,model_id,revision)
    assert got['model_id']==model_id
    other='mistralai/Timestral-209M' if model_id.endswith('-5M') else 'mistralai/Timestral-5M'
    with pytest.raises(ValueError):verify_profiles(tmp_path,digest,other,revision)
