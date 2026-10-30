"""Real SDK V2 routes must not echo/log series data on pre-model failures."""
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from kserve import Model
from kserve.errors import generic_exception_handler
from kserve.model_repository import ModelRepository
from kserve.protocol.dataplane import DataPlane
from kserve.protocol.rest.v2_endpoints import register_v2_endpoints


@pytest.fixture
def client():
    app=FastAPI()
    repository=ModelRepository()
    model=Model('timestral'); model.ready=True
    repository.update(model)
    register_v2_endpoints(app,DataPlane(model_registry=repository),None)
    # The test still executes the actual SDK routes when configuration is absent.
    try:
        from serving.errors import configure_transport_errors
    except ImportError:
        pass
    else:
        configure_transport_errors(app)
    # Match production: the SDK registers its generic handler after our hooks.
    app.add_exception_handler(Exception,generic_exception_handler)
    with TestClient(app,raise_server_exceptions=False) as client:
        yield client


@pytest.mark.parametrize('case',['missing-datatype','invalid-binary-header','truncated-binary','invalid-json','invalid-binary-datatype'])
def test_pre_model_failures_are_400_without_echo_or_log(client,caplog,case):
    private='private-series-marker-847236'
    body={'inputs':[{'name':private,'shape':[1,1,1],'data':[1234567.875]}]}
    if case=='missing-datatype': response=client.post('/v2/models/timestral/infer',json=body)
    elif case=='invalid-binary-header':
        response=client.post('/v2/models/timestral/infer',content=b'{}',headers={
            'content-type':'application/octet-stream','inference-header-content-length':private})
    elif case in ('truncated-binary','invalid-binary-datatype'):
        body['inputs'][0].update(datatype='FP32',parameters={'binary_data_size':4})
        body['inputs'][0].pop('data')
        if case=='invalid-binary-datatype': body['inputs'][0]['datatype']=123
        raw=json.dumps(body).encode()
        response=client.post('/v2/models/timestral/infer',content=raw+b'\x00',headers={
            'content-type':'application/octet-stream','inference-header-content-length':str(len(raw))})
    else:
        response=client.post('/v2/models/timestral/infer',content='{"'+private,headers={'content-type':'application/json'})
    assert response.status_code==400
    assert private not in response.text
    assert '1234567.875' not in response.text
    assert private not in caplog.text
    assert '1234567.875' not in caplog.text


@pytest.mark.parametrize('limit',[-1,0,8388609])
def test_invalid_grpc_receive_limits_fail_before_initialization(monkeypatch,limit):
    from serving import __main__ as entry
    monkeypatch.setattr(entry.model_server.args,'workers',1)
    monkeypatch.setattr(entry.model_server.args,'grpc_max_receive_message_length',limit)
    def forbid(): raise AssertionError('settings were loaded before the size guard')
    monkeypatch.setattr(entry.Settings,'from_env',forbid)
    with pytest.raises(ValueError,match='gRPC receive limit'): entry.main()
