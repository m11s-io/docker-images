import asyncio
import json
import threading
import tempfile
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


REVISION = "a" * 40
_clients = []


@pytest.fixture(autouse=True)
def close_clients(monkeypatch):
    # Docker supplies MODEL_DEVICE/HF_HOME; unit tests must control their own
    # settings rather than inherit the image's deployment configuration.
    for field in Settings.model_fields.values():
        monkeypatch.delenv(field.alias, raising=False)
    yield
    while _clients:
        _clients.pop().__exit__(None, None, None)


class Forecast:
    quantile_levels = (0.01, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45,
                       0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.99)

    def __init__(self, q):
        self.quantiles = q

    @property
    def median(self):
        return self.quantiles[..., 10]


class FakeForecaster:
    quantile_levels = Forecast.quantile_levels

    def __init__(self, block=None):
        self.block = block
        self.calls = []

    def forecast(self, context, prediction_length, **kwargs):
        self.calls.append((context, prediction_length, kwargs))
        if self.block:
            self.block.wait(timeout=5)
        b, v, _ = context.shape
        q = np.zeros((b, v, prediction_length, len(self.quantile_levels)), dtype=np.float32)
        q[..., 10] = 7
        return Forecast(q)


def client_for(settings=None, forecaster=None):
    forecaster = forecaster or FakeForecaster()
    app = create_app(settings=settings or make_settings(), model_loader=lambda _: forecaster)
    client = TestClient(app)
    client.__enter__()
    _clients.append(client)
    return client, forecaster


def make_settings(**overrides):
    overrides.setdefault("model_revision", REVISION)
    overrides.setdefault("hf_home", tempfile.mkdtemp(prefix="timestral-test-"))
    return Settings(**overrides)


def payload(**overrides):
    body = {"context": [[[1, 2, 3]]], "prediction_length": 2}
    body.update(overrides)
    return body


def flatten(value):
    if isinstance(value, list):
        for item in value:
            yield from flatten(item)
    else:
        yield value


def test_forecast_returns_quantiles_and_median_with_contract_dimensions():
    client, _ = client_for()
    response = client.post("/forecast", json=payload())
    assert response.status_code == 200
    body = response.json()
    assert body["quantile_levels"] == list(Forecast.quantile_levels)
    assert np.asarray(body["quantiles"]).shape == (1, 1, 2, 21)
    assert np.asarray(body["median"]).shape == (1, 1, 2)
    assert body["median"] == [[[7, 7]]]


def test_null_values_become_nan_before_upstream_forecast():
    client, forecaster = client_for()
    response = client.post("/forecast", json=payload(context=[[[1, None, 3]]]))
    assert response.status_code == 200
    assert np.isnan(forecaster.calls[0][0][0, 0, 1])


@pytest.mark.parametrize("change", [
    {"observation_mask": [[[True, False, True]]]},
    {"past_covariates": [[[10, 20, 30]]]},
    {"known_covariates": [[[10, 20, 30, 40, 50]]]},
    {"categorical_past_covariates": [[[1, 2, None]]]},
    {"categorical_known_covariates": [[[1, 2, 3, 4, 5]]]},
])
def test_valid_masks_and_covariates_pass_through(change):
    client, forecaster = client_for()
    response = client.post("/forecast", json=payload(**change))
    assert response.status_code == 200
    assert change.keys() <= forecaster.calls[0][2].keys()


@pytest.mark.parametrize("field,value", [
    ("context", [[[1, 2], [3]]]),
    ("context", [[1, 2, 3]]),
    ("observation_mask", [[[True, False]]]),
    ("observation_mask", [[[1, 0, 1]]]),
    ("past_covariates", [[[1, 2]]]),
    ("known_covariates", [[[1, 2, 3]]]),
    ("categorical_past_covariates", [[[1, 2]]]),
    ("categorical_known_covariates", [[[1, 2, 3]]]),
    ("context", [[[1, float("inf"), 3]]]),
    ("context", [[[1, float("nan"), 3]]]),
    ("context", [[[1, 1e100, 3]]]),
    ("context", [[[True, False, True]]]),
    ("past_covariates", [[[True, False, True]]]),
])
def test_invalid_shapes_values_and_booleans_return_422(field, value):
    client, _ = client_for()
    body = payload(**{field: value})
    if any(isinstance(item, float) and not np.isfinite(item) for item in flatten(value)):
        response = client.post("/forecast", content=json.dumps(body), headers={"content-type": "application/json"})
    else:
        response = client.post("/forecast", json=body)
    assert response.status_code == 422


def test_limits_reject_batch_rows_context_horizon_and_output_products():
    limits = make_settings(max_batch_size=1, max_rows_per_series=2,
                      max_context_steps=3, max_prediction_length=2, max_output_elements=3)
    client, _ = client_for(settings=limits)
    cases = [
        payload(context=[[[1, 2, 3]], [[1, 2, 3]]]),
        payload(context=[[[1, 2, 3], [1, 2, 3]]]),
        payload(context=[[[1, 2, 3, 4]]]),
        payload(prediction_length=3),
        payload(context=[[[1, 2, 3], [1, 2, 3]]], prediction_length=1),
    ]
    for body in cases:
        assert client.post("/forecast", json=body).status_code == 422


def test_declared_and_streamed_oversize_request_bodies_return_413():
    settings = make_settings(max_request_bytes=32)
    client, _ = client_for(settings=settings)
    assert client.post("/forecast", content=b" " * 33, headers={"content-type": "application/json",
                                                                    "content-length": "33"}).status_code == 413
    request = client.build_request("POST", "/forecast", content=b" " * 33,
                                   headers={"content-type": "application/json", "transfer-encoding": "chunked"})
    assert client.send(request).status_code == 413


def test_excessive_integer_and_nested_json_return_422():
    client, _ = client_for()
    huge_integer = b'{"context":[[[' + b"9" * 5000 + b']]],"prediction_length":1}'
    too_deep = b'{"context":' + b"[" * 2000 + b"0" + b"]" * 2000 + b',"prediction_length":1}'
    for body in (huge_integer, too_deep):
        response = client.post("/forecast", content=body, headers={"content-type": "application/json"})
        assert response.status_code == 422


def test_busy_inference_returns_503_while_health_remains_responsive():
    release = threading.Event()
    client, _ = client_for(forecaster=FakeForecaster(block=release))
    with ThreadPoolExecutor() as pool:
        first = pool.submit(client.post, "/forecast", json=payload())
        time.sleep(0.05)
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 200
        assert client.post("/forecast", json=payload()).status_code == 503
        release.set()
        assert first.result(timeout=3).status_code == 200


from concurrent.futures import ThreadPoolExecutor


def test_capacity_stays_occupied_after_async_request_cancellation():
    release = threading.Event()
    client, _ = client_for(forecaster=FakeForecaster(block=release))
    app = client.app
    async def exercise():
        payload_obj = {"context": [[[1, 2, 3]]], "prediction_length": 1}
        first = asyncio.create_task(app.state.forecast_request(payload_obj))
        await asyncio.sleep(0.05)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        with pytest.raises(Exception) as error:
            await app.state.forecast_request(payload_obj)
        assert getattr(error.value, "status_code", None) == 503
        release.set()
        await asyncio.sleep(0.05)
        result = await app.state.forecast_request(payload_obj)
        assert result["median"] == [[[7]]]
    asyncio.run(exercise())


def test_cancelled_worker_failure_is_consumed_and_capacity_recovers():
    release = threading.Event()

    class FailingForecaster(FakeForecaster):
        def forecast(self, *args, **kwargs):
            release.wait(timeout=5)
            raise RuntimeError("private upstream detail")

    app = create_app(settings=make_settings(), model_loader=lambda _: FailingForecaster())
    with TestClient(app) as client:
        async def exercise():
            data = {"context": [[[1, 2, 3]]], "prediction_length": 1}
            first = asyncio.create_task(app.state.forecast_request(data))
            await asyncio.sleep(0.05)
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            release.set()
            await asyncio.sleep(0.05)
            with pytest.raises(Exception) as error:
                await app.state.forecast_request(data)
            assert getattr(error.value, "status_code", None) == 500
        asyncio.run(exercise())


def test_health_and_ready_probe_states():
    app = create_app(settings=make_settings(), model_loader=lambda _: None)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 200


def test_missing_model_revision_is_a_configuration_error(monkeypatch):
    monkeypatch.delenv("MODEL_REVISION", raising=False)
    with pytest.raises(Exception):
        Settings(_env_file=None)


def test_cuda_request_fails_startup_without_device(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main.torch.cuda, "is_available", lambda: False)
    app = create_app(settings=make_settings(model_device="cuda"), model_loader=lambda _: FakeForecaster())
    with pytest.raises(RuntimeError, match="CUDA"):
        with TestClient(app):
            pass


def test_model_load_failure_is_sanitized():
    app = create_app(settings=make_settings(hf_token="hf-secret"),
                     model_loader=lambda _: (_ for _ in ()).throw(RuntimeError("hf-secret upstream")))
    with pytest.raises(RuntimeError) as error:
        with TestClient(app):
            pass
    assert "hf-secret" not in str(error.value)




def test_unwritable_cache_fails_with_actionable_error(tmp_path):
    file_path = tmp_path / "not-a-directory"
    file_path.write_text("x")
    app = create_app(settings=Settings(model_revision=REVISION, hf_home=str(file_path)),
                     model_loader=lambda _: FakeForecaster())
    with pytest.raises(RuntimeError, match="HF_HOME is not writable"):
        with TestClient(app):
            pass


def test_openapi_describes_forecast_contract():
    client, _ = client_for()
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/forecast"]["post"]
    request = operation["requestBody"]["content"]["application/json"]["schema"]
    assert set(request["required"]) == {"context", "prediction_length"}
    assert "observation_mask" in request["properties"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/ForecastResponse")


def test_model_failure_logs_sanitized_diagnostic(caplog):
    def fail(_):
        raise OSError("download failed hf-secret https://example.org/model?token=private")
    app = create_app(settings=make_settings(hf_token="hf-secret"), model_loader=fail)
    with pytest.raises(RuntimeError), TestClient(app):
        pass
    assert "download failed" in caplog.text
    assert "OSError" in caplog.text
    assert "hf-secret" not in caplog.text
    assert "token=private" not in caplog.text


def test_inference_failure_logs_detail_but_returns_generic_error(caplog):
    class BrokenForecaster(FakeForecaster):
        def forecast(self, *args, **kwargs):
            raise RuntimeError("tensor allocation failed")
    client, _ = client_for(forecaster=BrokenForecaster())
    response = client.post("/forecast", json=payload())
    assert response.status_code == 500
    assert response.json()["detail"] == "forecast inference failed"
    assert "tensor allocation failed" in caplog.text
