from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Callable

import numpy as np
import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from timestral import TimestralForecaster

from app.config import Settings
from app.schemas import ForecastRequest

MODEL_REVISION_209M = "9874d252ab0aae16f7f7c999f98f98d6ad7d8365"
MODEL_REVISION_5M = "bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f"


class CUDAUnavailableError(RuntimeError):
    pass


def _load_forecaster(settings: Settings) -> TimestralForecaster:
    token = settings.hf_token.get_secret_value() if settings.hf_token else None
    return TimestralForecaster.from_pretrained(
        settings.model_id,
        revision=settings.model_revision,
        device=settings.model_device,
        cache_dir=settings.hf_home,
        token=token,
    )


def _as_numpy(value: Any) -> np.ndarray:
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().numpy()
    return np.asarray(value)


def _numeric_array(value: Any, *, categorical: bool = False) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64 if categorical else np.float32)
    return np.where(array == None, np.nan, array)  # noqa: E711


def _serialize_forecast(result: Any, batch: int, variates: int, horizon: int) -> dict[str, Any]:
    quantiles = _as_numpy(result.quantiles)
    levels = tuple(float(level) for level in result.quantile_levels)
    if quantiles.ndim != 4 or quantiles.shape[:3] != (batch, variates, horizon):
        raise HTTPException(status_code=500, detail="forecast returned an invalid shape")
    if (quantiles.shape[-1] != len(levels) or len(levels) != 21 or 0.5 not in levels
            or not np.isfinite(np.asarray(levels)).all() or any(level < 0 or level > 1 for level in levels)):
        raise HTTPException(status_code=500, detail="forecast returned invalid quantile metadata")
    if not np.isfinite(quantiles).all():
        raise HTTPException(status_code=500, detail="forecast returned nonfinite values")
    median = quantiles[..., levels.index(0.5)]
    return {
        "quantile_levels": list(levels),
        "quantiles": quantiles.tolist(),
        "median": median.tolist(),
    }


def create_app(
    settings: Settings | None = None,
    model_loader: Callable[[Settings], Any] | None = None,
) -> FastAPI:
    settings = settings
    load_model = model_loader or _load_forecaster
    service_state: dict[str, Any] = {"ready": False, "forecaster": None, "busy": False}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal settings
        try:
            if settings is None:
                settings = Settings()
            cache = Path(settings.hf_home).expanduser()
            try:
                cache.mkdir(parents=True, exist_ok=True)
                probe = cache / ".timestral-write-check"
                probe.touch(exist_ok=True)
                probe.unlink(missing_ok=True)
            except OSError:
                raise RuntimeError("HF_HOME is not writable") from None
            if settings.model_device == "cuda" and not torch.cuda.is_available():
                raise CUDAUnavailableError("CUDA was requested but no usable CUDA device is available")
            torch.set_num_threads(settings.torch_num_threads)
            service_state["forecaster"] = await asyncio.to_thread(load_model, settings)
            service_state["ready"] = True
        except Exception as exc:
            service_state["forecaster"] = None
            if isinstance(exc, CUDAUnavailableError):
                raise RuntimeError(str(exc)) from None
            if str(exc) == "HF_HOME is not writable":
                raise RuntimeError(str(exc)) from None
            raise RuntimeError(f"Timestral model initialization failed ({type(exc).__name__})") from None
        try:
            yield
        finally:
            service_state["ready"] = False
            service_state["forecaster"] = None

    app = FastAPI(title="Timestral Forecast API", version="1.0.0", lifespan=lifespan)
    app.state.service = service_state

    async def forecast_request(data: ForecastRequest | dict[str, Any]) -> dict[str, Any]:
        if not service_state["ready"]:
            raise HTTPException(status_code=503, detail="model is not ready")
        if service_state["busy"]:
            raise HTTPException(status_code=503, detail="inference capacity is occupied")
        try:
            req = data if isinstance(data, ForecastRequest) else ForecastRequest.model_validate(data)
        except Exception as exc:
            raise HTTPException(status_code=422, detail="invalid forecast request") from exc

        b, v, t = _shape(req.context)
        row_count = v
        row_count += _covariate_rows(req.past_covariates)
        row_count += _covariate_rows(req.known_covariates)
        row_count += _covariate_rows(req.categorical_past_covariates)
        row_count += _covariate_rows(req.categorical_known_covariates)
        if b > settings.max_batch_size or row_count > settings.max_rows_per_series:
            raise HTTPException(status_code=422, detail="batch or row budget exceeded")
        if t > settings.max_context_steps or req.prediction_length > settings.max_prediction_length:
            raise HTTPException(status_code=422, detail="context or horizon limit exceeded")
        quantile_count = len(service_state["forecaster"].quantile_levels)
        output_size = b * v * req.prediction_length * quantile_count
        if output_size > settings.max_output_elements:
            raise HTTPException(status_code=422, detail="forecast output budget exceeded")

        kwargs: dict[str, Any] = {
            "observation_mask": np.asarray(req.observation_mask, dtype=np.bool_) if req.observation_mask is not None else None,
            "past_covariates": _numeric_array(req.past_covariates) if req.past_covariates is not None else None,
            "known_covariates": _numeric_array(req.known_covariates) if req.known_covariates is not None else None,
            "categorical_past_covariates": _numeric_array(req.categorical_past_covariates, categorical=True)
            if req.categorical_past_covariates is not None else None,
            "categorical_known_covariates": _numeric_array(req.categorical_known_covariates, categorical=True)
            if req.categorical_known_covariates is not None else None,
            "symmetric_averaging": req.symmetric_averaging,
            "clip_nonnegative": req.clip_nonnegative,
        }
        context = _numeric_array(req.context)
        service_state["busy"] = True
        inference = asyncio.create_task(asyncio.to_thread(
            service_state["forecaster"].forecast, context, req.prediction_length, **kwargs
        ))

        def release_slot(_task: asyncio.Task[Any]) -> None:
            try:
                _task.exception()
            except (asyncio.CancelledError, Exception):
                pass
            finally:
                service_state["busy"] = False

        try:
            result = await asyncio.shield(inference)
        except asyncio.CancelledError:
            inference.add_done_callback(release_slot)
            raise
        except Exception as exc:
            service_state["busy"] = False
            raise HTTPException(status_code=500, detail="forecast inference failed") from None
        service_state["busy"] = False
        data_out = _serialize_forecast(result, b, v, req.prediction_length)
        return {"model": settings.model_id, "revision": settings.model_revision, **data_out}

    app.state.forecast_request = forecast_request

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        if not service_state["ready"]:
            raise HTTPException(status_code=503, detail="model is not ready")
        return {"status": "ready"}

    @app.post("/forecast")
    async def forecast_endpoint(request: Request) -> JSONResponse:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > settings.max_request_bytes:
                    raise HTTPException(status_code=413, detail="request body too large")
            except ValueError:
                raise HTTPException(status_code=400, detail="invalid content length") from None
        pieces: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > settings.max_request_bytes:
                raise HTTPException(status_code=413, detail="request body too large")
            pieces.append(chunk)
        try:
            body = json.loads(b"".join(pieces))
        except (ValueError, UnicodeDecodeError, RecursionError):
            raise HTTPException(status_code=422, detail="request body must be valid JSON") from None
        response = await forecast_request(body)
        return JSONResponse(response)

    return app


def _shape(value: list[Any]) -> tuple[int, int, int]:
    return len(value), len(value[0]), len(value[0][0])


def _covariate_rows(value: list[Any] | None) -> int:
    return len(value[0]) if value else 0


app = create_app()
