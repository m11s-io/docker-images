"""The serving adapter preserves normal upstream constructor defaults."""
from types import SimpleNamespace
from serving.upstream import Settings, UpstreamForecaster

REVISION='bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f'


def test_backend_keeps_upstream_constructor_defaults(monkeypatch,tmp_path):
    import torch
    from timestral import TimestralForecaster
    calls=[]
    def load(*args,**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(model=torch.nn.Linear(1,1,dtype=torch.float32))
    monkeypatch.setattr(TimestralForecaster,'from_pretrained',load)
    UpstreamForecaster.load(Settings(model_id='mistralai/Timestral-5M',model_revision=REVISION,
        hf_home=str(tmp_path)))
    assert {k:v for k,v in calls[0].items() if k in ('max_context','per_shot_horizon_patches')}=={}
