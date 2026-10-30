"""Preserved export safeguards; no checkpoint downloads in unit tests."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]/'export'


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/f'{name}.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_guarded_rewrites_leave_reference_source_untouched(tmp_path):
    rewrites=load('rewrites')
    source=tmp_path/'original'; destination=tmp_path/'patched'
    (source/'src/timestral').mkdir(parents=True)
    scaler='means.unfold(-1, patch_size, patch_size)\nscales.unfold(-1, patch_size, patch_size)\n'
    masks='started = obs_per_patch.cummax(dim=-1).values\n'
    (source/'src/timestral/scaler.py').write_text(scaler)
    (source/'src/timestral/masks.py').write_text(masks)
    rewrites.patch_source(source,destination)
    assert (source/'src/timestral/scaler.py').read_text()==scaler
    assert (source/'src/timestral/masks.py').read_text()==masks
    assert '.unfold(' not in (destination/'src/timestral/scaler.py').read_text()
    assert 'cumsum' in (destination/'src/timestral/masks.py').read_text()


def test_source_drift_fails_without_a_partial_copy(tmp_path):
    rewrites=load('rewrites')
    source=tmp_path/'original'; destination=tmp_path/'patched'
    (source/'src/timestral').mkdir(parents=True)
    (source/'src/timestral/scaler.py').write_text('upstream changed')
    with pytest.raises(ValueError,match='source drift'): rewrites.patch_source(source,destination)
    assert not destination.exists()


def test_final_forecast_gate_rejects_bad_shape_dtype_finiteness_and_parity():
    exporter=load('profiles')
    expected=np.ones((1,1,65,21),dtype=np.float32)
    assert exporter.validate_outputs(expected,expected,65)['max_absolute_error']==0
    for actual in [expected[...,0],expected.astype(np.float16),expected*np.nan,expected+.1]:
        with pytest.raises((ValueError,AssertionError)): exporter.validate_outputs(expected,actual,65)
