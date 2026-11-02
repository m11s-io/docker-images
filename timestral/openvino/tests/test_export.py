"""Preserved export safeguards; no checkpoint downloads in unit tests."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]/'export'


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/f'{name}.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_guarded_rewrites_leave_reference_source_untouched(tmp_path):
    rewrites=load('rewrites')
    source=tmp_path/'original'; destination=tmp_path/'patched'
    (source/'src/timestral').mkdir(parents=True)
    scaler='means.unfold(-1, patch_size, patch_size)\nscales.unfold(-1, patch_size, patch_size)\n'
    masks='started = obs_per_patch.cummax(dim=-1).values\n'
    (source/'src/timestral/scaler.py').write_text(scaler)
    (source/'src/timestral/masks.py').write_text(masks)
    rewrites.patch_source(source,destination)
    assert (source/'src/timestral/scaler.py').read_text()==scaler
    assert (source/'src/timestral/masks.py').read_text()==masks
    assert '.unfold(' not in (destination/'src/timestral/scaler.py').read_text()
    assert 'cumsum' in (destination/'src/timestral/masks.py').read_text()


def test_source_drift_fails_without_a_partial_copy(tmp_path):
    rewrites=load('rewrites')
    source=tmp_path/'original'; destination=tmp_path/'patched'
    (source/'src/timestral').mkdir(parents=True)
    (source/'src/timestral/scaler.py').write_text('upstream changed')
    with pytest.raises(ValueError,match='source drift'): rewrites.patch_source(source,destination)
    assert not destination.exists()


def test_final_forecast_gate_rejects_bad_shape_dtype_finiteness_and_parity():
    exporter=load('profiles')
    expected=np.ones((1,1,65,21),dtype=np.float32)
    assert exporter.validate_outputs(expected,expected,65)['max_absolute_error']==0
    for actual in [expected[...,0],expected.astype(np.float16),expected*np.nan,expected+.1]:
        with pytest.raises((ValueError,AssertionError)): exporter.validate_outputs(expected,actual,65)


@pytest.mark.parametrize('covariates',[False,True])
def test_dynamic_block_preserves_shapes_groups_roles_and_future(covariates):
    import torch
    import openvino as ov
    from timestral.config import TimestralConfig
    from timestral.model import TimestralModel
    torch.manual_seed(173)
    torch.set_num_threads(2)
    config=TimestralConfig(patch_size=32,d_model=16,num_heads=2,mlp_hidden_dim=32,
        block_schedule=('time_variate','time_variate'),block_size=32,context_length=1024,
        quantile_knots=(.01,.05,.1,.15,.2,.25,.3,.35,.4,.45,.5,.55,.6,.65,.7,.75,.8,.85,.9,.95,.99))
    model=TimestralModel(config).eval()
    graph=load('profiles').convert_block(model,covariates=covariates)
    compiled=ov.Core().compile_model(graph,'CPU',{'INFERENCE_PRECISION_HINT':'f32','INFERENCE_NUM_THREADS':2})
    for rows,length,h in [(4,64,2),(6,288,7),(4,96,1),(1,32,32),(32,64,3)]:
        context=torch.randn(rows,length)
        observed=torch.rand(rows,length)>.2
        observed[0,:32]=False
        groups=(torch.arange(rows)//2)*3+7
        future=torch.randn(rows,h*32)
        values=dict(context=context.numpy(),observed=observed.numpy(),group_ids=groups.numpy(),
                    known_future=future.numpy())
        kwargs={}
        if covariates:
            roles=torch.tensor(([0,1,2]*((rows+2)//3))[:rows])
            if rows==32:roles[roles==2]=1
            future_mask=torch.rand(rows,h*32)>.3
            kwargs=dict(role_ids=roles,known_future=future,known_future_mask=future_mask)
            values.update(role_ids=roles.numpy(),known_future_mask=future_mask.numpy())
        with torch.inference_mode():
            expected=model.predict_block(context,observed,groups,h,**kwargs).numpy()
        actual=compiled(values)[compiled.output(0)]
        assert actual.shape==(rows,h*32,21)
        np.testing.assert_allclose(actual,expected,rtol=1e-4,atol=1e-4)
