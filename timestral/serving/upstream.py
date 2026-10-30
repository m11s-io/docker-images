"""Load pinned upstream weights and invoke its unchanged forecasting API."""
from dataclasses import dataclass
import os
from pathlib import Path
import re

import numpy as np
from kserve.errors import InvalidInput

from .contract import ForecastInputs, ForecastResult


@dataclass(frozen=True)
class Settings:
    model_revision: str
    model_id: str = 'mistralai/Timestral-209M'
    backend: str = 'cpu'
    model_device: str = 'cpu'
    hf_home: str = '/models/huggingface'
    torch_num_threads: int = 2

    def __post_init__(self):
        if not re.fullmatch(r'[0-9a-f]{40}', self.model_revision):
            raise ValueError('MODEL_REVISION must be an immutable commit')
        if self.model_id not in {f'mistralai/Timestral-{n}M' for n in (5,28,123,209)}:
            raise ValueError('unsupported MODEL_ID')
        if self.backend not in ('cpu','cuda','rocm','openvino'):
            raise ValueError('unsupported backend')
        if self.torch_num_threads < 1 or not self.hf_home:
            raise ValueError('invalid thread count or model cache')
        if self.backend in ('cpu','openvino'):
            if self.model_device != 'cpu': raise ValueError('backend requires explicit cpu device')
        elif not re.fullmatch(r'cuda(?::[0-9]+)?',self.model_device):
            raise ValueError('accelerator backend requires explicit cuda device')

    @classmethod
    def from_env(cls):
        return cls(model_revision=os.environ.get('MODEL_REVISION',''),
                   model_id=os.environ.get('MODEL_ID','mistralai/Timestral-209M'),
                   backend=os.environ.get('TIMESTRAL_BACKEND','cpu'),
                   model_device=os.environ.get('MODEL_DEVICE','cpu'),
                   hf_home=os.environ.get('HF_HOME','/models/huggingface'),
                   torch_num_threads=int(os.environ.get('TORCH_NUM_THREADS','2')))


def _check_device(settings, torch):
    device = torch.device(settings.model_device)
    if settings.backend == 'cpu': return device
    if not torch.cuda.is_available(): raise RuntimeError('requested accelerator is unavailable')
    if settings.backend == 'cuda':
        if torch.version.hip or not torch.version.cuda:
            raise RuntimeError('NVIDIA accelerator requires CUDA framework')
    elif settings.backend == 'rocm':
        if not torch.version.hip or torch.version.cuda:
            raise RuntimeError('AMD accelerator requires HIP framework')
        if os.environ.get('HSA_OVERRIDE_GFX_VERSION'):
            raise RuntimeError('GPU architecture overrides are forbidden')
    index = device.index if device.index is not None else 0
    if index >= torch.cuda.device_count(): raise RuntimeError('requested accelerator index is unavailable')
    properties = torch.cuda.get_device_properties(index)
    if settings.backend == 'rocm':
        if getattr(properties,'gcnArchName','').split(':')[0] != 'gfx1201':
            raise RuntimeError('unsupported AMD accelerator architecture')
    else:
        architecture = f'sm_{properties.major}{properties.minor}'
        if architecture not in torch.cuda.get_arch_list():
            raise RuntimeError('framework lacks requested NVIDIA accelerator architecture')
    torch.cuda.set_device(index)
    return torch.device('cuda', index)


class UpstreamForecaster:
    def __init__(self, forecaster):
        self.forecaster = forecaster

    @classmethod
    def load(cls, settings: Settings):
        import torch
        from timestral import TimestralForecaster
        if settings.backend == 'openvino':
            raise RuntimeError('OpenVINO profile backend is not accepted yet')
        device = _check_device(settings, torch)
        cache = Path(settings.hf_home).expanduser()
        cache.mkdir(parents=True,exist_ok=True)
        # Verify writable storage without placing weights in the image.
        import tempfile
        with tempfile.TemporaryFile(dir=cache): pass
        torch.set_num_threads(settings.torch_num_threads)
        forecaster = TimestralForecaster.from_pretrained(
            settings.model_id, revision=settings.model_revision, device=device,
            cache_dir=str(cache), token=os.environ.get('HF_TOKEN') or None)
        parameters = list(forecaster.model.parameters())
        if not parameters or any(p.device != device or p.dtype != torch.float32 for p in parameters):
            raise RuntimeError('loaded model does not match requested device and FP32 precision')
        return cls(forecaster)

    def forecast(self, inputs: ForecastInputs) -> ForecastResult:
        if inputs.covariates and not self.forecaster.supports_covariates:
            raise InvalidInput('checkpoint does not support covariates')
        if any('known' in name for name in inputs.covariates) and not self.forecaster.supports_known_covariates:
            raise InvalidInput('checkpoint does not support known-future covariates')
        result = self.forecaster.forecast(
            inputs.context, inputs.prediction_length,
            observation_mask=inputs.observation_mask,
            symmetric_averaging=inputs.symmetric_averaging,
            clip_nonnegative=inputs.clip_nonnegative, **inputs.covariates)
        return ForecastResult(result.quantiles.detach().cpu().numpy(),
                              np.asarray(result.quantile_levels,dtype=np.float32))
