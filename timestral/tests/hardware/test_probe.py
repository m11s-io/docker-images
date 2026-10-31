import importlib.util
from pathlib import Path
import numpy as np
import pytest

spec = importlib.util.spec_from_file_location('hardware_probe', Path(__file__).with_name('probe.py'))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_comparison_rejects_numerical_shape_and_dtype_regressions():
    expected = {'quantiles': np.ones((1, 1, 3, 21), dtype=np.float32)}
    assert probe.compare(expected, expected) == {'quantiles': 0}
    for bad in (np.zeros((1, 1, 3, 21), dtype=np.float32),
                np.ones((1, 1, 3, 20), dtype=np.float32),
                np.ones((1, 1, 3, 21), dtype=np.float64),
                np.full((1, 1, 3, 21), np.nan, dtype=np.float32)):
        with pytest.raises(AssertionError):
            probe.compare({'quantiles': bad}, expected)


def test_fixtures_cover_masks_options_grouped_rows_and_covariates():
    cases = {name: (values, h, kwargs) for name, values, h, kwargs in probe.fixtures()}
    assert len(cases) == 10
    assert cases['grouped'][0]['context'].shape[:2] == (2, 2)
    assert cases['decode-blocks'][1] == 1024
    assert not cases['missing'][0]['observation_mask'].all()
    for name in ('symmetry-off', 'clip-off', 'both-off'):
        values, _, kwargs = cases[name]
        for option in ('symmetric_averaging', 'clip_nonnegative'):
            assert values[option][0] == kwargs[option]
    values, _, kwargs = cases['covariates']
    for name in ('past_covariates', 'known_covariates',
                 'categorical_past_covariates', 'categorical_known_covariates'):
        assert np.isfinite(values[name]).all()
        assert np.isnan(kwargs[name]).any()
        assert values[name].shape == values[name+'_mask'].shape


def test_request_roundtrips_official_grpc_names_types_and_identity():
    from kserve import InferRequest
    _, values, _, _ = next(probe.fixtures())
    decoded = InferRequest.from_grpc(probe.request(values, 'hardware-probe').to_grpc())
    assert decoded.id == 'hardware-probe'
    assert decoded.model_name == 'timestral'
    for tensor in decoded.inputs:
        np.testing.assert_array_equal(tensor.as_numpy(), values[tensor.name])
