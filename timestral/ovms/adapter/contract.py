"""Explicit bounded KServe tensor contract; no HTTP framework."""
import numpy as np

INPUTS = frozenset({'context', 'observation_mask', 'prediction_length'})
MAX_CONTEXT = 256
MAX_HORIZON = 320


def validate_request(inputs):
    if set(inputs) != INPUTS:
        raise ValueError('expected context, observation_mask and prediction_length only')
    context = np.asarray(inputs['context'])
    mask = np.asarray(inputs['observation_mask'])
    horizon = np.asarray(inputs['prediction_length'])
    if context.dtype != np.float32 or context.ndim != 3 or context.shape[:2] != (1, 1):
        raise ValueError('context must be FP32 [1,1,T]')
    if not 1 <= context.shape[2] <= MAX_CONTEXT or not np.isfinite(context).all():
        raise ValueError('context length must be 1..256 with finite values')
    if mask.dtype != np.bool_ or mask.shape != context.shape or not mask.any():
        raise ValueError('observation_mask must be BOOL matching context, with at least one observation')
    if horizon.dtype != np.int64 or horizon.shape != (1,) or not 1 <= int(horizon[0]) <= MAX_HORIZON:
        raise ValueError('prediction_length must be INT64 [1] in 1..320')
    # Missing observations are explicit; no NaN representation on this API.
    return np.where(mask, context, np.float32(0)), mask, int(horizon[0])


def validate_response(quantiles, levels, horizon):
    values = np.asarray(quantiles)
    levels = np.asarray(levels, dtype=np.float32)
    if values.dtype != np.float32 or values.shape != (1, 1, horizon, 21) or not np.isfinite(values).all():
        raise ValueError('invalid forecast quantiles')
    if (levels.shape != (21,) or not np.isfinite(levels).all() or not np.all(np.diff(levels) > 0)
            or levels[0] < 0 or levels[-1] > 1 or np.count_nonzero(levels == .5) != 1):
        raise ValueError('invalid quantile levels')
    median = values[..., int(np.flatnonzero(levels == .5)[0])]
    return {'quantiles': np.ascontiguousarray(values), 'median': np.ascontiguousarray(median),
            'quantile_levels': np.ascontiguousarray(levels)}
