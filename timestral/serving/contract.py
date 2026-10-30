"""Version 1 forecasting tensors; no model loading or forecasting algorithms."""
from dataclasses import dataclass, field
import math
import numbers
from collections.abc import Iterable

import numpy as np
from kserve import InferInput, InferOutput, InferRequest, InferResponse
from kserve.errors import InvalidInput

MAX_REQUEST_BYTES = 8 * 1024 * 1024
COVARIATES = ('past_covariates', 'known_covariates',
              'categorical_past_covariates', 'categorical_known_covariates')
OPTIONS = ('symmetric_averaging', 'clip_nonnegative')
DTYPES = {'FP32': np.dtype('float32'), 'FP64': np.dtype('float64'),
          'BOOL': np.dtype('bool'), 'INT64': np.dtype('int64')}


@dataclass(frozen=True)
class ForecastInputs:
    context: np.ndarray
    observation_mask: np.ndarray
    prediction_length: int
    covariates: dict[str, np.ndarray] = field(default_factory=dict)
    symmetric_averaging: bool = True
    clip_nonnegative: bool = True


@dataclass(frozen=True)
class ForecastResult:
    quantiles: np.ndarray
    quantile_levels: np.ndarray


def _fail(message):
    raise InvalidInput(message)


def _check_values(data, datatype):
    """Reject JSON coercions before the SDK converts mixed values to numeric data."""
    if data is None:
        return  # Binary contents are decoded and checked by as_numpy below.
    if isinstance(data, np.ndarray):
        if data.dtype != DTYPES[datatype]:
            _fail('tensor storage dtype does not match declaration')
        return
    if isinstance(data, Iterable) and not isinstance(data, (str, bytes)):
        for item in data:
            _check_values(item, datatype)
        return
    if datatype == 'BOOL':
        valid = isinstance(data, (bool, np.bool_))
    elif datatype == 'INT64':
        valid = isinstance(data, numbers.Integral) and not isinstance(data, (bool, np.bool_))
    else:
        valid = isinstance(data, numbers.Real) and not isinstance(data, (bool, np.bool_))
    if not valid:
        _fail('tensor contains invalid scalar types')


def _array(inp: InferInput) -> np.ndarray:
    try:
        _check_values(inp.data, inp.datatype)
        value = inp.as_numpy()
    except (TypeError, ValueError, OverflowError, RecursionError):
        _fail('invalid tensor contents')
    if value.dtype != DTYPES[inp.datatype] or tuple(value.shape) != tuple(inp.shape):
        _fail('tensor contents do not match declaration')
    if value.dtype.kind == 'f' and not np.isfinite(value).all():
        _fail('tensors must contain finite placeholders')
    return value


def parse_forecast(request: InferRequest) -> ForecastInputs:
    if not isinstance(request, InferRequest):
        _fail('a standard V2 tensor request is required')
    tensors = {}
    allowed = {'context', 'observation_mask', 'prediction_length', *OPTIONS,
               *COVARIATES, *(name+'_mask' for name in COVARIATES)}
    total_bytes = 0
    # Validate declarations and budgets before decoding/allocating tensor arrays.
    for inp in request.inputs:
        if inp.name not in allowed or inp.name in tensors:
            _fail('unknown or duplicate tensor name')
        expected = ('INT64' if inp.name == 'prediction_length' else
                    'BOOL' if inp.name == 'observation_mask' or inp.name.endswith('_mask') or inp.name in OPTIONS else
                    'FP64' if inp.name.startswith('categorical_') else 'FP32')
        if inp.datatype != expected:
            _fail('incorrect tensor datatype')
        rank = 1 if inp.name in (*OPTIONS, 'prediction_length') else 3
        if (len(inp.shape) != rank or
                any(type(dim) is not int or dim < 1 for dim in inp.shape) or
                (rank == 1 and inp.shape != [1])):
            _fail('incorrect tensor rank or dimensions')
        total_bytes += math.prod(inp.shape) * DTYPES[expected].itemsize
        if total_bytes > MAX_REQUEST_BYTES:
            _fail('tensor byte budget exceeded')
        tensors[inp.name] = inp
    if not {'context', 'observation_mask', 'prediction_length'} <= tensors.keys():
        _fail('context, observation_mask and prediction_length are required')
    b, v, t = tensors['context'].shape
    if b > 8 or b*v > 32 or t > 32768:
        _fail('batch, total row or context budget exceeded')
    if tensors['observation_mask'].shape != [b,v,t]:
        _fail('observation mask must match context')
    h = int(_array(tensors['prediction_length'])[0])
    if not 1 <= h <= 1024 or b*v*h*21 > 1_000_000:
        _fail('horizon or output budget exceeded')
    rows = v
    for name in COVARIATES:
        if (name in tensors) != (name+'_mask' in tensors):
            _fail('each covariate requires exactly one matching mask')
        if name not in tensors:
            continue
        shape = tensors[name].shape
        length = t+h if 'known' in name else t
        if shape[0] != b or shape[2] != length or tensors[name+'_mask'].shape != shape:
            _fail('incorrect covariate or mask shape')
        rows += shape[1]
    if b*rows > 32:
        _fail('total row budget exceeded')
    context = _array(tensors['context'])
    observed = _array(tensors['observation_mask'])
    if not observed.any(axis=-1).all():
        _fail('each target row must have an observed value')
    covariates = {}
    for name in COVARIATES:
        if name in tensors:
            value = _array(tensors[name]).copy()
            value[~_array(tensors[name+'_mask'])] = np.nan
            covariates[name] = value
    options = {name: bool(_array(tensors[name])[0]) if name in tensors else True for name in OPTIONS}
    return ForecastInputs(context, observed, h, covariates, **options)


def encode_forecast(result: ForecastResult, request_id: str, model_name: str) -> InferResponse:
    q = np.asarray(result.quantiles, dtype=np.float32)
    levels = np.asarray(result.quantile_levels, dtype=np.float32)
    if (q.ndim != 4 or any(d < 1 for d in q.shape) or q.shape[-1] != 21 or
            levels.shape != (21,) or not np.isfinite(q).all() or not np.isfinite(levels).all() or
            not (np.diff(levels) > 0).all() or levels[0] < 0 or levels[-1] > 1 or
            np.count_nonzero(levels == .5) != 1):
        raise ValueError('invalid forecast result or quantile metadata')
    outputs = []
    for name, value in (('quantiles', q), ('median', q[..., int(np.flatnonzero(levels==.5)[0])]),
                        ('quantile_levels', levels)):
        output = InferOutput(name, list(value.shape), 'FP32')
        output.set_data_from_numpy(np.ascontiguousarray(value))
        outputs.append(output)
    return InferResponse(request_id, model_name, outputs, parameters={'contract_version': '1'})
