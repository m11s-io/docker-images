"""Untrusted artifact validation and explicit preview capability rejection."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from kserve.errors import InvalidInput
from serving.contract import ForecastInputs
from serving.artifacts import verify_profiles, validate_preview_request

REVISION='bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f'
SOURCE='a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff'


def bundle(tmp_path):
    files={'config.json':b'{}','LICENSE':b'Apache-2.0','README.md':b'Experimental preview'}
    for i in range(1,6):
        files[f'block-{i}.xml']=b'IR'
        files[f'block-{i}.bin']=b'weights'
    for name,content in files.items(): (tmp_path/name).write_bytes(content)
    manifest={'format':'timestral-openvino-profiles-v1','model_id':'mistralai/Timestral-5M',
              'model_revision':REVISION,'source_revision':SOURCE,'precision':'FP32',
              'max_context':256,'per_shot_horizon_patches':5,
              'files':{name:hashlib.sha256(content).hexdigest() for name,content in files.items()}}
    data=json.dumps(manifest,sort_keys=True).encode()
    (tmp_path/'manifest.json').write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def test_verified_bundle_has_exact_revision_and_profiles(tmp_path):
    digest=bundle(tmp_path)
    got=verify_profiles(tmp_path,digest,'mistralai/Timestral-5M',REVISION)
    assert got['per_shot_horizon_patches']==5


@pytest.mark.parametrize('bad',['checksum','manifest-digest','revision','model-size','extra','symlink','missing'])
def test_invalid_bundle_is_rejected_before_openvino_compilation(tmp_path,bad):
    digest=bundle(tmp_path)
    model_id='mistralai/Timestral-5M'; revision=REVISION
    if bad=='checksum': (tmp_path/'block-2.bin').write_bytes(b'corrupt')
    if bad=='manifest-digest': digest='0'*64
    if bad=='revision': revision='a'*40
    if bad=='model-size': model_id='mistralai/Timestral-209M'
    if bad=='extra': (tmp_path/'token').write_text('unexpected')
    if bad=='missing': (tmp_path/'block-3.xml').unlink()
    if bad=='symlink':
        (tmp_path/'config.json').unlink(); (tmp_path/'config.json').symlink_to(tmp_path/'block-1.xml')
    with pytest.raises(ValueError): verify_profiles(tmp_path,digest,model_id,revision)


@pytest.mark.parametrize('shape,horizon,cov', [((2,1,128),32,False),((1,2,128),32,False),
    ((1,1,257),32,False),((1,1,128),321,False),((1,1,128),32,True)])
def test_preview_rejects_unverified_features(shape,horizon,cov):
    inputs=ForecastInputs(np.ones(shape,dtype=np.float32),np.ones(shape,dtype=bool),horizon,
                          {'past_covariates':np.ones(shape,dtype=np.float32)} if cov else {})
    with pytest.raises(InvalidInput): validate_preview_request(inputs)


def test_openvino_load_verifies_artifacts_without_loading_reference_weights(monkeypatch,tmp_path):
    from serving.upstream import Settings, UpstreamForecaster
    from timestral import TimestralForecaster
    def forbid(*args,**kwargs): raise AssertionError('reference neural weights were loaded')
    monkeypatch.setattr(TimestralForecaster,'from_pretrained',forbid)
    monkeypatch.setenv('TIMESTRAL_FORECAST_ARTIFACTS',str(tmp_path))
    monkeypatch.setenv('TIMESTRAL_ARTIFACT_MANIFEST_SHA256','0'*64)
    with pytest.raises(ValueError,match='profile'):
        UpstreamForecaster.load(Settings(model_revision=REVISION,model_id='mistralai/Timestral-5M',backend='openvino'))
