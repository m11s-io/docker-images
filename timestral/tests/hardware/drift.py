"""Independent upstream CPU/GPU drift versus production server on the same GPU.

Diagnostic only: no tolerance change or promotion. Synthetic input bytes are
shared by all paths. Run in a digest-pinned candidate using isolated Job mounts.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import numpy as np

HORIZONS=(32,64,128,256,320,512,768,1024)


def metrics(actual, expected):
    assert actual.dtype==expected.dtype==np.float32
    assert actual.shape==expected.shape
    assert np.isfinite(actual).all() and np.isfinite(expected).all()
    delta=np.abs(actual.astype(np.float64)-expected.astype(np.float64))
    violations=int(np.sum(delta>1e-5+1e-5*np.abs(expected.astype(np.float64))))
    return dict(strict_pass=violations==0,bitwise_equal=np.array_equal(actual,expected),
        violations=violations,elements=int(actual.size),max_absolute_error=float(delta.max()),
        max_error_scaled_by_max_abs_reference_or_one=float(np.max(delta/np.maximum(np.abs(expected),1))),
        reference_max_absolute_value=float(np.max(np.abs(expected))))


def arrays(result):
    return dict(quantiles=result.quantiles.detach().cpu().numpy().copy(),
                median=result.median.detach().cpu().numpy().copy(),
                quantile_levels=np.asarray(result.quantile_levels,dtype=np.float32).copy())


def compare(actual,expected):
    assert set(actual)==set(expected)
    return {k:metrics(actual[k],expected[k]) for k in expected}


def run(report):
    import grpc
    import torch
    from timestral import TimestralForecaster
    from serving.upstream import Settings,_check_device
    from kserve import InferResponse
    from kserve.protocol.grpc import grpc_predict_v2_pb2_grpc as rpc
    from probe import http_infer,request

    s=Settings.from_env();device=_check_device(s,torch)
    torch.set_num_threads(2)
    if s.backend=='cuda':
        torch.backends.fp32_precision='ieee'
        torch.backends.cuda.matmul.fp32_precision='ieee'
        torch.backends.cudnn.conv.fp32_precision='ieee'
        torch.backends.cudnn.rnn.fp32_precision='ieee'
    else:
        torch.set_float32_matmul_precision('highest')
    report.update(backend=s.backend,model=s.model_id,revision=s.model_revision,
        image=os.environ['ACCEPTANCE_IMAGE'],source=os.environ['ACCEPTANCE_SOURCE'],
        device=torch.cuda.get_device_name(device),torch=torch.__version__,
        diagnostic_sha256=os.environ['DRIFT_SHA256'],probe_sha256=os.environ['ACCEPTANCE_PROBE_SHA256'],
        horizons=[],tolerance=dict(rtol=1e-5,atol=1e-5))
    # Both references invoke the original class directly, independently of the
    # serving adapter. Same FP32 precision policy as the production loader.
    cpu=TimestralForecaster.from_pretrained(s.model_id,revision=s.model_revision,
        device='cpu',cache_dir=s.hf_home)
    gpu=TimestralForecaster.from_pretrained(s.model_id,revision=s.model_revision,
        device=device,cache_dir=s.hf_home)
    assert all(p.device==device and p.dtype==torch.float32 for p in gpu.model.parameters())
    server=subprocess.Popen([sys.executable,'-m','serving','--workers','1',
        '--http_port','8080','--grpc_port','8081','--grpc_max_receive_message_length','8388608'])
    try:
        import urllib.request
        deadline=time.monotonic()+600
        while time.monotonic()<deadline:
            if server.poll() is not None: raise RuntimeError('server exited before Ready')
            try:
                with urllib.request.urlopen('http://127.0.0.1:8080/v2/health/ready',timeout=2) as response:
                    if response.status==200: break
            except OSError: pass
            time.sleep(1)
        else: raise TimeoutError('readiness timeout')
        context=np.sin(np.arange(65,dtype=np.float32).reshape(1,1,65)/7)
        mask=np.ones(context.shape,dtype=bool)
        with grpc.insecure_channel('127.0.0.1:8081') as channel:
            stub=rpc.GRPCInferenceServiceStub(channel)
            for horizon in HORIZONS:
                values=dict(context=context,observation_mask=mask,
                            prediction_length=np.array([horizon],dtype=np.int64))
                cpu_a=arrays(cpu.forecast(context,horizon,observation_mask=mask))
                cpu_b=arrays(cpu.forecast(context,horizon,observation_mask=mask))
                gpu_a=arrays(gpu.forecast(context,horizon,observation_mask=mask))
                gpu_b=arrays(gpu.forecast(context,horizon,observation_mask=mask))
                item=dict(horizon=horizon,cpu_repeat=compare(cpu_b,cpu_a),
                    gpu_repeat=compare(gpu_b,gpu_a),upstream_gpu_vs_cpu=compare(gpu_a,cpu_a),
                    server_vs_upstream_gpu={})
                for transport in ('http-json','http-binary','grpc'):
                    identity=str(uuid.uuid4())
                    if transport=='grpc':
                        result=InferResponse.from_grpc(stub.ModelInfer(request(values,identity).to_grpc(),timeout=600))
                    else: result=http_infer(values,identity,transport=='http-binary')
                    assert result.id==identity
                    actual={out.name:out.as_numpy() for out in result.outputs}
                    item['server_vs_upstream_gpu'][transport]=compare(actual,gpu_a)
                report['horizons'].append(item)
                print('DRIFT_HORIZON '+json.dumps(item),flush=True)
    finally:
        server.terminate()
        try: server.wait(timeout=30)
        except subprocess.TimeoutExpired:
            server.kill();server.wait()
    report['diagnostic_complete']=True
    report['same_gpu_parity']=all(m['strict_pass'] for h in report['horizons']
        for transport in h['server_vs_upstream_gpu'].values() for m in transport.values())
    # CPU/GPU differences are evidence, not a relaxed acceptance gate.
    report['cpu_gpu_parity']=all(m['strict_pass'] for h in report['horizons']
        for m in h['upstream_gpu_vs_cpu'].values())


def main():
    report=dict(diagnostic_complete=False,promotion='not-authorized')
    try: run(report)
    finally:
        Path('/results/drift.json').write_text(json.dumps(report,indent=2)+'\n')
        print('DRIFT_REPORT '+json.dumps(report),flush=True)


if __name__=='__main__': main()
