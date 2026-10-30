"""Experimental direct OpenVINO execution; inherited upstream final forecasting."""
from pathlib import Path
import numpy as np
import torch
from timestral.config import TimestralConfig
from timestral.forecaster import TimestralForecaster
from timestral.model import TimestralModel


class OpenVINOBlocks:
    def __init__(self, artifact_directory):
        import openvino as ov
        root = Path(artifact_directory)
        self.config = TimestralConfig.load(root / 'config.json')
        if self.config.patch_size != 32 or self.config.num_quantiles != 21:
            raise ValueError('unsupported model configuration')
        core = ov.Core()
        self.compiled = {}
        for horizon in range(1, 6):
            model = core.read_model(root / f'block-{horizon}.xml')
            if {p.get_any_name() for p in model.inputs} != {'context', 'observed'}:
                raise ValueError('IR input names do not match contract')
            if len(model.outputs) != 1 or model.output(0).get_any_name() != 'quantiles':
                raise ValueError('IR output names do not match contract')
            import openvino as ov
            for name, dtype in [('context', ov.Type.f32), ('observed', ov.Type.boolean)]:
                port = model.input(name)
                shape = port.get_partial_shape()
                if (port.get_element_type() != dtype or shape.rank.get_length() != 2 or
                        shape[0].get_min_length() != 1 or shape[0].get_max_length() != 1 or
                        shape[1].get_min_length() != 32 or shape[1].get_max_length() != 256):
                    raise ValueError('invalid IR input type or shape')
            output = model.output(0)
            if output.get_element_type() != ov.Type.f32 or list(output.get_shape()) != [1, horizon*32, 21]:
                raise ValueError('invalid IR output type or shape')
            self.compiled[horizon] = core.compile_model(model, 'CPU', {
                'INFERENCE_PRECISION_HINT': 'f32', 'INFERENCE_NUM_THREADS': 2,
                'NUM_STREAMS': 1, 'ENABLE_CPU_PINNING': False})

    def eval(self):
        return self

    def scale(self, inputs, observed):
        return TimestralModel.scale(self, inputs, observed)

    def predict_block(self, inputs, observed, group_ids, horizon_patches,
                      role_ids=None, known_future=None, known_future_mask=None):
        if (inputs.device.type != 'cpu' or inputs.dtype != torch.float32 or inputs.ndim != 2
                or inputs.shape[0] != 1 or not 32 <= inputs.shape[1] <= 256 or inputs.shape[1] % 32):
            raise ValueError('unsupported neural context profile')
        if observed.dtype != torch.bool or observed.shape != inputs.shape:
            raise ValueError('invalid neural observation mask')
        if group_ids.shape != (1,) or int(group_ids[0]) != 0:
            raise ValueError('only one independent series is supported')
        if role_ids is not None and (role_ids.shape != (1,) or not bool((role_ids == 0).all())):
            raise ValueError('covariates are not supported')
        if known_future is not None or known_future_mask is not None or horizon_patches not in self.compiled:
            raise ValueError('unsupported forecast profile')
        compiled = self.compiled[horizon_patches]
        result = compiled({'context': inputs.contiguous().numpy(),
                           'observed': observed.contiguous().numpy()})[compiled.output(0)]
        if result.shape != (1, horizon_patches * 32, 21) or result.dtype != np.float32 or not np.isfinite(result).all():
            raise ValueError('invalid OpenVINO block result')
        return torch.from_numpy(result.copy())


class CPUForecaster(TimestralForecaster):
    """Explicit CPU device contract, avoiding parameters or loaded reference weights."""
    @property
    def device(self):
        return torch.device('cpu')


def create_forecaster(artifact_directory):
    # Upstream algorithms remain inherited and unchanged. The bounds and block size
    # are an explicit service configuration, not a claim of upstream-default parity.
    return CPUForecaster(OpenVINOBlocks(artifact_directory), max_context=256,
                         per_shot_horizon_patches=5)
