"""Real dynamic IR adapter tests; no checkpoints or performance claims."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest
import importlib.metadata
try:importlib.metadata.version('openvino')
except importlib.metadata.PackageNotFoundError:pytest.skip('requires native OpenVINO environment',allow_module_level=True)
import openvino as ov
from timestral.config import TimestralConfig


def module():
    path=Path(__file__).resolve().parents[1]/'backend.py'
    spec=importlib.util.spec_from_file_location('direct_backend_test',path)
    backend=importlib.util.module_from_spec(spec);spec.loader.exec_module(backend)
    return backend


def profiles(root,bad=None):
    from openvino import opset13 as ops
    levels=(.01,.05,.1,.15,.2,.25,.3,.35,.4,.45,.5,.55,.6,.65,.7,.75,.8,.85,.9,.95,.99)
    TimestralConfig(patch_size=32,d_model=16,num_heads=2,mlp_hidden_dim=32,
        block_schedule=('time_variate','time_variate'),quantile_knots=levels,
        block_size=32,context_length=1024).save(root/'config.json')
    for name in ('context','covariates'):
        types={'context':ov.Type.f32,'observed':ov.Type.boolean,'group_ids':ov.Type.i64,'known_future':ov.Type.f32,'loc':ov.Type.f32,'scale':ov.Type.f32}
        if name=='covariates':types.update(role_ids=ov.Type.i64)
        ports=[]
        for key,dtype in types.items():
            shape=[-1] if key in ('group_ids','role_ids') else [-1,-1]
            if bad=='fixed-shape' and key=='context':shape=[1,128]
            if bad=='input-type' and key=='observed':dtype=ov.Type.f32
            port=ops.parameter(shape,dtype,name=key)
            port.output(0).get_tensor().set_names({'wrong' if bad=='input-name' and key=='context' else key});ports.append(port)
        future=ports[list(types).index('known_future')]
        target=ops.concat([ops.shape_of(future,'i64'),ops.constant([20 if bad=='output-shape' else 21])],0)
        out=ops.broadcast(ops.constant(np.float16(0) if bad=='output-type' else np.float32(0)),target)
        if bad=='fixed-output':out=ops.constant(np.zeros((4,32,21),np.float32))
        out.output(0).get_tensor().set_names({'wrong' if bad=='output-name' else 'quantiles'})
        ov.save_model(ov.Model([out],ports),root/f'{name}.xml',compress_to_fp16=False)


@pytest.mark.parametrize('bad',['input-type','input-name','fixed-shape','output-shape','output-type','output-name','fixed-output'])
def test_bad_ir_contract_fails_before_ready(tmp_path,bad):
    profiles(tmp_path,bad)
    with pytest.raises(ValueError):module().OpenVINOBlocks(tmp_path)


def test_direct_dynamic_execution_without_pytorch_neural_parameters(tmp_path):
    import torch
    profiles(tmp_path);backend=module().OpenVINOBlocks(tmp_path)
    assert not isinstance(backend,torch.nn.Module) and not hasattr(backend,'parameters')
    for r,t,h in [(1,32,1),(4,288,7),(32,64,32)]:
        x=torch.ones(r,t);mask=torch.ones(r,t,dtype=torch.bool);groups=torch.arange(r)//2
        for roles in (None,torch.arange(r)%3):
            result=backend.predict_block(x,mask,groups,h,roles)
            assert result.shape==(r,h*32,21) and result.dtype==torch.float32
            assert torch.count_nonzero(result)==0


def test_openvino_forecaster_uses_cpu_defaults_and_explicit_profile(tmp_path):
    profiles(tmp_path)
    backend=module();forecaster=backend.create_forecaster(tmp_path)
    assert forecaster.max_context==1024 and forecaster.per_shot_horizon_patches==32
    bounded=backend.create_forecaster(tmp_path,forecast_profile='bounded-v1')
    assert bounded.max_context==256 and bounded.per_shot_horizon_patches==5
