import importlib.util
from pathlib import Path
import numpy as np
import pytest

spec=importlib.util.spec_from_file_location('drift',Path(__file__).with_name('drift.py'))
drift=importlib.util.module_from_spec(spec)
spec.loader.exec_module(drift)


def test_metrics_preserve_threshold_failures_and_handle_zero_reference():
    x=np.array([0,1,1000],dtype=np.float32)
    a=x+np.array([.01,0,.1],dtype=np.float32)
    m=drift.metrics(a,x)
    assert m['violations']==2
    assert not m['strict_pass']
    assert .009 < m['max_error_scaled_by_max_abs_reference_or_one'] < .011
    assert drift.metrics(x,x)['bitwise_equal']
    for invalid in (x.astype(np.float64),x[:2],np.full(3,np.nan,dtype=np.float32)):
        with pytest.raises(AssertionError): drift.metrics(invalid,x)
