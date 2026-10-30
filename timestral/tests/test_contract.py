"""Consumer contract tests: malformed wire tensors must never reach inference."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest
from kserve import InferInput, InferRequest, InferResponse
from kserve.errors import InvalidInput

from serving.contract import ForecastResult, encode_forecast, parse_forecast


def tensor(name, data, datatype=None):
    a = np.asarray(data)
    datatype = datatype or {np.dtype('float32'): 'FP32', np.dtype('float64'): 'FP64',
                            np.dtype('int64'): 'INT64', np.dtype('bool'): 'BOOL'}[a.dtype]
    value = InferInput(name, list(a.shape), datatype)
    value.set_data_from_numpy(a)
    return value


def request(b=1, v=1, t=5, h=3):
    return InferRequest('timestral', [
        tensor('context', np.arange(b*v*t, dtype=np.float32).reshape(b,v,t)),
        tensor('observation_mask', np.ones((b,v,t), dtype=bool)),
        tensor('prediction_length', np.array([h], dtype=np.int64)),
    ], request_id='forecast-123')


def test_context_options_missingness_and_categorical_precision():
    req = request()
    mask = np.array([[[True, False, True, True, True]]])
    req.inputs[1] = tensor('observation_mask', mask)
    cats = np.array([[[2**24+1, 0, 2**24+2, 1, 2]]], dtype=np.float64)
    req.inputs += [tensor('categorical_past_covariates', cats),
                   tensor('categorical_past_covariates_mask', mask),
                   tensor('symmetric_averaging', np.array([False]))]
    got = parse_forecast(req)
    assert got.context.shape == (1,1,5)
    assert got.prediction_length == 3
    assert got.symmetric_averaging is False
    assert got.clip_nonnegative is True
    assert got.covariates['categorical_past_covariates'].dtype == np.float64
    assert got.covariates['categorical_past_covariates'][0,0,0] == 16777217
    assert np.isnan(got.covariates['categorical_past_covariates'][0,0,1])
    np.testing.assert_array_equal(got.observation_mask, mask)


@pytest.mark.parametrize('change', ['missing-context','missing-mask','duplicate','unknown',
    'dtype','rank','mask-shape','zero-dim','negative-dim','nan','infinity','empty-observed',
    'float-horizon','zero-horizon','large-horizon','batch','rows','context-length',
    'bool-number','int-bool','float-bool','fractional-int','orphan-mask','missing-cov-mask',
    'cov-length','cov-batch','cov-dtype','bytes'])
def test_invalid_tensors_are_rejected(change):
    req = request()
    if change.startswith('missing-') and change in ('missing-context','missing-mask'):
        req.inputs.pop(0 if change == 'missing-context' else 1)
    elif change == 'duplicate': req.inputs.append(req.inputs[0])
    elif change == 'unknown': req.inputs.append(tensor('surprise', np.array([1], dtype=np.int64)))
    elif change == 'dtype': req.inputs[0] = tensor('context', np.zeros((1,1,5), dtype=np.float64))
    elif change == 'rank': req.inputs[0] = tensor('context', np.zeros((1,5), dtype=np.float32))
    elif change == 'mask-shape': req.inputs[1] = tensor('observation_mask', np.ones((1,1,4), dtype=bool))
    elif change == 'zero-dim': req.inputs[0].shape = [1,0,5]
    elif change == 'negative-dim': req.inputs[0].shape = [1,1,-5]
    elif change in ('nan','infinity'):
        req.inputs[0] = tensor('context', np.full((1,1,5), np.nan if change=='nan' else np.inf, dtype=np.float32))
    elif change == 'empty-observed': req.inputs[1] = tensor('observation_mask', np.zeros((1,1,5),dtype=bool))
    elif change == 'float-horizon': req.inputs[2] = tensor('prediction_length', np.array([3.],dtype=np.float32))
    elif change == 'zero-horizon': req = request(h=0)
    elif change == 'large-horizon': req = request(h=1025)
    elif change == 'batch': req = request(b=9)
    elif change == 'rows': req = request(b=2,v=17)
    elif change == 'context-length': req.inputs[0].shape = [1,1,32769]
    elif change == 'bool-number': req.inputs[0] = InferInput('context',[1,1,5],'FP32',data=[1,True,2,3,4])
    elif change == 'int-bool': req.inputs[2] = InferInput('prediction_length',[1],'INT64',data=[True])
    elif change == 'float-bool': req.inputs.append(InferInput('clip_nonnegative',[1],'BOOL',data=[1]))
    elif change == 'fractional-int': req.inputs[2] = InferInput('prediction_length',[1],'INT64',data=[1.5])
    elif change == 'orphan-mask': req.inputs.append(tensor('past_covariates_mask',np.ones((1,1,5),dtype=bool)))
    elif change == 'missing-cov-mask': req.inputs.append(tensor('past_covariates',np.ones((1,1,5),dtype=np.float32)))
    elif change.startswith('cov-'):
        a = np.ones((2 if change=='cov-batch' else 1,1,7 if change=='cov-length' else 8),dtype=np.float64 if change=='cov-dtype' else np.float32)
        req.inputs += [tensor('known_covariates',a),tensor('known_covariates_mask',np.ones(a.shape,dtype=bool))]
    elif change == 'bytes': req.inputs[0].shape = [8,32,32768]
    with pytest.raises(InvalidInput): parse_forecast(req)


def test_all_covariates_have_matching_shapes_and_masks():
    req = request(b=2,v=2,t=7,h=3)
    for name in ('past_covariates','known_covariates','categorical_past_covariates','categorical_known_covariates'):
        shape = (2,1,10 if 'known' in name else 7)
        a = np.ones(shape,dtype=np.float64 if name.startswith('categorical') else np.float32)
        mask = np.ones(shape,dtype=bool); mask[...,1] = False
        req.inputs += [tensor(name,a),tensor(name+'_mask',mask)]
    got = parse_forecast(req)
    assert len(got.covariates) == 4
    for a in got.covariates.values(): assert np.isnan(a[...,1]).all()


def test_outputs_preserve_identity_names_order_quantiles_and_median():
    q = np.arange(126,dtype=np.float32).reshape(1,2,3,21)
    levels = np.array([.01,.05,.1,.15,.2,.25,.3,.35,.4,.45,.5,.55,.6,.65,.7,.75,.8,.85,.9,.95,.99],dtype=np.float32)
    response = encode_forecast(ForecastResult(q,levels), 'forecast-123','timestral')
    assert response.id == 'forecast-123'
    assert [o.name for o in response.outputs] == ['quantiles','median','quantile_levels']
    assert [o.datatype for o in response.outputs] == ['FP32']*3
    np.testing.assert_array_equal(response.outputs[0].as_numpy(), q)
    np.testing.assert_array_equal(response.outputs[1].as_numpy(), [[[10,31,52],[73,94,115]]])
    np.testing.assert_array_equal(response.outputs[2].as_numpy(),levels)


@pytest.mark.parametrize('bad',['shape','nonfinite','levels-order','levels-count','missing-median'])
def test_invalid_backend_results_are_not_encoded(bad):
    q = np.zeros((1,1,3,21),dtype=np.float32)
    levels = np.array([.01,.05,.1,.15,.2,.25,.3,.35,.4,.45,.5,.55,.6,.65,.7,.75,.8,.85,.9,.95,.99],dtype=np.float32)
    if bad == 'shape': q = q[...,0]
    if bad == 'nonfinite': q[...,0] = np.nan
    if bad == 'levels-order': levels = levels[::-1]
    if bad == 'levels-count': levels = levels[:-1]
    if bad == 'missing-median': levels[10] = .51
    with pytest.raises(ValueError): encode_forecast(ForecastResult(q,levels),'id','timestral')


@pytest.mark.parametrize('transport',['json','rest-binary','grpc-typed','grpc-binary'])
def test_official_protocol_paths_round_trip(transport):
    req = request()
    # Build the actual transport with the public SDK, then decode as the server does.
    if transport in ('json','rest-binary'):
        for inp in req.inputs:
            inp.set_data_from_numpy(inp.as_numpy(),binary_data=transport=='rest-binary')
        body, header_length = req.to_rest()
        if isinstance(body,dict): body = json.dumps(body).encode()
        req = InferRequest.from_bytes(body,header_length or len(body),'timestral')
    else:
        for inp in req.inputs:
            inp.set_data_from_numpy(inp.as_numpy(),binary_data=transport=='grpc-binary')
        req = InferRequest.from_grpc(req.to_grpc())
    got = parse_forecast(req)
    np.testing.assert_array_equal(got.context, [[[0,1,2,3,4]]])
    assert req.id == 'forecast-123'


def test_largest_output_within_row_and_horizon_budgets_is_accepted():
    got = parse_forecast(request(b=2,v=16,h=1024))
    assert got.context.shape == (2,16,5)
    assert got.prediction_length == 1024


def test_documented_json_fixture_is_accepted_by_sdk_and_contract():
    body = (Path(__file__).parent/'fixtures/forecast-v1.json').read_bytes()
    req = InferRequest.from_bytes(body,len(body),'timestral')
    got = parse_forecast(req)
    assert req.id == 'forecast-123'
    assert got.prediction_length == 3
    np.testing.assert_array_equal(got.observation_mask, [[[True,False,True,True,True]]])
