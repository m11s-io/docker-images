"""OVMS Python node: standard tensors -> upstream forecasting -> standard tensors."""
import os
from threading import Lock
import numpy as np
from contract import INPUTS, validate_request, validate_response


class OvmsPythonModel:
    def initialize(self, kwargs):
        import torch
        from backend import create_forecaster
        torch.set_num_threads(2)
        self.forecaster = create_forecaster(os.environ['TIMESTRAL_FORECAST_ARTIFACTS'])
        self.lock = Lock()

    def execute(self, inputs):
        from pyovms import Tensor
        if len(inputs) != len(INPUTS) or {t.name for t in inputs} != INPUTS:
            raise ValueError('invalid input tensor names')
        values = {t.name: np.asarray(t) for t in inputs}
        context, mask, horizon = validate_request(values)
        with self.lock:
            forecast = self.forecaster.forecast(context, horizon, observation_mask=mask,
                symmetric_averaging=True, clip_nonnegative=True)
            outputs = validate_response(forecast.quantiles.numpy(), forecast.quantile_levels, horizon)
        return [Tensor(name, value) for name, value in outputs.items()]
