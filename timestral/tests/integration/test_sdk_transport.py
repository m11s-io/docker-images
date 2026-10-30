"""Weight-free real-server diagnostic; separate from actual-image acceptance."""
import os
import numpy as np
import pytest

pytestmark = pytest.mark.skipif(not os.environ.get('TIMESTRAL_SDK_PROBE'),reason='requires weight-free sdk_server.py diagnostic')


@pytest.mark.parametrize('transport',['http-json','http-binary','grpc'])
def test_official_server_metadata_ids_and_transport(transport):
    if transport.startswith('http'):
        import tritonclient.http as protocol
        client = protocol.InferenceServerClient('localhost:18080')
    else:
        import tritonclient.grpc as protocol
        client = protocol.InferenceServerClient('localhost:18081')
    if transport.startswith('http'):
        with protocol.InferenceServerClient('localhost:18080') as probe:
            assert probe.is_server_ready()
    else:
        assert client.is_server_ready()
    if transport.startswith('http'):
        with protocol.InferenceServerClient('localhost:18080') as probe:
            assert probe.is_model_ready('timestral')
    else:
        assert client.is_model_ready('timestral')
    client.get_model_metadata('timestral')
    inputs = []
    for name,data,dtype in [('context',np.ones((1,1,5),dtype=np.float32),'FP32'),
                            ('observation_mask',np.ones((1,1,5),dtype=bool),'BOOL'),
                            ('prediction_length',np.array([3],dtype=np.int64),'INT64')]:
        inp = protocol.InferInput(name,data.shape,dtype)
        if transport.startswith('http'): inp.set_data_from_numpy(data,binary_data=transport=='http-binary')
        else: inp.set_data_from_numpy(data)
        inputs.append(inp)
    with client:
        result = client.infer('timestral',inputs,request_id='transport-probe',headers={'content-type':'application/json'} if transport=='http-json' else None)
    response = result.get_response()
    assert (response['id'] if isinstance(response,dict) else response.id) == 'transport-probe'
    np.testing.assert_array_equal(result.as_numpy('median'),[[[1,1,1]]])
    assert result.as_numpy('quantiles').shape == (1,1,3,21)
    assert result.as_numpy('quantile_levels').shape == (21,)


def test_grpc_invalid_input_status_is_standard():
    from tritonclient.grpc import InferenceServerClient
    from tritonclient.utils import InferenceServerException
    with InferenceServerClient('localhost:18081') as client:
        with pytest.raises(InferenceServerException) as error:
            client.infer('timestral',[],request_id='invalid')
    assert error.value.status() == 'StatusCode.INVALID_ARGUMENT'
