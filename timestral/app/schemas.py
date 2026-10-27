from __future__ import annotations

import math
from numbers import Real
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator


def _check_numeric_tree(value: Any, field: str, *, max_abs: float | None = None) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, Real):
        if isinstance(value, list):
            for item in value:
                _check_numeric_tree(item, field, max_abs=max_abs)
            return
        raise ValueError(f"{field} values must be finite numbers or null")
    if not math.isfinite(float(value)):
        raise ValueError(f"{field} values must be finite numbers or null")
    if max_abs is not None and abs(float(value)) > max_abs:
        raise ValueError(f"{field} values exceed the supported numeric range")


def _rectangular_shape(value: Any, field: str, ndim: int = 3) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a rectangular {ndim}-dimensional array")
    if ndim == 1:
        return (len(value),)
    child_shapes = [_rectangular_shape(item, field, ndim - 1) for item in value]
    if not child_shapes:
        return (0,) + (0,) * (ndim - 1)
    if any(shape != child_shapes[0] for shape in child_shapes):
        raise ValueError(f"{field} must be rectangular")
    return (len(value),) + child_shapes[0]


class ForecastRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: list[list[list[float | None]]]
    prediction_length: int = Field(gt=0, strict=True)
    observation_mask: list[list[list[StrictBool]]] | None = None
    past_covariates: list[list[list[float | None]]] | None = None
    known_covariates: list[list[list[float | None]]] | None = None
    categorical_past_covariates: list[list[list[float | None]]] | None = None
    categorical_known_covariates: list[list[list[float | None]]] | None = None
    symmetric_averaging: StrictBool = True
    clip_nonnegative: StrictBool = True

    @model_validator(mode="before")
    @classmethod
    def validate_values(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        for field in (
            "context", "past_covariates", "known_covariates",
            "categorical_past_covariates", "categorical_known_covariates",
        ):
            if field in value and value[field] is not None:
                categorical = field.startswith("categorical_")
                _check_numeric_tree(value[field], field, max_abs=None if categorical else 3.4028234663852886e38)
                _rectangular_shape(value[field], field)
        if value.get("observation_mask") is not None:
            _rectangular_shape(value["observation_mask"], "observation_mask")
            for row in _walk(value["observation_mask"]):
                if not isinstance(row, bool):
                    raise ValueError("observation_mask values must be booleans")
        return value

    @model_validator(mode="after")
    def validate_dimensions(self) -> "ForecastRequest":
        b, v, t = _rectangular_shape(self.context, "context")
        if b < 1 or v < 1 or t < 1:
            raise ValueError("context dimensions must be positive")
        expected = (b, v, t)
        if self.observation_mask is not None and _rectangular_shape(self.observation_mask, "observation_mask") != expected:
            raise ValueError("observation_mask shape must match context")
        for name in ("past_covariates", "categorical_past_covariates"):
            value = getattr(self, name)
            if value is not None:
                cb, _, ct = _rectangular_shape(value, name)
                if cb != b or ct != t:
                    raise ValueError(f"{name} batch and time dimensions must match context")
        for name in ("known_covariates", "categorical_known_covariates"):
            value = getattr(self, name)
            if value is not None:
                cb, _, ct = _rectangular_shape(value, name)
                if cb != b or ct != t + self.prediction_length:
                    raise ValueError(f"{name} batch must match context and time must include the prediction horizon")
        return self


def _walk(value: Any):
    if isinstance(value, list):
        for item in value:
            yield from _walk(item)
    else:
        yield value


class ForecastResponse(BaseModel):
    model: str
    revision: str
    quantile_levels: list[float]
    quantiles: list[list[list[list[float]]]]
    median: list[list[list[float]]]
