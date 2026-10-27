"""Opt-in comparisons against the pinned upstream Timestral checkpoint."""

import os
import tempfile

import numpy as np
import pytest
from fastapi.testclient import TestClient
from timestral import TimestralForecaster

from app.config import Settings
from app.main import create_app

MODEL_REVISION_5M = "bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f"

pytestmark = [pytest.mark.cpu, pytest.mark.skipif(
    os.getenv("TIMESTRAL_RUN_REAL_TESTS") != "1",
    reason="set TIMESTRAL_RUN_REAL_TESTS=1 to download the pinned checkpoint",
)]


def test_cpu_http_forecast_matches_direct_upstream_with_missing_values_and_covariates():
    forecaster = TimestralForecaster.from_pretrained(
        "mistralai/Timestral-5M", revision=MODEL_REVISION_5M, device="cpu"
    )
    settings = Settings(
        model_id="mistralai/Timestral-5M",
        model_revision=MODEL_REVISION_5M,
        model_device="cpu",
        hf_home=tempfile.mkdtemp(prefix="timestral-smoke-"),
        max_context_steps=512,
        max_prediction_length=96,
    )
    app = create_app(settings=settings, model_loader=lambda _: forecaster)
    context = [[[1.0, 1.5, None, 2.5, 3.0, 2.0, 4.0, 3.5]]]
    past_covariates = [[[0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]]]
    known_covariates = [[[0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0]]]
    categorical_past_covariates = [[[1, 1, 2, 2, 1, 3, 3, 3]]]
    categorical_known_covariates = [[[1, 1, 2, 2, 1, 3, 3, 3, 2, 1, 3]]]
    direct = forecaster.forecast(
        np.array(context, dtype=np.float32),
        prediction_length=3,
        past_covariates=np.array(past_covariates, dtype=np.float32),
        known_covariates=np.array(known_covariates, dtype=np.float32),
        categorical_past_covariates=np.array(categorical_past_covariates, dtype=np.float64),
        categorical_known_covariates=np.array(categorical_known_covariates, dtype=np.float64),
    )
    with TestClient(app) as client:
        response = client.post("/forecast", json={
            "context": context,
            "prediction_length": 3,
            "past_covariates": past_covariates,
            "known_covariates": known_covariates,
            "categorical_past_covariates": categorical_past_covariates,
            "categorical_known_covariates": categorical_known_covariates,
        })
    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "mistralai/Timestral-5M"
    assert body["revision"] == MODEL_REVISION_5M
    np.testing.assert_allclose(body["quantiles"], direct.quantiles.detach().cpu().numpy(), rtol=1e-5, atol=1e-5)
    np.testing.assert_allclose(body["median"], direct.median.detach().cpu().numpy(), rtol=1e-5, atol=1e-5)
