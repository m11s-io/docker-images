import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('forecast_cases',Path(__file__).parent/'integration/forecast_cases.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_openvino_conversion_policy_is_distinct_from_unchanged_framework_policy():
    assert module.forecast_tolerances(False)=={'rtol':1e-5,'atol':1e-5}
    assert module.forecast_tolerances(True)=={'rtol':1e-4,'atol':1e-4}
