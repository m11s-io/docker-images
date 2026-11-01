"""Actual-image acceptance. Opt in with endpoints; never replaced by mock inference."""
import os
import uuid
import numpy as np
import pytest

HTTP = os.environ.get('TIMESTRAL_TEST_HTTP_URL')
GRPC = os.environ.get('TIMESTRAL_TEST_GRPC_URL')
PREVIEW = os.environ.get('TIMESTRAL_TEST_PREVIEW') == '1'
pytestmark = pytest.mark.skipif(not (HTTP and GRPC),reason='requires actual candidate image HTTP/gRPC endpoints')


@pytest.fixture(scope='module')
def reference(record_testsuite_property):
    from forecast_cases import forecast_tolerances
    for name,value in forecast_tolerances(PREVIEW).items():
        record_testsuite_property('forecast_'+name,str(value))
    record_testsuite_property('model_id',os.environ['MODEL_ID'])
    record_testsuite_property('model_revision',os.environ['MODEL_REVISION'])
    if os.environ.get('TIMESTRAL_REFERENCE_DIR'):
        import json
        from pathlib import Path
        from types import SimpleNamespace
        root = Path(os.environ['TIMESTRAL_REFERENCE_DIR'])
        metadata = json.loads((root/'metadata.json').read_text())
        assert metadata['model_id'] == os.environ['MODEL_ID']
        assert metadata['revision'] == os.environ['MODEL_REVISION']
        return SimpleNamespace(max_context=metadata['max_context'], root=root)
    from timestral import TimestralForecaster
    import torch
    torch.set_num_threads(2)
    return TimestralForecaster.from_pretrained(
        os.environ['MODEL_ID'],revision=os.environ['MODEL_REVISION'],device='cpu',
        **({'max_context':256,'per_shot_horizon_patches':5} if PREVIEW else {}))


@pytest.mark.parametrize('transport',['http-json','http-binary','grpc'])
@pytest.mark.parametrize('case',['short','nonaligned','long','missing','grouped','blocks','multi-block','covariates','symmetry-off','clip-off','options'])
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
    from forecast_cases import make_case, forecast_tolerances
    b,v,t,h,context,values,kwargs = make_case(case, reference.max_context)
    if hasattr(reference, 'root'):
        with np.load(reference.root/f'{case}.npz') as arrays:
            values = {key[6:]: arrays[key] for key in arrays.files if key.startswith('input_')}
    inputs = []
    types = {np.dtype('float32'):'FP32',np.dtype('float64'):'FP64',np.dtype('int64'):'INT64',np.dtype('bool'):'BOOL'}
    for name,a in values.items():
        inp = protocol.InferInput(name,a.shape,types[a.dtype])
        if transport.startswith('http'): inp.set_data_from_numpy(a,binary_data=transport=='http-binary')
        else: inp.set_data_from_numpy(a)
        inputs.append(inp)
    request_id = str(uuid.uuid4())
    if PREVIEW and ((b,v)!=(1,1) or t>256 or h>320 or case=='covariates'):
        from tritonclient.utils import InferenceServerException
        with client, pytest.raises(InferenceServerException) as error:
            client.infer('timestral',inputs,request_id=request_id,headers={'content-type':'application/json'} if transport=='http-json' else None)
        assert error.value.status() == ('400' if transport.startswith('http') else 'StatusCode.INVALID_ARGUMENT')
        return
    if hasattr(reference, 'root'):
        with np.load(reference.root/f'{case}.npz') as arrays:
            expected_q = arrays['quantiles']
            expected_median = arrays['median']
            expected_levels = arrays['quantile_levels']
    else:
        expected = reference.forecast(context,h,**kwargs)
        expected_q = expected.quantiles.cpu().numpy()
        expected_median = expected.median.cpu().numpy()
        expected_levels = expected.quantile_levels
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
    np.testing.assert_allclose(q,expected_q,**forecast_tolerances(PREVIEW))
    np.testing.assert_allclose(median,expected_median,**forecast_tolerances(PREVIEW))
    np.testing.assert_allclose(levels,expected_levels,rtol=1e-6,atol=1e-7)


@pytest.mark.parametrize('case',['missing-datatype','invalid-binary-header','truncated-binary','invalid-json','invalid-binary-datatype'])
def test_actual_image_redacts_malformed_transport(case):
    import httpx
    import json
    private='private-series-marker-847236'
    body={'inputs':[{'name':private,'shape':[1,1,1],'data':[1234567.875]}]}
    url=f'http://{HTTP}/v2/models/timestral/infer'
    if case=='missing-datatype': response=httpx.post(url,json=body)
    elif case=='invalid-binary-header':
        response=httpx.post(url,content=b'{}',headers={'content-type':'application/octet-stream',
                            'inference-header-content-length':private})
    elif case in ('truncated-binary','invalid-binary-datatype'):
        body['inputs'][0].update(datatype='FP32',parameters={'binary_data_size':4})
        body['inputs'][0].pop('data')
        if case=='invalid-binary-datatype': body['inputs'][0]['datatype']=123
        raw=json.dumps(body).encode()
        response=httpx.post(url,content=raw+b'\x00',headers={'content-type':'application/octet-stream',
                            'inference-header-content-length':str(len(raw))})
    else:
        response=httpx.post(url,content='{"'+private,headers={'content-type':'application/json'})
    assert response.status_code==400
    assert private not in response.text
    assert '1234567.875' not in response.text
