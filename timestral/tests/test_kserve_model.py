"""Model lifecycle and admission tested with real SDK objects; no weight downloads."""
import asyncio
import threading
from types import SimpleNamespace

import numpy as np
import pytest
from kserve.errors import InvalidInput, ModelNotReady

from serving.contract import ForecastResult
from serving.kserve_model import TimestralModel
from serving.upstream import Settings, UpstreamForecaster
from test_contract import request

LEVELS = np.array([.01,.05,.1,.15,.2,.25,.3,.35,.4,.45,.5,.55,.6,.65,.7,.75,.8,.85,.9,.95,.99],dtype=np.float32)
REVISION = 'a'*40


class BlockingBackend:
    """External computation double; admission and lifecycle remain production code."""
    def __init__(self, block=False, error=False):
        self.started = threading.Event()
        self.release = threading.Event()
        self.block, self.error = block, error

    def forecast(self, inputs):
        self.started.set()
        if self.block and not self.release.wait(5): raise RuntimeError('test timed out')
        if self.error: raise RuntimeError('Bearer sensitive-token private-series')
        return ForecastResult(np.ones((*inputs.context.shape[:2],inputs.prediction_length,21),dtype=np.float32),LEVELS)


def model(tmp_path, backend):
    settings = Settings(model_revision=REVISION, hf_home=str(tmp_path))
    return TimestralModel(settings, loader=lambda _: backend)


@pytest.mark.asyncio
async def test_load_readiness_ids_numerical_outputs_and_sdk_call(tmp_path):
    m = model(tmp_path,BlockingBackend())
    assert m.ready is False
    with pytest.raises(ModelNotReady): await m.predict(request())
    assert m.load() is True
    assert m.ready is True
    response, _ = await m(request())
    assert response.id == 'forecast-123'
    assert response.parameters['model_revision'] == REVISION
    assert response.parameters['model_id'] == 'mistralai/Timestral-209M'
    np.testing.assert_array_equal(response.outputs[1].as_numpy(), [[[1,1,1]]])
    assert [o['name'] for o in m.get_output_types()] == ['quantiles','median','quantile_levels']


@pytest.mark.asyncio
async def test_cancellation_does_not_release_running_inference(tmp_path):
    backend = BlockingBackend(block=True)
    m = model(tmp_path,backend); m.load()
    task = asyncio.create_task(m.predict(request()))
    assert await asyncio.to_thread(backend.started.wait,2)
    # Event loop is responsive while forecast runs; new work is rejected.
    with pytest.raises(ModelNotReady) as busy: await m.predict(request())
    assert busy.value.reason == 'inference capacity is occupied'
    task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    with pytest.raises(ModelNotReady): await m.predict(request())
    backend.release.set()
    for _ in range(100):
        await asyncio.sleep(.01)
        try:
            response = await m.predict(request())
            break
        except ModelNotReady: pass
    else: pytest.fail('capacity not released after computation finished')
    assert response.id == 'forecast-123'


@pytest.mark.asyncio
async def test_internal_failure_is_redacted_and_slot_recovers(tmp_path):
    backend = BlockingBackend(error=True)
    m = model(tmp_path,backend); m.load()
    with pytest.raises(RuntimeError,match='forecast inference failed') as error:
        await m.predict(request())
    assert 'sensitive-token' not in str(error.value)
    backend.error = False
    assert (await m.predict(request())).id == 'forecast-123'


def test_initialization_failure_never_sets_ready_or_exposes_details(tmp_path):
    def fail(_): raise RuntimeError('https://private.example?token=secret')
    m = TimestralModel(Settings(model_revision=REVISION,hf_home=str(tmp_path)),loader=fail)
    with pytest.raises(RuntimeError,match='model initialization failed') as error: m.load()
    assert 'secret' not in str(error.value)
    assert m.ready is False


@pytest.mark.parametrize('kwargs', [dict(model_revision='main'), dict(model_id='other/model'),
    dict(model_device='auto'),dict(backend='automatic'),dict(torch_num_threads=0),
    dict(model_device='cuda',backend='cpu'),dict(model_device='cpu',backend='cuda')])
def test_invalid_settings_fail_closed(kwargs):
    with pytest.raises(ValueError): Settings(**({'model_revision':REVISION}|kwargs))


@pytest.mark.asyncio
async def test_requested_output_names_are_validated_and_subset_preserved(tmp_path):
    from kserve.protocol.infer_type import RequestedOutput
    m = model(tmp_path,BlockingBackend()); m.load()
    req = request(); req.request_outputs = [RequestedOutput('median')]
    response = await m.predict(req)
    assert [o.name for o in response.outputs] == ['median']
    req.request_outputs = [RequestedOutput('missing')]
    with pytest.raises(InvalidInput): await m.predict(req)


@pytest.mark.parametrize('backend', ['cuda','rocm'])
def test_unavailable_accelerator_never_falls_back(monkeypatch,tmp_path,backend):
    import torch
    monkeypatch.setattr(torch.cuda,'is_available',lambda:False)
    with pytest.raises(RuntimeError,match='accelerator'):
        UpstreamForecaster.load(Settings(model_revision=REVISION,hf_home=str(tmp_path),backend=backend,model_device='cuda:0'))


@pytest.mark.asyncio
async def test_binary_response_uses_official_public_response_configuration(tmp_path):
    m = model(tmp_path,BlockingBackend()); m.load()
    req = request(); req.parameters = {'binary_data_output': True}
    response = await m.predict(req)
    body, header_length = response.to_rest()
    assert isinstance(body, bytes)
    assert header_length is not None
    from kserve import InferResponse
    decoded = InferResponse.from_bytes(body,header_length)
    np.testing.assert_array_equal(decoded.outputs[1].as_numpy(), [[[1,1,1]]])


@pytest.mark.parametrize('device,dtype',[('meta','float32'),('cpu','float16')])
def test_loaded_weights_must_match_requested_device_and_precision(monkeypatch,tmp_path,device,dtype):
    import torch
    from timestral import TimestralForecaster
    neural = torch.nn.Linear(1,1,device=device,dtype=getattr(torch,dtype))
    monkeypatch.setattr(TimestralForecaster,'from_pretrained',lambda *a,**kw:SimpleNamespace(model=neural))
    with pytest.raises(RuntimeError,match='device and FP32'):
        UpstreamForecaster.load(Settings(model_revision=REVISION,hf_home=str(tmp_path)))


@pytest.mark.asyncio
async def test_failed_executor_submission_releases_capacity(monkeypatch,tmp_path):
    m=model(tmp_path,BlockingBackend()); m.load()
    original=asyncio.to_thread
    async def fail(*args,**kwargs): raise RuntimeError('executor unavailable')
    monkeypatch.setattr(asyncio,'to_thread',fail)
    with pytest.raises(RuntimeError,match='forecast inference failed'): await m.predict(request())
    monkeypatch.setattr(asyncio,'to_thread',original)
    assert (await m.predict(request())).id=='forecast-123'


@pytest.mark.asyncio
@pytest.mark.parametrize('field,value',[('model_name','other'),('model_version','b'*40)])
async def test_inference_identity_cannot_select_another_model(tmp_path,field,value):
    m=model(tmp_path,BlockingBackend()); m.load()
    req=request(); setattr(req,field,value)
    with pytest.raises(InvalidInput): await m.predict(req)


def test_packaged_variant_cannot_be_changed_by_runtime_environment(monkeypatch,tmp_path):
    import serving.upstream as upstream
    (tmp_path/'image-variant').write_text('cuda\n')
    monkeypatch.setattr(upstream,'__file__',str(tmp_path/'serving/upstream.py'))
    monkeypatch.setenv('MODEL_REVISION',REVISION)
    monkeypatch.setenv('TIMESTRAL_BACKEND','cpu')
    monkeypatch.setenv('MODEL_DEVICE','cpu')
    with pytest.raises(ValueError,match='packaged variant'): Settings.from_env()


@pytest.mark.asyncio
async def test_preview_response_declares_its_distinct_forecast_configuration(tmp_path):
    m=TimestralModel(Settings(model_revision='bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f',
        model_id='mistralai/Timestral-5M',backend='openvino'),loader=lambda _:BlockingBackend())
    m.load()
    response=await m.predict(request())
    assert response.parameters['experimental'] is True
    assert response.parameters['max_context']==256
    assert response.parameters['per_shot_horizon_patches']==5
