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


def test_openvino_fixtures_are_identical_to_normal_cpu():
    cpu=list(probe.fixtures('cpu'));actual=list(probe.fixtures('openvino'))
    assert [x[0] for x in actual]==[x[0] for x in cpu]
    for (_,a,h,kwargs),(_,b,expected_h,_) in zip(actual,cpu):
        assert h==expected_h
        assert set(a)==set(b)
        for key in a:np.testing.assert_array_equal(a[key],b[key])


def test_openvino_conversion_policy_does_not_relax_pytorch_comparison():
    expected = {'quantiles': np.ones((1,1,3,21), dtype=np.float32)}
    actual = {'quantiles': expected['quantiles'] + np.float32(5e-5)}
    probe.compare(actual, expected, 'openvino')
    for backend in ('cpu','cuda','rocm'):
        with pytest.raises(AssertionError):
            probe.compare(actual, expected, backend)


def test_identity_checks_decode_official_grpc_parameter_values():
    from kserve import InferResponse
    revision = 'a'*40
    response = InferResponse('id', 'timestral', [], model_version=revision,
                            parameters={'model_id':'mistralai/Timestral-5M', 'backend':'cpu'})
    decoded = InferResponse.from_grpc(response.to_grpc())
    assert probe.parameter_value(decoded.parameters['model_id']) == 'mistralai/Timestral-5M'
    assert probe.parameter_value('cpu') == 'cpu'


def test_conversion_tolerance_does_not_relax_quantile_level_identity():
    expected = {'quantile_levels': np.full(21, .5, dtype=np.float32)}
    actual = {'quantile_levels': expected['quantile_levels'] + np.float32(5e-6)}
    with pytest.raises(AssertionError):
        probe.compare(actual, expected, 'openvino')
