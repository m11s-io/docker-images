"""Generate unchanged-upstream forecasts in the candidate's exact userland.

Mount this diagnostic code externally. Do not import the serving adapter: the
reference remains an independent direct upstream forecast invocation. Matching
framework, glibc/libm and CPU dispatch avoids attributing platform rounding to
transport differences in numerically sensitive autoregressive horizons.
"""
import json
import os
from pathlib import Path

import numpy as np
import torch
from timestral import TimestralForecaster
from forecast_cases import CASES, make_case


def main():
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision('highest')
    model_id, revision = os.environ['MODEL_ID'], os.environ['MODEL_REVISION']
    reference = TimestralForecaster.from_pretrained(model_id, revision=revision,
        device='cpu', cache_dir=os.environ['HF_HOME'])
    destination = Path('/reference')
    destination.mkdir(exist_ok=True)
    for case in CASES:
        _, _, _, h, context, values, kwargs = make_case(case, reference.max_context)
        expected = reference.forecast(context, h, **kwargs)
        np.savez(destination/f'{case}.npz', **{'input_'+k: v for k,v in values.items()}, quantiles=expected.quantiles.cpu().numpy(),
                 median=expected.median.cpu().numpy(),
                 quantile_levels=np.asarray(expected.quantile_levels,dtype=np.float32))
    (destination/'metadata.json').write_text(json.dumps(dict(model_id=model_id,
        revision=revision, max_context=reference.max_context, torch=torch.__version__)))


if __name__ == '__main__':
    main()
