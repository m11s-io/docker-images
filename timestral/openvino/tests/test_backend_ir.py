"""Real tiny IR tests; no Timestral weights, exports or performance claims."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest

import importlib.metadata
try:
    importlib.metadata.version('openvino')
except importlib.metadata.PackageNotFoundError:
    pytest.skip('requires installed vendor OpenVINO package',allow_module_level=True)
import openvino as ov
from timestral.config import TimestralConfig


def module():
    path=Path(__file__).resolve().parents[1]/'backend.py'
    spec=importlib.util.spec_from_file_location('direct_backend_test',path)
    backend=importlib.util.module_from_spec(spec); spec.loader.exec_module(backend)
    return backend


def profiles(root,bad=None,dynamic=False):
    levels=(.01,.05,.1,.15,.2,.25,.3,.35,.4,.45,.5,.55,.6,.65,.7,.75,.8,.85,.9,.95,.99)
    TimestralConfig(patch_size=32,d_model=16,num_heads=2,mlp_hidden_dim=32,
                    block_schedule=('time',),quantile_knots=levels,block_size=5,context_length=256).save(root/'config.json')
    from openvino import opset13 as ops
    for h in range(1,6):
        shape=ov.PartialShape([1,ov.Dimension(32,256)])
        context=ops.parameter(shape,ov.Type.f32,name='context')
        observed=ops.parameter(shape,ov.Type.f32 if bad=='input-type' else ov.Type.boolean,name='observed')
        context.output(0).get_tensor().set_names({'wrong' if bad=='input-name' else 'context'})
        observed.output(0).get_tensor().set_names({'observed'})
        out=ops.constant(np.zeros((1,h*32,20 if bad=='output-shape' else 21),dtype=np.float16 if bad=='output-type' else np.float32))
        if dynamic:
            # All admitted lengths are multiples of 32, so this is exactly 21
            # at runtime while shape inference retains a symbolic dimension.
            length=ops.gather(ops.shape_of(context,'i64'),ops.constant([1]),ops.constant(0))
            if bad=='dynamic-output':
                first=ops.gather(ops.reshape(context,ops.constant([-1]),False),ops.constant([0]),ops.constant(0))
                width=ops.add(ops.convert(ops.absolute(first),'i64'),ops.constant([20]))
            else:
                width=ops.add(ops.floor_mod(length,ops.constant([32])),ops.constant([21]))
            target=ops.concat([ops.constant([1,h*32]),width],0)
            out=ops.broadcast(ops.constant(np.float32(0)),target)
        out.output(0).get_tensor().set_names({'wrong' if bad=='output-name' else 'quantiles'})
        model=ov.Model([out],[context,observed])
        ov.save_model(model,root/f'block-{h}.xml',compress_to_fp16=False)


@pytest.mark.parametrize('bad',['input-type','input-name','output-shape','output-type','output-name'])
def test_bad_ir_contract_fails_before_ready(tmp_path,bad):
    profiles(tmp_path,bad)
    with pytest.raises(ValueError): module().OpenVINOBlocks(tmp_path)


def test_direct_execution_uses_no_reference_neural_module_or_parameters(tmp_path):
    import torch
    profiles(tmp_path)
    backend=module().OpenVINOBlocks(tmp_path)
    assert not isinstance(backend,torch.nn.Module)
    assert not hasattr(backend,'parameters')
    result=backend.predict_block(torch.ones(1,128),torch.ones(1,128,dtype=torch.bool),torch.zeros(1,dtype=torch.long),1)
    assert result.shape==(1,32,21)
    assert result.dtype==torch.float32
    assert torch.count_nonzero(result)==0


def test_symbolic_output_shape_is_verified_for_every_supported_context(tmp_path):
    profiles(tmp_path,dynamic=True)
    backend=module().OpenVINOBlocks(tmp_path)
    assert set(backend.compiled)=={1,2,3,4,5}


def test_incompatible_symbolic_execution_fails_before_ready(tmp_path):
    profiles(tmp_path,bad='dynamic-output',dynamic=True)
    shape=ov.Core().read_model(tmp_path/'block-1.xml').output(0).get_partial_shape()
    assert shape.is_dynamic
    assert shape.compatible(ov.PartialShape([1,32,21]))
    with pytest.raises(ValueError):
        module().OpenVINOBlocks(tmp_path)
