"""The accepted 5M tail exception never changes the strict measurements."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest
spec=importlib.util.spec_from_file_location('divergence',Path(__file__).parents[1]/'serving/divergence.py')
m=importlib.util.module_from_spec(spec)
if Path(spec.origin).exists():spec.loader.exec_module(m)


def test_measured_tail_exception_is_explicit_and_scoped():
    e=np.ones((1,1,1024,21),np.float32);a=e.copy();a.flat[0]+=.0003
    r=m.assess(a,e,model_id='mistralai/Timestral-5M',case='maximum-horizon')
    assert not r['strict_passed'] and r['accepted']
    assert r['outside_original_tolerance']==1 and r['exception']=='5m-long-horizon-tails-2026-11-02'
    for model,case in [('mistralai/Timestral-209M','maximum-horizon'),('mistralai/Timestral-5M','unreviewed')]:
        assert not m.assess(a,e,model_id=model,case=case)['accepted']


def test_exception_rejects_broad_drift_median_drift_and_invalid_outputs():
    e=np.ones((1,1,1024,21),np.float32)
    for a in [e+.0003,e.copy(),e.copy()]:
        if np.array_equal(a,e):a[...,10]+=.0003
        assert not m.assess(a,e,model_id='mistralai/Timestral-5M',case='blocks')['accepted']
    a=e.copy();a.flat[0]+=.001
    assert not m.assess(a,e,model_id='mistralai/Timestral-5M',case='blocks')['accepted']
    for a in [e[...,0],e.astype(np.float16),e*np.nan]:
        with pytest.raises(ValueError):m.assess(a,e,model_id='mistralai/Timestral-5M',case='blocks')


def test_reviewed_ci_tail_envelope():
    e=np.ones((1,1,1024,21),np.float32)
    for ratio,accepted in [(2.29825,True),(2.31,False)]:
        a=e.copy();a.flat[0]+=np.float32(.0002*ratio)
        r=m.assess(a,e,model_id='mistralai/Timestral-5M',case='blocks')
        assert not r['strict_passed']
        assert r['accepted']==accepted
