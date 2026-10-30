"""Actual-image acceptance. Opt in with endpoints; never replaced by mock inference."""
import os
import uuid
import numpy as np
import pytest

HTTP = os.environ.get('TIMESTRAL_TEST_HTTP_URL')
GRPC = os.environ.get('TIMESTRAL_TEST_GRPC_URL')
pytestmark = pytest.mark.skipif(not (HTTP and GRPC),reason='requires actual candidate image HTTP/gRPC endpoints')


@pytest.fixture(scope='module')
def reference():
    from timestral import TimestralForecaster
    import torch
    torch.set_num_threads(2)
    return TimestralForecaster.from_pretrained(
        os.environ['MODEL_ID'],revision=os.environ['MODEL_REVISION'],device='cpu')


@pytest.mark.parametrize('transport',['http-json','http-binary','grpc'])
@pytest.mark.parametrize('case',['short','nonaligned','long','missing','grouped','blocks','covariates','options'])
def test_standard_inference_matches_unchanged_upstream(reference,transport,case):
    if transport.startswith('http'):
        import tritonclient.http as protocol
        client = protocol.InferenceServerClient(HTTP)
    else:
        import tritonclient.grpc as protocol
        client = protocol.InferenceServerClient(GRPC)
    if transport.startswith('http'):
        with protocol.InferenceServerClient(HTTP) as probe:
            assert probe.is_server_live()
    else:
        assert client.is_server_live()
    if transport.startswith('http'):
        with protocol.InferenceServerClient(HTTP) as probe:
            assert probe.is_server_ready()
    else:
        assert client.is_server_ready()
    if transport.startswith('http'):
        with protocol.InferenceServerClient(HTTP) as probe:
            assert probe.is_model_ready('timestral')
    else:
        assert client.is_model_ready('timestral')
    metadata = client.get_model_metadata('timestral')
    if not isinstance(metadata,dict):
        from google.protobuf.json_format import MessageToDict
        metadata = MessageToDict(metadata,preserving_proto_field_name=True)
    assert metadata['name'] == 'timestral'
    assert {o['name'] for o in metadata['outputs']} == {'quantiles','median','quantile_levels'}
    b,v,t,h = {'short':(1,1,7,3),'nonaligned':(1,1,65,35),'long':(1,1,1103,33),
               'missing':(1,1,65,35),'grouped':(2,2,65,35),'blocks':(1,1,65,1024),
               'covariates':(1,1,65,35),'options':(1,1,65,35)}[case]
    context = np.sin(np.arange(b*v*t,dtype=np.float32).reshape(b,v,t)/7)
    mask = np.ones(context.shape,dtype=bool)
    if case == 'missing': mask[...,1::3] = False
    values = {'context':context,'observation_mask':mask,
              'prediction_length':np.array([h],dtype=np.int64)}
    kwargs = {'observation_mask':mask}
    if case == 'options':
        values.update(symmetric_averaging=np.array([False]),clip_nonnegative=np.array([False]))
        kwargs.update(symmetric_averaging=False,clip_nonnegative=False)
    if case == 'covariates':
        for name in ('past_covariates','known_covariates','categorical_past_covariates','categorical_known_covariates'):
            length = t+h if 'known' in name else t
            a = (np.arange(length).reshape(1,1,length)%3).astype(np.float64 if name.startswith('categorical') else np.float32)
            if name.startswith('categorical'): a += 2**24
            observed = np.ones(a.shape,dtype=bool); observed[...,2::5] = False
            values[name],values[name+'_mask'] = a,observed
            internal = a.copy(); internal[~observed] = np.nan
            kwargs[name] = internal
    expected = reference.forecast(context,h,**kwargs)
    inputs = []
    types = {np.dtype('float32'):'FP32',np.dtype('float64'):'FP64',np.dtype('int64'):'INT64',np.dtype('bool'):'BOOL'}
    for name,a in values.items():
        inp = protocol.InferInput(name,a.shape,types[a.dtype])
        if transport.startswith('http'): inp.set_data_from_numpy(a,binary_data=transport=='http-binary')
        else: inp.set_data_from_numpy(a)
        inputs.append(inp)
    request_id = str(uuid.uuid4())
    with client:
        result = client.infer('timestral',inputs,request_id=request_id,headers={'content-type':'application/json'} if transport=='http-json' else None)
    response = result.get_response()
    actual_id = response['id'] if isinstance(response,dict) else response.id
    assert actual_id == request_id
    q = result.as_numpy('quantiles')
    median = result.as_numpy('median')
    levels = result.as_numpy('quantile_levels')
    assert q.dtype == median.dtype == levels.dtype == np.float32
    assert q.shape == (b,v,h,21)
    assert median.shape == (b,v,h)
    assert levels.shape == (21,)
    np.testing.assert_allclose(q,expected.quantiles.cpu().numpy(),rtol=1e-5,atol=1e-5)
    np.testing.assert_allclose(median,expected.median.cpu().numpy(),rtol=1e-5,atol=1e-5)
    np.testing.assert_allclose(levels,expected.quantile_levels,rtol=1e-6,atol=1e-7)
