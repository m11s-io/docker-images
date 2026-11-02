"""Real official server transports exercise cancellation without neural weights."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import grpc
import pytest
from kserve import InferRequest, InferInput
from kserve.protocol.grpc import grpc_predict_v2_pb2_grpc as rpc

SERVER = '''
import sys,time
from pathlib import Path
import numpy as np
from kserve import ModelServer,model_server
from serving.contract import ForecastResult
from serving.errors import configure_transport_errors
from serving.kserve_model import TimestralModel
from serving.upstream import Settings
http,grpc,root=int(sys.argv[-3]),int(sys.argv[-2]),Path(sys.argv[-1])
class Blocking:
 def forecast(self,inputs):
  (root/'started').touch()
  deadline=time.monotonic()+30
  while not (root/'release').exists():
   if time.monotonic()>deadline:raise RuntimeError('bounded test computation timed out')
   time.sleep(.01)
  levels=np.array([.01,.05,.1,.15,.2,.25,.3,.35,.4,.45,.5,.55,.6,.65,.7,.75,.8,.85,.9,.95,.99],dtype=np.float32)
  return ForecastResult(np.ones((*inputs.context.shape[:2],inputs.prediction_length,21),dtype=np.float32),levels)
configure_transport_errors(model_server.app)
m=TimestralModel(Settings(model_id='mistralai/Timestral-5M',model_revision='bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f'),loader=lambda _:Blocking());m.load()
ModelServer(http_port=http,grpc_port=grpc,workers=1).start([m])
'''


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]


def test_real_server_cancellation_keeps_execution_slot_until_worker_finishes(tmp_path):
    http_port,grpc_port=port(),port()
    while grpc_port==http_port:grpc_port=port()
    log=(tmp_path/'server.log').open('w')
    server=subprocess.Popen([sys.executable,'-c',SERVER,str(http_port),str(grpc_port),str(tmp_path)],
        stdout=log,stderr=subprocess.STDOUT,env=os.environ.copy())
    body=dict(id='cancelled-request',inputs=[
        dict(name='context',datatype='FP32',shape=[1,1,3],data=[1.,2.,3.]),
        dict(name='observation_mask',datatype='BOOL',shape=[1,1,3],data=[True]*3),
        dict(name='prediction_length',datatype='INT64',shape=[1],data=[3])])
    try:
        with grpc.insecure_channel(f'127.0.0.1:{grpc_port}') as channel:
            grpc.channel_ready_future(channel).result(timeout=30)
            stub=rpc.GRPCInferenceServiceStub(channel)
            request=InferRequest(model_name='timestral',request_id=body['id'],infer_inputs=[InferInput(**i) for i in body['inputs']]).to_grpc()
            first=stub.ModelInfer.future(request,timeout=30)
            deadline=time.monotonic()+10
            while not (tmp_path/'started').exists():
                assert server.poll() is None
                if time.monotonic()>deadline:pytest.fail('server did not enter inference')
                time.sleep(.01)
            first.cancel()
            with pytest.raises(grpc.FutureCancelledError):first.result()
            with pytest.raises(grpc.RpcError) as busy:stub.ModelInfer(request,timeout=5)
            assert busy.value.code()==grpc.StatusCode.UNAVAILABLE
            req=urllib.request.Request(f'http://127.0.0.1:{http_port}/v2/models/timestral/infer',
                data=json.dumps(body).encode(),headers={'content-type':'application/json'})
            with pytest.raises(urllib.error.HTTPError) as busy_http:urllib.request.urlopen(req,timeout=5)
            assert busy_http.value.code==503
            (tmp_path/'release').touch()
            deadline=time.monotonic()+10
            while True:
                try:
                    response=stub.ModelInfer(request,timeout=5)
                    break
                except grpc.RpcError as error:
                    assert error.code()==grpc.StatusCode.UNAVAILABLE
                    if time.monotonic()>deadline:raise
                    time.sleep(.01)
            assert response.id=='cancelled-request'
            assert len(response.outputs)==3

    finally:
        (tmp_path/'release').touch()
        server.terminate()
        try:server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill();server.wait()
        log.close()
