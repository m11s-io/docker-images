"""Named comparison profiles preserve upstream defaults and artifact bounds."""
from types import SimpleNamespace
import pytest
from serving.upstream import Settings, UpstreamForecaster

REVISION='bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f'


def test_default_resolution_matches_cpu_for_openvino():
    assert Settings(model_revision=REVISION).resolved_profile=='upstream-default'
    assert Settings(model_revision=REVISION,backend='openvino').resolved_profile=='upstream-default'
    assert Settings(model_revision=REVISION,backend='openvino',forecast_profile='upstream-default').resolved_profile=='upstream-default'
    with pytest.raises(ValueError):Settings(model_revision=REVISION,forecast_profile='custom')


@pytest.mark.parametrize('profile,expected', [('default',{}),('upstream-default',{}),
    ('bounded-v1',{'max_context':256,'per_shot_horizon_patches':5})])
def test_explicit_preset_only_changes_selected_upstream_constructor_options(monkeypatch,tmp_path,profile,expected):
    import torch
    from timestral import TimestralForecaster
    calls=[]
    def load(*args,**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(model=torch.nn.Linear(1,1,dtype=torch.float32))
    monkeypatch.setattr(TimestralForecaster,'from_pretrained',load)
    UpstreamForecaster.load(Settings(model_id='mistralai/Timestral-5M',model_revision=REVISION,
        hf_home=str(tmp_path),forecast_profile=profile))
    assert {k:v for k,v in calls[0].items() if k in ('max_context','per_shot_horizon_patches')}==expected


def test_environment_selects_named_profile_explicitly(monkeypatch):
    monkeypatch.setenv('MODEL_REVISION',REVISION)
    monkeypatch.setenv('TIMESTRAL_FORECAST_PROFILE','bounded-v1')
    assert Settings.from_env().resolved_profile=='bounded-v1'
