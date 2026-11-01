"""Run inside an immutable candidate image; no extra packages or host changes.

CPU reference uses unchanged upstream forecasting in this same pinned framework
build. Strict CPU CI tolerances are retained; failed cases are evidence, never a
reason to silently widen tolerances. This is acceptance, not a performance test.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import uuid

import numpy as np


def fixtures():
    for name, b, v, t, h in (
        ('short', 1, 1, 7, 3), ('nonaligned', 1, 1, 65, 35),
        ('long', 1, 1, 1103, 33), ('missing', 1, 1, 65, 35),
        ('grouped', 2, 2, 65, 35), ('decode-blocks', 1, 1, 65, 1024),
        ('covariates', 1, 1, 65, 35), ('symmetry-off', 1, 1, 65, 35),
        ('clip-off', 1, 1, 65, 35), ('both-off', 1, 1, 65, 35),
    ):
        context = np.sin(np.arange(b*v*t, dtype=np.float32).reshape(b, v, t)/7)
        mask = np.ones(context.shape, dtype=bool)
        if name == 'missing':
            mask[..., 1::3] = False
        values = dict(context=context, observation_mask=mask,
                      prediction_length=np.array([h], dtype=np.int64))
        kwargs = dict(observation_mask=mask)
        if name in ('symmetry-off', 'clip-off', 'both-off'):
            if name == 'clip-off':
                context[:] = np.abs(context)
            for option, enabled in [('symmetric_averaging', name == 'clip-off'),
                                    ('clip_nonnegative', name == 'symmetry-off')]:
                values[option] = np.array([enabled], dtype=bool)
                kwargs[option] = enabled
        if name == 'covariates':
            for key in ('past_covariates', 'known_covariates',
                        'categorical_past_covariates', 'categorical_known_covariates'):
                length = t+h if 'known' in key else t
                a = (np.arange(length).reshape(1, 1, length) % 3).astype(
                    np.float64 if key.startswith('categorical') else np.float32)
                if key.startswith('categorical'):
                    a += 2**24
                observed = np.ones(a.shape, dtype=bool)
                observed[..., 2::5] = False
                values[key], values[key+'_mask'] = a, observed
                internal = a.copy()
                internal[~observed] = np.nan
                kwargs[key] = internal
        yield name, values, h, kwargs


def request(values, request_id):
    from kserve import InferInput, InferRequest
    types = {'float32': 'FP32', 'float64': 'FP64', 'bool': 'BOOL', 'int64': 'INT64'}
    return InferRequest(model_name='timestral', request_id=request_id, infer_inputs=[
        InferInput(name=key, shape=list(a.shape), datatype=types[str(a.dtype)],
                   data=a) for key, a in values.items()])


def http_infer(values, request_id, binary=False):
    from kserve import InferResponse
    inputs, payloads = [], []
    for inp in request(values, request_id).inputs:
        entry = dict(name=inp.name, shape=inp.shape, datatype=inp.datatype)
        a = values[inp.name]
        if binary:
            raw = a.tobytes()
            entry['parameters'] = dict(binary_data_size=len(raw))
            payloads.append(raw)
        else:
            entry['data'] = a.reshape(-1).tolist()
        inputs.append(entry)
    raw = json.dumps(dict(id=request_id, inputs=inputs)).encode()
    headers = {'content-type': 'application/json'}
    if binary:
        headers = {'content-type': 'application/octet-stream',
                   'inference-header-content-length': str(len(raw))}
        raw += b''.join(payloads)
    req = urllib.request.Request('http://127.0.0.1:8080/v2/models/timestral/infer',
                                 data=raw, headers=headers)
    with urllib.request.urlopen(req, timeout=600) as response:
        return InferResponse.from_rest(json.load(response))


def compare(actual, expected):
    errors = {}
    assert set(actual) == set(expected)
    for key in expected:
        a, e = actual[key], expected[key]
        assert a.dtype == e.dtype == np.float32
        assert a.shape == e.shape
        assert np.isfinite(a).all()
        errors[key] = float(np.max(np.abs(a-e)))
        np.testing.assert_allclose(a, e, rtol=1e-5, atol=1e-5)
    return errors


def run(report):
    import grpc
    import torch
    from kserve import InferResponse
    from kserve.protocol.grpc import grpc_predict_v2_pb2_grpc as rpc
    from serving.upstream import Settings, _check_device
    from timestral import TimestralForecaster

    settings = Settings.from_env()
    device = _check_device(settings, torch)
    props = torch.cuda.get_device_properties(device)
    report.update(backend=settings.backend, model=settings.model_id,
                  revision=settings.model_revision, torch=torch.__version__,
                  cuda=torch.version.cuda, hip=torch.version.hip,
                  device=props.name, architecture=getattr(props, 'gcnArchName', None),
                  compute_capability=[props.major, props.minor],
                  image=os.environ['ACCEPTANCE_IMAGE'], source=os.environ['ACCEPTANCE_SOURCE'],
                  probe_sha256=os.environ['ACCEPTANCE_PROBE_SHA256'],
                  tolerances=dict(rtol=1e-5, atol=1e-5), cases=[])
    # Prove missing accelerator fails; no weights need to be loaded for this gate.
    hidden = dict(os.environ, CUDA_VISIBLE_DEVICES='', HIP_VISIBLE_DEVICES='', ROCR_VISIBLE_DEVICES='')
    result = subprocess.run([sys.executable, '-c',
        'import torch; from serving.upstream import Settings, _check_device; '
        '_check_device(Settings.from_env(), torch)'], env=hidden,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=60)
    assert result.returncode != 0 and b'requested accelerator is unavailable' in result.stderr
    report['missing_device_rejected'] = True
    torch.set_num_threads(2)
    reference = TimestralForecaster.from_pretrained(settings.model_id,
        revision=settings.model_revision, device='cpu', cache_dir=settings.hf_home)
    # This separate process owns one GPU model and checks all parameter residency
    # and FP32 invariants in the production loader before the server can be Ready.
    server = subprocess.Popen([sys.executable, '-m', 'serving', '--workers', '1',
        '--http_port', '8080', '--grpc_port', '8081',
        '--grpc_max_receive_message_length', '8388608'])
    try:
        deadline = time.monotonic()+600
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError('candidate server exited before Ready')
            try:
                with urllib.request.urlopen('http://127.0.0.1:8080/v2/health/ready', timeout=2) as r:
                    if r.status == 200:
                        break
            except OSError:
                pass
            time.sleep(1)
        else:
            raise TimeoutError('candidate readiness timed out')
        with grpc.insecure_channel('127.0.0.1:8081', options=[
                ('grpc.max_receive_message_length', 16*1024*1024)]) as channel:
            stub = rpc.GRPCInferenceServiceStub(channel)
            for name, values, h, kwargs in fixtures():
                result = reference.forecast(values['context'], h, **kwargs)
                expected = dict(quantiles=result.quantiles.cpu().numpy(),
                    median=result.median.cpu().numpy(),
                    quantile_levels=np.asarray(result.quantile_levels, dtype=np.float32))
                for transport in ('http-json', 'http-binary', 'grpc'):
                    identity = str(uuid.uuid4())
                    start = time.monotonic()
                    if transport == 'grpc':
                        response = InferResponse.from_grpc(stub.ModelInfer(
                            request(values, identity).to_grpc(), timeout=600))
                    else:
                        response = http_infer(values, identity, transport == 'http-binary')
                    assert response.id == identity and response.model_name == 'timestral'
                    actual = {out.name: out.as_numpy() for out in response.outputs}
                    passed = True
                    try:
                        error = compare(actual, expected)
                    except AssertionError:
                        # Preserve the failure while collecting the remaining
                        # cases; never make one mismatch hide later coverage.
                        passed = False
                        report.setdefault('failed_cases', []).append(dict(case=name, transport=transport))
                        error = {key: float(np.max(np.abs(actual[key]-expected[key])))
                                 for key in expected if key in actual and actual[key].shape == expected[key].shape}
                    case = dict(case=name, transport=transport, passed=passed, max_absolute_error=error,
                                elapsed_seconds=time.monotonic()-start)
                    report['cases'].append(case)
                    print(json.dumps(case), flush=True)
    finally:
        server.terminate()
        try:
            server.wait(timeout=30)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
    if report.get('failed_cases'):
        raise AssertionError('GPU forecasts exceed the unchanged CPU parity threshold')
    report['result'] = 'passed'


def main():
    report = dict(result='failed', promotion='not-authorized')
    destination = Path(os.environ.get('ACCEPTANCE_REPORT', '/results/acceptance.json'))
    try:
        run(report)
    finally:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2)+'\n')
        print('ACCEPTANCE_REPORT '+json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
