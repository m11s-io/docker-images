import importlib.util
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('cross_device',Path(__file__).with_name('cross_device.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_independent_cases_cover_scales_masks_grouping_and_options():
    cases=list(module.cases());assert len(cases)==54
    assert {c[-1] for c in cases}=={.001,1.,1000.}
    assert {c[3] for c in cases}=={160,1024}
    assert any(c[1].shape[:2]==(2,2) for c in cases)
    assert any(not c[2].all() for c in cases)
    assert all(np.isfinite(c[1]).all() for c in cases)


def test_unit_floor_cannot_hide_small_input_scale_drift():
    e=np.array([.001],dtype=np.float32);a=e+.0001
    metric=module.budget_metrics(a,e,.001)
    assert metric['provisional_unit_budget_pass']
    assert not metric['provisional_input_scale_budget_pass']
    assert metric['original_violations']==1
